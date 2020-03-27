# -*- coding: UTF-8 -*-
"""A suite of unit tests for the ``input_validators.py`` module"""
import unittest
import ipaddress

from vlab_inf_common import input_validators


class TestNetworkConfigOk(unittest.TestCase):
    """A suite of test cases for the ``network_config_ok`` function"""
    def test_good_config(self):
        """``network_config_ok`` returns a zero-length string when the config is good"""
        error = input_validators.network_config_ok(ip='192.168.1.2',
                                                   gateway='192.168.1.1',
                                                   netmask='255.255.255.0')
        expected = ''

        self.assertEqual(error, expected)

    def test_bad_config(self):
        """``network_config_ok`` returns an string when the config is bad"""
        error = input_validators.network_config_ok(ip='10.7.1.2',
                                                   gateway='192.168.1.1',
                                                   netmask='255.255.255.0')
        expected = 'Static IP 10.7.1.2 is not part of network 192.168.1.0/24. Adjust your netmask and/or default gateway.'

        self.assertEqual(error, expected)

    def test_bad_network(self):
        """``network_config_ok`` returns an string when the supplied gateway/subnet doesn't make sense"""
        error = input_validators.network_config_ok(ip='10.7.1.2',
                                                   gateway='192.168.1.1',
                                                   netmask='9.9.9.0')
        expected = 'Default gateway 192.168.1.1 not part of subnet 9.9.9.0'

        self.assertEqual(error, expected)


class TestToNetwork(unittest.TestCase):
    """A suite of test cases for the ``_to_network`` function"""
    def test_return_type(self):
        """``_to_network`` returns an IPv4Network object"""
        gateway = '192.168.1.1'
        netmask = '255.255.255.0'
        cidr = '192.168.1.0/24'

        network = input_validators._to_network(gateway, netmask)
        expected = ipaddress.IPv4Network(cidr)

        self.assertEqual(network, expected)


if __name__ == '__main__':
    unittest.main()
