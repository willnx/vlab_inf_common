# -*- coding: UTF-8 -*-
"""Unittests for the vlab_inf_common.vmware.tasks module"""
import unittest
from unittest.mock import patch, MagicMock

import vlab_inf_common.vmware.tasks as task_lib

class TestConsumeTask(unittest.TestCase):
    """A set of test cases for the ``consume_task`` function"""

    @patch.object(task_lib, 'time')
    def test_happy_path(self, fake_time):
        """``consume_task`` - Works as expected when there are no issues"""
        fake_task = MagicMock()
        fake_task.info.error = None
        fake_task.info.result = 'woot'

        result = task_lib.consume_task(fake_task, timeout=2)
        expected = 'woot'

        self.assertEqual(result, expected)

    @patch.object(task_lib, 'time')
    def test_timeout(self, fake_time):
        """``consume_task`` raises RuntimeError if the task does not complete within the timeout"""
        fake_task = MagicMock()
        fake_task.info.completeTime = None
        fake_task.info.error = None
        fake_task.info.result = 'woot'

        with self.assertRaises(RuntimeError):
            task_lib.consume_task(fake_task, timeout=2)

    @patch.object(task_lib, 'time')
    def test_error(self, fake_time):
        """``consume_task`` - raises RuntimeError if the task complete with an error"""
        fake_task = MagicMock()
        fake_task.info.error = 'someError'
        fake_task.info.result = 'woot'

        with self.assertRaises(RuntimeError):
            task_lib.consume_task(fake_task, timeout=2)

    @patch.object(task_lib, 'time')
    def test_blocks(self, fake_time):
        """``consume_task`` - Blocks until the task is complete"""
        fake_task = MagicMock()
        fake_task.info.error = None
        fake_task.info.result = 'woot'
        fake_task.info.completeTime.side_effect = [None, 'someTimestamp']

        result = task_lib.consume_task(fake_task, timeout=5)
        expected = 'woot'

        self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main()
