#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Tests for the Windows recycler parsers."""

import unittest

from plaso.formatters import recycler as _  # pylint: disable=unused-import
from plaso.lib import eventdata
from plaso.lib import timelib
from plaso.parsers import recycler
from plaso.parsers import test_lib


class WinRecycleBinParserTest(test_lib.ParserTestCase):
  """Tests for the Windows Recycle Bin parser."""

  def setUp(self):
    """Sets up the needed objects used throughout the test."""
    self._parser = recycler.WinRecycleBinParser()

  def testParse(self):
    """Tests the Parse function."""
    test_file = self._GetTestFilePath([u'$II3DF3L.zip'])
    event_queue_consumer = self._ParseFile(self._parser, test_file)
    event_objects = self._GetEventObjectsFromQueue(event_queue_consumer)

    self.assertEqual(len(event_objects), 1)

    event_object = event_objects[0]

    self.assertEqual(event_object.orig_filename, (
        u'C:\\Users\\nfury\\Documents\\Alloy Research\\StarFury.zip'))

    expected_timestamp = timelib.Timestamp.CopyFromString(
        u'2012-03-12 20:49:58.633')
    self.assertEqual(event_object.timestamp, expected_timestamp)
    self.assertEqual(event_object.file_size, 724919)

    expected_msg = (
        u'C:\\Users\\nfury\\Documents\\Alloy Research\\StarFury.zip '
        u'(from drive: UNKNOWN)')
    expected_msg_short = (
        u'Deleted file: C:\\Users\\nfury\\Documents\\Alloy Research\\'
        u'StarFury.zip')

    self._TestGetMessageStrings(event_object, expected_msg, expected_msg_short)


class WinRecyclerInfo2ParserTest(test_lib.ParserTestCase):
  """Tests for the Windows Recycler INFO2 parser."""

  def setUp(self):
    """Sets up the needed objects used throughout the test."""
    self._parser = recycler.WinRecyclerInfo2Parser()

  def testParse(self):
    """Reads an INFO2 file and run a few tests."""
    test_file = self._GetTestFilePath([u'INFO2'])
    event_queue_consumer = self._ParseFile(self._parser, test_file)
    event_objects = self._GetEventObjectsFromQueue(event_queue_consumer)

    self.assertEqual(len(event_objects), 4)

    event_object = event_objects[0]

    expected_timestamp = timelib.Timestamp.CopyFromString(
        u'2004-08-25 16:18:25.237')
    self.assertEqual(event_object.timestamp, expected_timestamp)
    self.assertEqual(event_object.timestamp_desc,
                      eventdata.EventTimestamp.DELETED_TIME)

    self.assertEqual(event_object.index, 1)
    self.assertEqual(event_object.orig_filename, (
        u'C:\\Documents and Settings\\Mr. Evil\\Desktop\\lalsetup250.exe'))

    event_object = event_objects[1]

    expected_msg = (
        u'DC2 -> C:\\Documents and Settings\\Mr. Evil\\Desktop'
        u'\\netstumblerinstaller_0_4_0.exe (from drive: C)')
    expected_msg_short = (
        u'Deleted file: C:\\Documents and Settings\\Mr. Evil\\Desktop'
        u'\\netstumblerinstaller...')

    self._TestGetMessageStrings(event_object, expected_msg, expected_msg_short)

    event_object = event_objects[2]

    self._TestGetSourceStrings(event_object, u'Recycle Bin', u'RECBIN')


if __name__ == '__main__':
  unittest.main()
