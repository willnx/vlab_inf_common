# -*- coding: UTF-8 -*-
"""
Common functions for interacting with Virtual Machines in VMware
"""
import ssl
import time
import random
import textwrap

import ujson
import OpenSSL
from pyVmomi import vim

from vlab_inf_common.vmware import consume_task
from vlab_inf_common.constants import const


def power(the_vm, state, timeout=600):
    """Turn on/off/restart a given virtual machine.

    Turning off and restarting do **not** perform graceful shutdowns; it's like
    pulling the power cable. This method blocks until the VM is in the requested
    power state.

    :Returns: Boolean

    :param the_vm: The pyVmomi Virtual machine object
    :type the_vm: vim.VirtualMachine

    :param state: The power state to put the VM into. Valid values are "on" "off" and "reset"
    :type state: Enum/String

    :param timeout: Optional - How long (in milliseconds) to block waiting on a given power state
    :type timeout: Integer
    """
    valid_states = {'on', 'off', 'restart'}
    if state not in valid_states:
        error = 'state must be one of {}, supplied {}'.format(valid_states, state)
        raise ValueError(error)

    if the_vm.runtime.powerState.lower().replace('powered', '') == state:
        return True
    elif state == 'on':
        task = the_vm.PowerOn()
    elif state == 'off':
        task = the_vm.PowerOff()
    elif state == 'restart':
        task = the_vm.ResetVM_Task()

    try:
        consume_task(task, timeout=timeout)
    except RuntimeError:
        # task failed or timed out
        return False
    return True


def get_info(vcenter, the_vm, username, ensure_ip=False, ensure_timeout=600):
    """Obtain basic information about a virtual machine

    :Returns: Dictionary

    :param vcenter: The vCenter object
    :type vcenter: vlab_inf_common.vmware.vcenter.vCenter

    :param the_vm: The pyVmomi Virtual machine object
    :type the_vm: vim.VirtualMachine

    :param username: The name of the user who owns the VM
    :type username: String

    :param ensure_ip: Block until the VM acquires an IP
    :type ensure_ip: Boolean

    :param ensure_timeout: How long to wait on an IP in seconds
    :type ensure_timeout: Integer
    """
    details = {}
    details['state'] = the_vm.runtime.powerState
    details['console'] = _get_vm_console_url(vcenter, the_vm)
    details['ips'] = _get_vm_ips(the_vm, ensure_ip, ensure_timeout)
    details['networks'] = get_networks(vcenter, the_vm, username)
    details['moid'] = the_vm._moId
    if the_vm.config:
        try:
            meta_data = ujson.loads(the_vm.config.annotation)
        except (ValueError, TypeError):
            # ValueError -> VM created, but notes not updated
            # TypeError  -> VM failed to be created; notes are None
            meta_data = {'component': 'Unknown',
                         'created': 0,
                         'version': "Unknown",
                         'generation': 0,
                         'configured': False
                         }
    else:
        # A VM being deployed has no config
        meta_data = {'component': 'Unknown',
                     'created': 0,
                     'version': "Unknown",
                     'generation': 0,
                     'configured': False
                     }
    details['meta'] = meta_data
    return details


def get_networks(vcenter, the_vm, username):
    """Obtain a list of all networks a VM is connected to.

    :Returns: List

    :param vcenter: An established connection to vCenter
    :type vcenter: vlab_inf_common.vmware.vcenter.vCenter

    :param the_vm: The virtual machine that owns the specific NIC
    :type the_vm: vim.VirtualMachine

    :param username: The name of the user who owns the VM
    :type username: String
    """
    networks = []
    user_networks = {x:y for x,y in vcenter.networks.items() if x.startswith(username)}
    for net_name, net_object in user_networks.items():
        for vm in net_object.vm:
            if vm.name == the_vm.name:
                networks.append(net_name.replace('{}_'.format(username), ''))
    return networks


def set_meta(the_vm, meta_data):
    """Truncate and replace the meta data associated with a given virtual machine.

    :Returns: None

    :Raises: ValueError - when invalid meta data supplied

    :param the_vm: The virtual machine to assign the meta data to
    :type the_vm: vim.VirtualMachine

    :param meta_data: The extra information to associate to the virtual machine
    :type meta_data: Dictionary
    """
    expected = {'component', 'created', 'version', 'generation', 'configured'}
    provided = set(meta_data.keys())
    if not expected == provided:
        error = "Invalid meta data schema. Supplied: {}, Required: {}".format(provided, expected)
        raise ValueError(error)
    spec = vim.vm.ConfigSpec()
    spec_info = ujson.dumps(meta_data)
    spec.annotation = spec_info
    task = the_vm.ReconfigVM_Task(spec)
    consume_task(task)


def _get_vm_ips(the_vm, ensure_ip, ensure_timeout):
    """Obtain all IPs assigned to a supplied virtual machine

    :Returns: List

    :param the_vm: The pyVmomi Virtual machine object
    :type the_vm: vim.VirtualMachine
    """
    ips = []
    for nic in the_vm.guest.net:
        ips += nic.ipAddress

    if ensure_ip and not ips:
        for _ in range(ensure_timeout):
            time.sleep(1)
            for nic in the_vm.guest.net:
                ips += nic.ipAddress
            if ips:
                break
        else:
            error = "Unable to obtain an IP within {} seconds".format(ensure_timeout)
            raise RuntimeError(error)
    # No point is showing the IPv6 link local addrs if a firewall wont forward them
    # https://en.wikipedia.org/wiki/Link-local_address
    ips = [x for x in ips if not (x.startswith('fe80::') and x != '127.0.0.1')]
    return ips


def _get_vm_console_url(vcenter, the_vm):
    """Obtain the HTML5-based console for a supplied virtual machine

    :Returns: (Really long) String

    :param vcenter: The vCenter object
    :type vcenter: vlab_inf_common.vmware.vcenter.vCenter

    :param the_vm: The pyVmomi Virtual machine object
    :type the_vm: vim.VirtualMachine
    """
    fqdn = None
    vcenter_cert = ssl.get_server_certificate((const.INF_VCENTER_SERVER, const.INF_VCENTER_PORT))
    thumbprint = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, vcenter_cert).digest('sha1').decode()
    server_guid = vcenter.content.about.instanceUuid
    session = vcenter.content.sessionManager.AcquireCloneTicket()
    for item in vcenter.content.setting.setting:
        if item.key == 'VirtualCenter.FQDN':
            fqdn = item.value
            break

    url = """\
    https://{0}/ui/webconsole.html?vmId={1}&vmName={2}&serverGuid={3}&
    locale=en_US&host={0}&sessionTicket={4}&thumbprint={5}
    """.format(const.INF_VCENTER_SERVER,
               the_vm._moId,
               the_vm.name,
               server_guid,
               session,
               thumbprint)
    return textwrap.dedent(url).replace('\n', '')


def run_command(vcenter, the_vm, command, user, password, arguments='', init_timeout=600, timeout=600, one_shot=False):
    """Execute a command within a supplied virtual machine

    :Returns: vim.vm.guest.ProcessManager.ProcessInfo

    :param vcenter: The vCenter object
    :type vcenter: vlab_inf_common.vmware.vcenter.vCenter

    :param the_vm: The pyVmomi Virtual machine object
    :type the_vm: vim.VirtualMachine

    :param command: The abolute path to the command you want to execute
    :type command: String

    :param arguments: Optionally supply arguments to your command
    :type arguments: String

    :param user: The username of the account that will execute the command
    :type user: String

    :param password: The password of the given user
    :type password: String

    :param init_timeout: How long to wait for VMware Tools to become available.
                         Handy for running a command on a VM after booting it up.
    :type init_timeout: Integer

    :param timeout: How long to wait for the command to terminate
    :type timeout: Integer

    :param one_shot: Set to True if you do not want to wait on the exit status
    :type one_shot: Boolean
    """
    creds = vim.vm.guest.NamePasswordAuthentication(username=user, password=password)
    process_mgr = vcenter.content.guestOperationsManager.processManager
    program_spec = vim.vm.guest.ProcessManager.ProgramSpec(programPath=command, arguments=arguments)
    for _ in range(init_timeout):
        try:
            pid = process_mgr.StartProgramInGuest(the_vm, creds, program_spec)
        except vim.fault.GuestOperationsUnavailable:
            # VMTools not yet available
            time.sleep(1)
            pass
        else:
            break
    else:
        raise RuntimeError('VMTools not available within {} seconds'.format(init_timeout))

    if one_shot:
        info = vim.vm.guest.ProcessManager.ProcessInfo(pid=pid)
    else:
        info = get_process_info(vcenter, the_vm, user, password, pid)
        for _ in range(timeout):
            if not info.endTime:
                time.sleep(1)
                info = get_process_info(vcenter, the_vm, user, password, pid)
            else:
                break
        else:
            raise RuntimeError('Command {} {} took more than {} seconds'.format(command, arguments, timeout))
    return info


def get_process_info(vcenter, the_vm, user, password, pid):
    """Lookup information about a running process within a virtual machine.

    :Returns: vim.vm.guest.ProcessManager.ProcessInfo

    :param vcenter: The vCenter object
    :type vcenter: vlab_inf_common.vmware.vcenter.vCenter

    :param the_vm: The pyVmomi Virtual machine object
    :type the_vm: vim.VirtualMachine

    :param user: The username of the account to authenticate with inside the VM
    :type user: String

    :param password: The password of the given user
    :type password: String

    :param pid: The process ID to lookup
    :type pid: Integer
    """
    creds = vim.vm.guest.NamePasswordAuthentication(username=user, password=password)
    return vcenter.content.guestOperationsManager.processManager.ListProcessesInGuest(vm=the_vm,
                                                                                      auth=creds,
                                                                                      pids=[pid])[0]


def deploy_from_ova(vcenter, ova, network_map, username, machine_name, logger, power_on=True):
    """Makes the deployment spec and uploads the OVA to create a new Virtual Machine

    :Returns: vim.VirtualMachine

    :param vcenter: The vCenter object
    :type vcenter: vlab_inf_common.vmware.vcenter.vCenter

    :param ova: The Ova object
    :type ova: vlab_inf_common.vmware.ova.Ova

    :param network_map: The mapping of networks defined in the OVA with what's
                        available in vCenter.
    :type network_map: List of vim.OvfManager.NetworkMapping

    :type username: The name of the user deploying a new VM
    :type username: String

    :param machine_name: The unqiue name to give the new VM
    :type machine_name: String

    :param logger: A logging object
    :type logger: logging.Logger

    :param power_on: Set to True to have the VM powered on after deployment. Default True
    :type power_on: Boolean
    """
    if not isinstance(network_map, list):
        raise ValueError('Param network_map must be of type list, found {}'.format(type(network_map)))

    folder = vcenter.get_by_name(name=username, vimtype=vim.Folder)
    resource_pool = vcenter.resource_pools[const.INF_VCENTER_RESORUCE_POOL]
    datastore = vcenter.datastores[random.choice(const.INF_VCENTER_DATASTORE)]
    if isinstance(datastore, vim.StoragePod):
        datastore = random.choice(datastore.childEntity)
    all_hosts = [vcenter.host_systems[x] for x in vcenter.host_systems.keys() if not vcenter.host_systems[x].runtime.inMaintenanceMode]
    host = random.choice(all_hosts)
    spec_params = vim.OvfManager.CreateImportSpecParams(entityName=machine_name,
                                                        diskProvisioning='thin',
                                                        networkMapping=network_map)
    spec = vcenter.ovf_manager.CreateImportSpec(ovfDescriptor=ova.ovf,
                                                resourcePool=resource_pool,
                                                datastore=datastore,
                                                cisp=spec_params)
    lease = _get_lease(resource_pool, spec.importSpec, folder, host)
    logger.debug('Uploading OVA')
    ova.deploy(spec, lease, host.name)
    logger.debug('OVA deployed successfully')
    # Find the new VM so we can turn it on, and return the object to the caller
    for entity in folder.childEntity:
        if entity.name == machine_name:
            the_vm = entity
            break
    else:
        error = 'Unable to find newly created VM by name {}'.format(machine_name)
        raise RuntimeError(error)
    if power_on:
        logger.debug("Powering on {}'s new VM {}".format(username, machine_name))
        power(the_vm, state='on')
    return the_vm


def _get_lease(resource_pool, import_spec, folder, host):
    """Obtain a OVA deploy lease that's ready to be used

    :Returns: vim.Task

    :param resource_pool: The resource pool that new VM will be part of.
    :type resource_pool: vim.ResourcePool

    :param import_spec: The configuration of the new VM
    :type import_spec: vim.ImportSpec

    :param folder: The folder to store the new VM in
    :type folder: vim.Folder

    :param host: The ESXi host to upload the OVA to
    :type host: vim.HostSystem
    """
    lease = resource_pool.ImportVApp(import_spec, folder=folder, host=host)
    for _ in range(30):
        if lease.error:
            error = lease.error.msg
            raise ValueError(error)
        elif lease.state != 'ready':
            time.sleep(1)
        else:
            break
    else:
        error = 'Lease never because usable'
        raise RuntimeError(error)
    return lease


def adjust_ram(the_vm, mb_of_ram):
    """Set the amount of RAM for a VM

    **IMPORTANT**
    Most VMs are required to be powered off in order to adjust RAM.
    Unless you know that your guest OS supports hot-swap RAM, power your VM off
    before changing how much RAM it has.

    :Returns: None

    :param the_vm: The virtual machine to adjust RAM on
    :type the_vm: vim.VirtualMachine

    :param mb_of_ram: The number of MB of RAM/memory to give the virtual machine
    :type mb_of_ram: Integer
    """
    config_spec = vim.vm.ConfigSpec()
    config_spec.memoryMB = mb_of_ram

    consume_task(the_vm.Reconfigure(config_spec))


def change_network(the_vm, network, adapter_label='Network adapter 1'):
    """Update the VM; replace existing network with the supplied network.

    :Returns: None

    :param the_vm: The virtual machine to update
    :type the_vm: vim.VirtualMachine

    :param network: The new network the VM should be connected to
    :type network: vim.Network

    :param adapter_label: The name of the virtual NIC to connect to a new device
    :type adapter_label: String
    """
    devices = [x for x in the_vm.config.hardware.device if x.deviceInfo.label == adapter_label]
    if not devices:
        error = "VM has no network adapter named {}".format(adapter_label)
        raise RuntimeError(error)
    else:
        device = devices[0]

    nicspec = vim.vm.device.VirtualDeviceSpec()
    nicspec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
    nicspec.device = device
    nicspec.device.wakeOnLanEnabled = True
    dvs_port_connection = vim.dvs.PortConnection()
    dvs_port_connection.portgroupKey = network.key
    dvs_port_connection.switchUuid = network.config.distributedVirtualSwitch.uuid
    nicspec.device.backing = vim.vm.device.VirtualEthernetCard.DistributedVirtualPortBackingInfo()
    nicspec.device.backing.port = dvs_port_connection
    nicspec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
    nicspec.device.connectable.startConnected = True
    nicspec.device.connectable.allowGuestControl = True
    nicspec.device.connectable.connected = True
    config_spec = vim.vm.ConfigSpec(deviceChange=[nicspec])
    consume_task(the_vm.ReconfigVM_Task(config_spec))
