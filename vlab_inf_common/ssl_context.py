# -*- encoding: UTF-8 -*-
import ssl

from vlab_inf_common.constants import const

def get_context():
    context = ssl.create_default_context()
    if const.INF_VCENTER_VERIFY_CERT is False:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return context
