# -*- coding: UTF-8 -*-
"""A unit tests for the constants.py module"""
import unittest

from vlab_inf_common.constants import const


class TestConstants(unittest.TestCase):
    """A suite of test cases for the constants.py module"""

    def test_expected_const(self):
        """``const`` has the expected constants defined"""
        found = [x for x in dir(const) if x.isupper()]
        expected = ['INF_LOG_LEVEL', 'INF_VCENTER_CONSOLE_PORT', 'INF_VCENTER_DATASTORE', 'INF_VCENTER_OVA_HOME', 'INF_VCENTER_PASSWORD', 'INF_VCENTER_PORT', 'INF_VCENTER_RESORUCE_POOL', 'INF_VCENTER_SERVER', 'INF_VCENTER_TEMPLATES_DIR', 'INF_VCENTER_TOP_LVL_DIR', 'INF_VCENTER_USER', 'INF_VCENTER_VERIFY_CERT', 'VLAB_URL']

        self.assertEqual(set(found), set(expected))

    def test_datastore_type(self):
        """``const.INF_VCENTER_DATASTORE`` is a list of usable datastores"""
        self.assertTrue(isinstance(const.INF_VCENTER_DATASTORE, list))


if __name__ == '__main__':
    unittest.main()
