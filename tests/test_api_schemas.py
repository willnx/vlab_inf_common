# -*- coding: UTF-8 -*-
"""A suite of unit tests for the API schemas"""
import unittest

from jsonschema import Draft4Validator, validate, ValidationError

from vlab_inf_common.views import task_view


class TestTaskViewSchema(unittest.TestCase):
    """A set of test cases for the TaskView schemas"""

    def test_task_get_schema(self):
        """The scheam defined for GET on /task is valid"""
        try:
            Draft4Validator.check_schema(task_view.TaskView.TASK_ARGS)
            schema_valid = True
        except RuntimeError:
            schema_valid = False

        self.assertTrue(schema_valid)

    def test_network_put_schema(self):
        """The schema defined for PUT on /network is valid"""
        try:
            Draft4Validator.check_schema(task_view.TaskView.NETWORK_SCHEMA)
            schema_valid = True
        except RuntimeError:
            schema_valid = False

        self.assertTrue(schema_valid)


if __name__ == '__main__':
    unittest.main()
