# -*- encoding: UTF-8 -*-
import ssl

from vlab_inf_common.constants import const

def get_context():
    if const.INF_VCENTER_VERIFY_CERT is False:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS)
        context.verify_mode = ssl.CERT_NONE
    else:
        context = ssl.create_default_context()
    return context
