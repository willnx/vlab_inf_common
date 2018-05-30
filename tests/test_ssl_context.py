# -*- coding: UTF-8 -*-
"""
A suite of tests for the ``ssl_context`` module
"""
import ssl
import unittest
from unittest.mock import patch

from vlab_inf_common import ssl_context


class TestGetContext(unittest.TestCase):
    """Test cases for the ``get_context`` function"""

    def test_verify_false(self):
        """ssl_context - ``get_context`` wont enforce TLS cert verification when VERIFY is False"""
        context = ssl_context.get_context()

        self.assertEqual(context.verify_mode, ssl.CERT_NONE)

    @patch.object(ssl_context, 'const')
    def test_verify_true(self, fake_const):
        """ssl_context - ``get_context`` returns a default context when VERIFY True"""
        context = ssl_context.get_context()
        expected = ssl.create_default_context()

        self.assertEqual(context.verify_mode, expected.verify_mode)
        self.assertEqual(context.protocol, expected.protocol)


if __name__ == '__main__':
    unittest.main()
