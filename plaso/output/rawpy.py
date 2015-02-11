# -*- coding: utf-8 -*-

from plaso.output import interface
from plaso.output import manager


class NativePythonOutputFormatter(interface.FileLogOutputFormatter):
  """Prints out a "raw" interpretation of the EventObject."""

  # TODO: Revisit the name of this class, perhaps rename it to
  # something more closely similar to what it is doing now, as in
  # "native" or something else.
  NAME = u'rawpy'
  DESCRIPTION = u'Prints out a "raw" interpretation of the EventObject.'

  def EventBody(self, event_object):
    """Prints out to a filehandle string representation of an EventObject.

    Each EventObject contains both attributes that are considered "reserved"
    and others that aren't. The 'raw' representation of the object makes a
    distinction between these two types as well as extracting the format
    strings from the object.

    Args:
      event_object: The EventObject.
    """
    # TODO: Move the unicode cast into the event object itself, expose
    # a ToString function or something similar that will send back the
    # unicode string.
    self.filehandle.WriteLine(unicode(event_object))


manager.OutputManager.RegisterOutput(NativePythonOutputFormatter)
