#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2012 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""This file contains classes to handle the transmission protobuf.

The classes are designed to create and process the transmission protobuf.
This involves opening up files and returning filehandles and creating
protobufs that can accurately describe files and their locations so they
can be successfully opened by Plaso.

"""
import bz2
import gzip
import logging
import os
import tarfile
import zipfile

import pytsk3
import pyvshadow

from plaso.lib import errors
from plaso.lib import registry
from plaso.lib import sleuthkit
from plaso.lib import timelib
from plaso.lib import vss
from plaso.proto import transmission_pb2

# TODO: Add support for "carving" embedded files
# out using the embedded portion of the proto.


class FilesystemContainer(object):
  """A container for the filesystem and image."""

  def __init__(self, fs, img, path, offset=0, volume=None, store_nr=-1):
    """Container for objects needed to cache a filesystem connection.

    Args:
      fs: A FS_Info object.
      img: An Img_Info object.
      path: The path to the image.
      offset: An offset to the image.
      volume: If this is a VSS, the volume object.
      store_nr: If this is a VSS, the store number.
    """
    self.fs = fs
    self.img = img
    self.path = path
    self.offset = offset
    self.volume = volume
    self.store_nr = store_nr


class FilesystemCache(object):
  """A class to open and store filesystem objects in cache."""

  cached_filesystems = {}

  @classmethod
  def OpenTskImage(cls, path, offset=0):
    """Open and store a regular TSK image in cache.

    Args:
      path: Full path to the image file.
      offset: Offset in bytes to the start of the volume.

    Returns:
      A FilesystemContainer object that stores a cache of the FS.
    """
    img = pytsk3.Img_Info(path)
    fs = pytsk3.FS_Info(img, offset=offset)
    return FilesystemContainer(fs, img, path, offset)

  @classmethod
  def OpenVssImage(cls, path, store_nr, offset=0):
    """Open and store a VSS image in cache.

    Args:
      path: Full path to the image file.
      store_nr: Integer, indicating the VSS store number.
      offset: Offset in bytes to the start of the volume.

    Returns:
      A FilesystemContainer object that stores a cache of the FS.
    """
    volume = pyvshadow.volume()
    fh = vss.VShadowVolume(path, offset)
    volume.open_file_object(fh)
    store = volume.get_store(store_nr)
    img = vss.VShadowImgInfo(store)
    fs = pytsk3.FS_Info(img)

    return FilesystemContainer(fs, img, path, offset, volume, store_nr)

  @classmethod
  def Open(cls, path, offset=0, store_nr=-1):
    """Return a filesystem from the cache.

    Args:
      path: Full path to the image file.
      offset: Offset in bytes to the start of the volume.
      store_nr: If this is a VSS then the store nr.

    Returns:
      If the filesystem object is cached it will be returned,
      otherwise it will be opened and then returned.
    """
    fs_hash = u'%s:%d:%d' % (path, offset, store_nr)

    if fs_hash in cls.cached_filesystems:
      return cls.cached_filesystems[fs_hash]

    if store_nr >= 0:
      fs = cls.OpenVssImage(path, store_nr, offset)
    else:
      fs = cls.OpenTskImage(path, offset)

    cls.cached_filesystems[fs_hash] = fs
    return fs


class PlasoFile(object):
  """Base class for a file like object."""
  __metaclass__ = registry.MetaclassRegistry
  __abstract = True  # pylint: disable=C6409

  TYPE = transmission_pb2.PathSpec.UNSET
  fh = None

  def __init__(self, proto, root=None):
    """Constructor.

    Args:
      proto: The transmission_proto that describes the file.
      root: The root transmission_proto that describes the file if one exists.

    Raises:
      IOError: If this class supports the wrong driver for this file.
    """
    self.pathspec = proto
    if root:
      self.pathspec_root = root
    else:
      self.pathspec_root = proto
    self.name = ''

    if proto.type != self.TYPE:
      raise errors.UnableToOpenFile('Unable to handle this file type.')

  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc_value, traceback):
    self.close()
    return False

  def __str__(self):
    if hasattr(self, 'display_name'):
      return self.display_name
    else:
      return 'Unknown File'

  # Implementing an interface.
  def seek(self, offset, whence=0):   # pylint: disable=C6409
    """Seek to an offset in the file."""
    if self.fh:
      self.fh.seek(offset, whence)
    else:
      raise RuntimeError('Unable to seek into a file that is not open.')

  # Implementing an interface.
  def read(self, size=None):   # pylint: disable=C6409
    """Read size bytes from file and return them."""
    if self.fh:
      # Some internal implementations require unbound read operations
      # to use a -1 as the default value, others None.
      try:
        return self.fh.read(size)
      except TypeError:
        return self.fh.read(-1)
    else:
      return ''

  # Implementing an interface.
  def tell(self):   # pylint: disable=C6409
    """Return the current offset into the file."""
    if self.fh:
      return self.fh.tell()
    else:
      return 0

  # Implementing an interface.
  def close(self):    # pylint: disable=C6409
    """Close the file."""
    if self.fh:
      self.fh.close()
      self.fh = None

  # Implementing an interface.
  def readline(self, size=None):    # pylint: disable=C6409
    """Read a line from the file.

    Args:
      size: Defines the maximum byte count (including the new line trail)
      and if defined may get the function to return an incomplete line.

    Returns:
      A string containing a single line read from the file.
    """
    if self.fh:
      return self.fh.readline(size)
    else:
      return ''

  def Open(self, filehandle=None):
    """Open the file as it is described in the PathSpec protobuf.

    This method reads the content of the PathSpec protobuf and opens
    the filehandle up according to the driver the class supports.

    Filehandle can be passed to the method if the file that needs to
    be opened is within another file.

    Args:
      filehandle: A PlasoFile object that the file is contained within.
    """
    raise NotImplementedError

  def Stat(self):
    """Return a Stats object that contains stats like information."""
    raise NotImplementedError

  def HasParent(self):
    """Check if the PathSpec defines a parent."""
    return self.pathspec.HasField('nested_pathspec')


class TskFile(PlasoFile):
  """Class to open up files using TSK."""

  TYPE = transmission_pb2.PathSpec.TSK

  def _OpenFileSystem(self, path, offset):
    """Open the filesystem object and store a copy of it for caching.

    Args:
      path: Path to the image file.
      offset: If this is a disk partition an offset to the filesystem
      is needed.
    """
    fs_obj = FilesystemCache.Open(path, offset)

    self._fs = fs_obj.fs

  def Stat(self):
    """Return a Stats object that contains stats like information."""
    ret = Stats()
    if not self.fh:
      return ret

    info = self.fh.fileobj.info
    meta = info.meta
    if not meta:
      return ret

    ret.mode = meta.mode
    try:
      ret.ino = meta.addr
    except AttributeError:
      pass

    try:
      ret.nlink = meta.nlink
    except AttributeError:
      pass

    try:
      ret.uid = meta.uid
      ret.gid = meta.gid
    except AttributeError:
      pass

    try:
      ret.size = meta.size
    except AttributeError:
      pass

    try:
      ret.atime = meta.atime
      ret.atime_nano = meta.atime_nano
    except AttributeError:
      pass

    try:
      ret.crtime = meta.crtime
      ret.crtime_nano = meta.crtime_nano
    except AttributeError:
      pass

    try:
      ret.mtime = meta.mtime
      ret.mtime_nano = meta.mtime_nano
    except AttributeError:
      pass

    try:
      ret.ctime = meta.ctime
      ret.ctime_nano = meta.ctime_nano
    except AttributeError:
      pass

    try:
      ret.dtime = meta.ctime
      ret.dtime_nano = meta.ctime_nano
    except AttributeError:
      pass

    try:
      ret.bkup_time = meta.ctime
      ret.bkup_time_nano = meta.ctime_nano
    except AttributeError:
      pass

    fs_type = str(self._fs.info.ftype)
    if len(fs_type) > 12:
      ret.os_type = fs_type[12:]
    else:
      ret.os_type = fs_type

    return ret

  def Open(self, filehandle=None):
    """Open the file as it is described in the PathSpec protobuf.

    This method reads the content of the PathSpec protobuf and opens
    the filehandle using the Sleuthkit (TSK).

    Args:
      filehandle: A PlasoFile object that the file is contained within.
    """
    if filehandle:
      path = filehandle
    else:
      path = self.pathspec.container_path

    if self.pathspec.HasField('image_offset'):
      self._OpenFileSystem(path, self.pathspec.image_offset)
    else:
      self._OpenFileSystem(path, 0)

    inode = 0
    if self.pathspec.HasField('image_inode'):
      inode = self.pathspec.image_inode

    self.fh = sleuthkit.Open(self._fs, inode, self.pathspec.file_path)

    self.name = self.pathspec.file_path
    self.size = self.fh.size
    self.display_name = u'%s:%s' % (self.pathspec.container_path,
                                    self.pathspec.file_path)
    if filehandle:
      self.display_name = u'%s:%s' % (filehandle.name, self.display_name)


class OsFile(PlasoFile):
  """Class to provide a file-like object to a file stored on a filesystem."""

  TYPE = transmission_pb2.PathSpec.OS

  def Open(self, filehandle=None):
    """Open the file as it is described in the PathSpec protobuf."""
    self.fh = open(self.pathspec.file_path, 'rb')
    self.name = self.pathspec.file_path
    if filehandle:
      self.display_name = u'%s:%s' % (filehandle.name, self.name)
    else:
      self.display_name = self.name

  def readline(self, size=-1):
    """Read a line from the file.

    Args:
      size: Defines the maximum byte count (including the new line trail)
      and if defined may get the function to return an incomplete line.

    Returns:
      A string containing a single line read from the file.
    """
    if self.fh:
      return self.fh.readline(size)
    else:
      return ''

  def Stat(self):
    """Return a Stats object that contains stats like information."""
    ret = Stats()
    if not self.fh:
      return ret

    stat = os.stat(self.name)
    ret.mode = stat.st_mode
    ret.ino = stat.st_ino
    ret.dev = stat.st_dev
    ret.nlink = stat.st_nlink
    ret.uid = stat.st_uid
    ret.gid = stat.st_gid
    ret.size = stat.st_size
    ret.atime = stat.st_atime
    ret.mtime = stat.st_mtime
    ret.ctime = stat.st_ctime
    ret.os_type = 'Unknown'

    return ret


class ZipFile(PlasoFile):
  """Provide a file-like object to a file stored inside a ZIP file."""
  TYPE = transmission_pb2.PathSpec.ZIP

  def Stat(self):
    """Return a Stats object that contains stats like information."""
    ret = Stats()

    if not self.fh:
      return ret

    # TODO: Make this a proper stat element with as much information
    # as can be extracted.
    # Also confirm for sure that this is the correct timestamp and it is
    # stored in UTC (or if it is in local timezone, adjust it)
    ret.ctime = timelib.Timetuple2Timestamp(self.zipinfo.date_time)
    ret.ino = self.inode
    ret.size = self.zipinfo.file_size
    ret.os_type = 'ZIP Container'
    return ret

  def Open(self, filehandle=None):
    """Open the file as it is described in the PathSpec protobuf."""
    if filehandle:
      zf = zipfile.ZipFile(filehandle, 'r')
      path_name = filehandle.name
      self.inode = getattr(filehandle.Stat(), 'ino', 0)
    else:
      path_name = self.pathspec.container_path
      zf = zipfile.ZipFile(path_name, 'r')
      self.inode = os.stat(path_name).st_ino

    self.name = self.pathspec.file_path
    self.display_name = u'%s:%s' % (path_name, self.pathspec.file_path)
    self.offset = 0
    self.orig_fh = filehandle
    self.zipinfo = zf.getinfo(self.pathspec.file_path)
    self.size = self.zipinfo.file_size
    try:
      self.fh = zf.open(self.pathspec.file_path, 'r')
    except RuntimeError as e:
      raise IOError('Unable to open ZIP file: {%s} -> %s' % (self.name, e))

  def read(self, size=None):
    """Read size bytes from file and return them."""
    if not self.fh:
      return ''

    # There is an error in the ZipExtFile, at least with Python v 2.6.
    # If a readline is called the results are stored in linebuffer,
    # while read uses the readbuffer for buffer, ignoring the content
    # of linebuffer.
    if hasattr(self.fh, 'linebuffer'):
      if self.fh.linebuffer:
        self.fh.readbuffer = self.fh.linebuffer + self.fh.readbuffer
        self.fh.linebuffer = ''

    if size is None:
      size = min(self.size - self.offset, 1024 * 1024 * 24)
      logging.debug(u'[ZIP] Unbound read attempted: %s -> %s', self.name,
                    self.display_name)
      if size != self.size - self.offset:
        logging.debug('[ZIP] Not able to read in the entire file (too large).')

    line = self.fh.read(size)
    self.offset += len(line)
    return line

  def readline(self, size=None):
    """Read a line from the file.

    Args:
      size: Defines the maximum byte count (including the new line trail)
      and if defined may get the function to return an incomplete line.

    Returns:
      A string containing a single line read from the file.
    """
    if self.fh:
      line = self.fh.readline(size)
      self.offset += len(line)
      return line
    else:
      return ''

  def tell(self):
    """Return the current offset into the file.

    A ZipExtFile object maintains an object called fileobj that implements
    a tell function, which reads the offset into the current fileobj.

    However, that object may have some data that has been read in that is
    stored in buffers, so we need to subtract buffer read data to get the
    actual offset into the file.

    Returns:
      An offset into the file, indicating current location.
    """
    if not self.fh:
      return 0

    return self.offset

  def close(self):
    if self.fh:
      self.fh.close()
      self.fh = None
      self.offset = 0

  def seek(self, offset, whence=0):
    if not self.fh:
      raise RuntimeError('Unable to seek into a file that is not open.')

    if whence == 0:
      self.close()
      self.Open(self.orig_fh)
      _ = self.read(offset)
    elif whence == 1:
      if offset > 0:
        _ = self.read(offset)
      else:
        ofs = self.offset + offset
        self.seek(ofs)
    elif whence == 2:
      ofs = self.size + offset
      if ofs > self.offset:
        _ = self.read(ofs - self.offset)
      else:
        self.seek(0)
        _ = self.read(ofs)
    else:
      raise RuntimeError('Illegal whence value %s' % whence)


class GzipFile(PlasoFile):
  """Provide a file-like object to a file compressed using GZIP."""
  TYPE = transmission_pb2.PathSpec.GZIP

  def Stat(self):
    """Return a Stats object that contains stats like information."""
    ret = Stats()
    if not self.fh:
      return ret

    ret.size = self.size
    ret.ino = self.inode
    ret.os_type = 'GZ File'

    return ret

  def seek(self, offset, whence=0):
    """Seek into a specific location in a file.

    This method implements a simple method to seek into a
    compressed file from the end, which is not implemented by the
    gzip library.

    Args:
      offset: An integer, indicating the number of bytes to seek in file,
      how that value is interpreted depends on the 'whence' value.
      whence: An integer; 0 means from beginning, 1 from last position
      and 2 indicates we are about to seek from the end of the file.

    Raises:
      RuntimeError: If a seek is attempted to a closed file.
    """
    if not self.fh:
      raise RuntimeError('Unable to seek into a file that is not open.')

    if whence == 2:
      ofs = self.size + offset
      if ofs > self.tell():
        self.fh.seek(ofs - self.fh.offset, 1)
      else:
        self.fh.rewind()
        self.fh.seek(ofs)
    else:
      self.fh.seek(offset, whence)

  def read(self, size=-1):   # pylint: disable=C6409
    """Read size bytes from file and return them."""
    if self.fh:
      return self.fh.read(size)
    else:
      return ''

  def Open(self, filehandle=None):
    """Open the file as it is described in the PathSpec protobuf."""
    if filehandle:
      filehandle.seek(0)
      self.fh = gzip.GzipFile(fileobj=filehandle, mode='rb')
      self.inode = getattr(filehandle.Stat(), 'ino', 0)
    else:
      self.fh = gzip.GzipFile(filename=self.pathspec.file_path, mode='rb')
      self.inode = os.stat(self.pathspec.file_path).st_ino

    self.name = self.pathspec.file_path
    if filehandle:
      self.display_name = u'%s_uncompressed' % filehandle.name
    else:
      self.display_name = self.name

    # To get the size properly calculated.
    try:
      _ = self.fh.read(4)
    except IOError as e:
      dn = self.display_name
      raise IOError('Not able to open the GZIP file %s -> %s [%s]' % (
          self.name, dn, e))
    self.fh.rewind()
    try:
      self.size = self.fh.size
    except AttributeError:
      self.size = 0


class Bz2File(PlasoFile):
  """Provide a file-like object to a file compressed using BZ2."""
  TYPE = transmission_pb2.PathSpec.BZ2

  def Stat(self):
    """Return a Stats object that contains stats like information."""
    ret = Stats()
    if not self.fh:
      return ret

    ret.ino = self.inode
    ret.os_type = 'BZ2 container'
    return ret

  def readline(self, size=-1):
    """Read a line from the file.

    Args:
      size: Defines the maximum byte count (including the new line trail)
      and if defined may get the function to return an incomplete line.

    Returns:
      A string containing a single line read from the file.
    """
    if self.fh:
      return self.fh.readline(size)
    else:
      return ''

  def Open(self, filehandle=None):
    """Open the file as it is described in the PathSpec protobuf."""
    if filehandle:
      self.inode = getattr(filehandle.Stat(), 'ino', 0)
      try:
        filehandle.seek(0)
      except NotImplementedError:
        pass
      self.fh = bz2.BZ2File(filehandle, 'r')
      self.display_name = u'%s:%s' % (filehandle.name, self.pathspec.file_path)
    else:
      self.display_name = self.pathspec.file_path
      self.fh = bz2.BZ2File(self.pathspec.file_path, 'r')
      self.inode = os.stat(self.pathspec.file_path).st_ino

    self.name = self.pathspec.file_path


class TarFile(PlasoFile):
  """Provide a file-like object to a file stored inside a TAR file."""
  TYPE = transmission_pb2.PathSpec.TAR

  def Stat(self):
    """Return a Stats object that contains stats like information."""
    ret = Stats()
    if not self.fh:
      return ret

    ret.ino = self.inode
    ret.os_type = 'Tar container'
    return ret

  def Open(self, filehandle=None):
    """Open the file as it is described in the PathSpec protobuf."""
    if filehandle:
      ft = tarfile.open(fileobj=filehandle, mode='r')
      self.display_name = u'%s:%s' % (filehandle.name, self.pathspec.file_path)
      self.inode = getattr(filehandle.Stat(), 'ino', 0)
    else:
      self.display_name = u'%s:%s' % (self.pathspec.container_path,
                                      self.pathspec.file_path)
      ft = tarfile.open(self.pathspec.container_path, 'r')
      self.inode = os.stat(self.pathspec.container_path).st_ino

    self.fh = ft.extractfile(self.pathspec.file_path)
    if not self.fh:
      raise IOError(
          '[TAR] File %s empty or unable to open.' % self.pathspec.file_path)
    self.buffer = ''
    self.name = self.pathspec.file_path
    self.size = self.fh.size

  def read(self, size=None):
    """Read size bytes from file and return them."""
    if not self.fh:
      return ''

    if size and len(self.buffer) >= size:
      ret = self.buffer[:size]
      self.buffer = self.buffer[size:]
      return ret

    ret = self.buffer
    self.buffer = ''

    read_size = None
    if size:
      read_size = size - len(ret)

    ret += self.fh.read(read_size)

    # In my testing I've seen the underlying read operation
    # sometimes read in way more than the size here indicates.
    # Slapping an additional check to make sure we return the amount
    # of bytes that we are really asking for.
    if size and len(ret) > size:
      self.buffer = ret[size:]
      ret = ret[:size]

    return ret

  def readline(self, size=-1):
    """Read a line from the file.

    Args:
      size: Defines the maximum byte count (including the new line trail)
      and if defined may get the function to return an incomplete line.

    Returns:
      A string containing a single line read from the file.
    """
    if not self.fh:
      return ''

    if '\n' not in self.buffer:
      self.buffer += self.fh.readline(size)

    # TODO: Make this more resiliant/optimized. For now this
    # code only checks the size in two places, better to always fill
    # the buffer, make sure it is of certain size before moving on.
    if size > 0 and len(self.buffer) > size:
      ret = self.buffer[:size]
      self.buffer = self.buffer[size:]
    else:
      ret = self.buffer
      self.buffer = ''

    result, sep, ret = ret.partition('\n')
    self.buffer = ret + self.buffer

    return result + sep

  def seek(self, offset, whence=0):
    if not self.fh:
      raise RuntimeError('Unable to seek into a file that is not open.')

    if whence == 1:
      if offset > 0 and len(self.buffer) > offset:
        self.buffer = self.buffer[offset:]
      else:
        ofs = offset - len(self.buffer)
        self.buffer = ''
        self.fh.seek(ofs, 1)
    else:
      self.buffer = ''
      self.fh.seek(offset, whence)

  def tell(self):
    if not self.fh:
      return 0

    return self.fh.tell() - len(self.buffer)


class VssFile(TskFile):
  """Class to open up files in Volume Shadow Copies."""

  TYPE = transmission_pb2.PathSpec.VSS

  def _OpenFileSystem(self, path, offset):
    if not self.pathspec.HasField('vss_store_number'):
      raise IOError((u'Unable to open VSS file: {%s} -> No VSS store number '
                     'defined.') % self.name)

    self._fs_obj = FilesystemCache.Open(
        path, offset, self.pathspec.vss_store_number)

    self._fs = self._fs_obj.fs

  def Open(self, filehandle=None):
    super(VssFile, self).Open(filehandle)

    self.display_name = u'%s:vss_store_%d' % (
        self.display_name, self.pathspec.vss_store_number)


class Stats(object):
  """Provide an object for stat results."""

  attributes = None

  def __init__(self):
    self.attributes = {}

  def __setattr__(self, attr, value):
    """Sets the value to either the default or the attribute store."""
    try:
      object.__getattribute__(self, attr)
      object.__setattr__(self, attr, value)
    except AttributeError:
      self.attributes.__setitem__(attr, value)

  def __iter__(self):
    """Return a generator that returns key/value pairs for each attribute."""
    for key, value in sorted(self.attributes.items()):
      yield key, value

  def __getattr__(self, attr):
    """Determine if attribute is set within the event or in a container."""
    try:
      return object.__getattribute__(self, attr)
    except AttributeError:
      pass

    # Check the attribute store.
    try:
      if attr in self.attributes:
        return self.attributes.__getitem__(attr)
    except TypeError as e:
      raise AttributeError('%s', e)

    raise AttributeError('Attribute not defined')


PFILE_HANDLERS = {}
PFILE_TYPES = {}


def InitPFile():
  """Creates a dict object with all PFile handlers."""
  for cl in PlasoFile.classes:
    PFILE_HANDLERS[PlasoFile.classes[cl].TYPE] = PlasoFile.classes[cl]

  for value in transmission_pb2.PathSpec.DESCRIPTOR.enum_types_by_name[
      'FileType'].values:
    PFILE_TYPES[value.number] = value.name


def OpenPFile(spec, fh=None, orig=None):
  """Open up a PlasoFile object.

  The location and how to open the file is described in the PathSpec protobuf
  that includes location and information about which driver to use to open it.

  Each PathSpec can also define a nested PathSpec, if that file is stored within
  another file, or even an embedded one.

  An example PathSpec describing an image file that contains a GZIP compressed
  TAR file, that contains a GZIP compressed syslog file, providing multiple
  level of nested paths.

  type: TSK
  file_path: "/logs/sys.tgz"
  container_path: "test_data/syslog_image.dd"
  image_offset: 0
  image_inode: 12
  nested_pathspec {
    type: GZIP
    file_path: "/logs/sys.tgz"
    nested_pathspec {
      type: TAR
      file_path: "syslog.gz"
      container_path: "/logs/sys.tgz"
      nested_pathspec {
        type: GZIP
        file_path: "syslog.gz"
      }
    }
  }

  Args:
    spec: A PathSpec protobuf that describes the file that needs to be opened.
    fh: A PFile object that is used as base for extracting the needed file out.
    orig: A PathSpec protobuf that describes the root pathspec of the file.

  Returns:
    A PFile object, that is a file like object.

  Raises:
    IOError: If the method is unable to open the file.
  """
  if not PFILE_HANDLERS:
    InitPFile()

  handler_class = PFILE_HANDLERS.get(spec.type,
                                     transmission_pb2.PathSpec.UNSET)
  try:
    handler = handler_class(spec, orig)
  except errors.UnableToOpenFile:
    raise IOError('Unable to open the file: %s using %s' % (
        spec.file_path, PFILE_TYPES[spec.type]))

  try:
    handler.Open(fh)
  except IOError as e:
    raise IOError('[%s] Unable to open the file: %s, error: %s' % (
        handler.__class__.__name__, spec.file_path, e))

  if spec.HasField('nested_pathspec'):
    if orig:
      orig_proto = orig
    else:
      orig_proto = spec
    return OpenPFile(spec.nested_pathspec, handler, orig_proto)
  else:
    logging.debug('Opening file: %s [%s]', handler.name,
                  PFILE_TYPES[spec.type])
    return handler

  raise IOError('Unable to open the file.')


def GetUnicodeString(string):
  """Returns a unicode object."""
  if type(string) != unicode:
    return str(string).decode('utf8', 'ignore')

  return string