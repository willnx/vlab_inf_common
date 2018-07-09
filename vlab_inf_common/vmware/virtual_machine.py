# -*- coding: UTF-8 -*-
"""
Common functions for interacting with Virtual Machines in VMware
"""
import ssl
import time
import textwrap

import OpenSSL

from vlab_inf_common.constants import const


def power(virtual_machine, state, timeout=600):
    """Turn on/off/restart a given virtual machine.

    Turning off and restarting do **not** perform graceful shutdowns; it's like
    pulling the power cable. This method blocks until the VM is in the requested
    power state.

    :Returns: Boolean

    :param virtual_machine: The pyVmomi Virtual machine object
    :type virtual_machine: vim.VirtualMachine

    :param state: The power state to put the VM into. Valid values are "on" "off" and "reset"
    :type state: Enum/String

    :param timeout: Optional - How long (in milliseconds) to block waiting on a given power state
    :type timeout: Integer
    """
    valid_states = {'on', 'off', 'restart'}
    if state not in valid_states:
        error = 'state must be one of {}, supplied {}'.format(valid_states, state)
        raise ValueError(error)

    if virtual_machine.runtime.powerState.lower() == state:
        return True
    elif state == 'on':
        task = virtual_machine.PowerOn()
    elif state == 'off':
        task = virtual_machine.PowerOff()
    elif state == 'restart':
        task = virtual_machine.ResetVM()

    for _ in range(timeout):
        if task.info.completeTime:
            # Trying to turn on/off a VM that's already in the requested state
            # yields a completed task. Who really cares if it was already on/off?
            break
        else:
            time.sleep(0.1)
    else:
        return False
    return True


def get_info(vcenter, virtual_machine):
    """Obtain basic information about a virtual machine

    :Returns: Dictionary

    :param vcenter: The vCenter object
    :type vcenter: vlab_inf_common.vmware.vcenter.vCenter

    :param virtual_machine: The pyVmomi Virtual machine object
    :type virtual_machine: vim.VirtualMachine
    """
    info = {}
    info['state'] = virtual_machine.runtime.powerState
    info['console'] = _get_vm_console_url(vcenter, virtual_machine)
    info['ips'] = _get_vm_ips(virtual_machine)
    return info


def _get_vm_ips(virtual_machine):
    """Obtain all IPs assigned to a supplied virtual machine

    :Returns: List

    :param virtual_machine: The pyVmomi Virtual machine object
    :type virtual_machine: vim.VirtualMachine
    """
    ips = []
    for nic in virtual_machine.guest.net:
        ips += nic.ipAddress
    return ips


def _get_vm_console_url(vcenter, virtual_machine):
    """Obtain the HTML5-based console for a supplied virtual machine

    :Returns: (Really long) String

    :param vcenter: The vCenter object
    :type vcenter: vlab_inf_common.vmware.vcenter.vCenter

    :param virtual_machine: The pyVmomi Virtual machine object
    :type virtual_machine: vim.VirtualMachine
    """
    fqdn = None
    vcenter_cert = ssl.get_server_certificate((const.INF_VCENTER_SERVER, const.INF_VCENTER_PORT))
    thumbprint = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, vcenter_cert).digest('sha1')
    server_guid = vcenter.content.about.instanceUuid
    session = vcenter.content.sessionManager.AcquireCloneTicket()
    for item in vcenter.content.setting.setting:
        if item.key == 'VirtualCenter.FQDN':
            fqdn = item.value
            break

    url = """\
    https://{0}:{1}/vsphere-client/webconsole.html?vmId={2}&vmName={3}&serverGuid={4}&
    locale=en_US&host={0}:{5}&sessionTicket={6}&thumbprint={7}
    """.format(const.INF_VCENTER_SERVER,
               const.INF_VCENTER_CONSOLE_PORT,
               virtual_machine._moId,
               virtual_machine.name,
               server_guid,
               const.INF_VCENTER_PORT,
               session,
               thumbprint)
    return textwrap.dedent(url).replace('\n', '')
