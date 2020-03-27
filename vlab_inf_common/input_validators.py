# -*- coding: UTF-8 -*-
"""A library for validating user input to the API"""
import ipaddress


def network_config_ok(ip, gateway, netmask):
    """Validate that the supplied IPv4 network config is valid.

    The return value is an error string. When the string has a length of zero,
    that indicates zero errors (i.e. the config is valid).

    :Returns: String

    :param ip: The IP to validate as part of a network config
    :type ip: String

    :param gateway: The default gateway of the subnet
    :type gateway: String

    :param netmask: The subnet mask of the network, i.e. 255.255.255.0
    :type netmask: String
    """
    error = ''
    # default gateway must within supplied subnet, so lets assume that is the network
    try:
        network = _to_network(gateway, netmask)
    except Exception:
        error = 'Default gateway {} not part of subnet {}'.format(gateway, netmask)
    else:
        if not ipaddress.IPv4Address(ip) in list(network):
            error = 'Static IP {} is not part of network {}. Adjust your netmask and/or default gateway.'.format(ip, network)
    return error


def _to_network(gateway, netmask):
    """Convert an IP and subnet mask into CIDR format

    :Returns: ipaddress.IPv4Network

    :param gateway: The IPv4 address of the default gateway
    :type gateway: String

    :param netmask: The subnet mask of the network
    :type netmask: String
    """
    ipaddr = gateway.split('.')
    mask = netmask.split('.')
    # to calculate network start do a bitwise AND of the octets between netmask and ip
    net_start = '.'.join([str(int(ipaddr[x]) & int(mask[x])) for x in range(4)])
    bit_count = sum([bin(int(x)).count("1") for x in netmask.split('.')])
    cidr = '{}/{}'.format(net_start, bit_count)
    return ipaddress.IPv4Network(cidr)
