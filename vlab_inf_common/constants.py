# -*- coding: UTF-8 -*-
"""
Constant values that should not change durning runtime, and are common across
different vLab infrastructure services.
"""
from os import environ
from collections import namedtuple, OrderedDict


DEFINED = OrderedDict([
            ('VLAB_URL', environ.get('VLAB_URL', 'https://localhost')),
            ('INF_VCENTER_SERVER', environ.get('INF_VCENTER_SERVER', 'localhost')),
            ('INF_VCENTER_PORT', int(environ.get('INFO_VCENTER_PORT', 443))),
            ('INF_VCENTER_CONSOLE_PORT', int(environ.get('INF_VCENTER_CONSOLE_PORT', 9443))),
            ('INF_VCENTER_USER', environ.get('INF_VCENTER_USER', 'tester')),
            ('INF_VCENTER_PASSWORD', environ.get('INF_VCENTER_PASSWORD', 'a')),
            ('INF_VCENTER_TOP_LVL_DIR', environ.get('INF_VCENTER_TOP_LVL_DIR', '/')),
            ('INF_VCENTER_DATASTORE', environ.get('INF_VCENTER_DATASTORE', 'VM-Storage').split(',')),
            ('INF_VCENTER_RESORUCE_POOL', environ.get('INF_VCENTER_RESORUCE_POOL', 'Resources')),
            ('INF_LOG_LEVEL', environ.get('INF_LOG_LEVEL', 'INFO')),
            ('INF_VCENTER_TEMPLATES_DIR', environ.get('INF_VCENTER_TEMPLATES_DIR', 'vlab/templates')),
            ('INF_VCENTER_OVA_HOME', environ.get('INF_VCENTER_OVA_HOME', 'http://localhost/ovas')),
            ('INF_VCENTER_VERIFY_CERT', environ.get('INF_VCENTER_VERIFY_CERT', False)),
            ('VLAB_VERIFY_TOKEN', environ.get('VLAB_VERIFY_TOKEN', False)),
          ])

Constants = namedtuple('Constants', list(DEFINED.keys()))

# The '*' expands the list, just liked passing a function *args
const = Constants(*list(DEFINED.values()))
