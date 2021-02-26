# -*- coding: UTF-8 -*-
"""
Common functions for interacting with Virtual Machines in VMware
"""
import ssl
import time
import shutil
import random
import os.path
import tarfile
import textwrap
import threading
from io import BytesIO

import ujson
import OpenSSL
import requests
from pyVmomi import vim
from urllib3.exceptions import InsecureRequestWarning

from vlab_inf_common.constants import const
from vlab_inf_common.vmware.tasks import consume_task
from vlab_inf_common.vmware.exceptions import DeployFailure

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)


def power(the_vm, state, timeout=600):
    """Turn on/off/restart a given virtual machine.

    Turning off and restarting do **not** perform graceful shutdowns; it's like
    pulling the power cable. This method blocks until the VM is in the requested
    power state.

    :Returns: Boolean

    :param the_vm: The pyVmomi Virtual machine object
    :type the_vm: vim.VirtualMachine

    :param state: The power state to put the VM into. Valid values are "on" "off" and "restart"
    :type state: Enum/String

    :param timeout: Optional - How long (in milliseconds) to block waiting on a given power state
    :type timeout: Integer
    """
    valid_states = {'on', 'off', 'restart'}
    if state not in valid_states:
        error = 'state must be one of {}, supplied {}'.format(valid_states, state)
        raise ValueError(error)

    vm_power_state = the_vm.runtime.powerState.lower().replace('powered', '')
    if vm_power_state == state:
        return True
    elif (state == 'on') or (vm_power_state == 'off' and state == 'restart'):
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
    if not expected.issubset(provided):
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
    info = None
    creds = vim.vm.guest.NamePasswordAuthentication(username=user, password=password)
    for _ in range(30):
        try:
            info = vcenter.content.guestOperationsManager.processManager.ListProcessesInGuest(vm=the_vm,
                                                                                              auth=creds,
                                                                                              pids=[pid])[0]
        except vim.fault.GuestOperationsUnavailable:
            time.sleep(1)
        else:
            break
    if info is None:
        raise RuntimeError('Timed out trying to lookup info for PID {}'.format(pid))
    return info

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
    timeout = 300
    lease = resource_pool.ImportVApp(import_spec, folder=folder, host=host)
    for _ in range(timeout):
        if lease.error:
            error = lease.error.msg
            raise DeployFailure(error)
        elif lease.state != 'ready':
            time.sleep(1)
        else:
            break
    else:
        error = 'Deploy lease not usable after {} seconds'.format(timeout)
        raise DeployFailure(error)
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


def adjust_cpu(the_vm, cpu_count):
    """Set the number of CPUs for a VM

    **IMPORTANT**
    Make sure your VM is powered off before calling this function, otherwise
    it'll fail.

    :param the_vm: The virtual machine to adjust CPU count on
    :type the_vm: vim.VirtualMachine

    :param cpu_count: The number of CPU cores to allocate to the VM
    :type cpu_count: Integer
    """
    config_spec = vim.vm.ConfigSpec()
    config_spec.numCPUs = cpu_count
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


def config_static_ip(vcenter, the_vm, static_ip, default_gateway, subnet_mask, dns, user, password, logger, os='centos8'):
    os = os.lower()
    if os == 'windows':
        _config_windows_network(vcenter, the_vm, static_ip, default_gateway, subnet_mask, dns, user, password, logger)
    elif os == 'centos8':
        _config_centos8_network(vcenter, the_vm, static_ip, default_gateway, subnet_mask, dns, user, password, logger)
    else:
        raise ValueError('Unsupported OS supplied: {}'.format(os))


def _config_windows_network(vcenter, the_vm, static_ip, default_gateway, netmask, dns, user, password, logger):
    """Set a static IP and DNS server on a Windows VM

    :Returns: None

    :param vcenter: The instantiated connection to vCenter
    :type vcenter: vlab_inf_common.vmware.vCenter

    :param the_vm: The virtual machine to set a static IP on
    :type the_vm: vim.VirtualMachine

    :param static_ip: The IPv4 address to assign to the VM
    :type static_ip: String

    :param default_gateway: The IPv4 address of the network gateway
    :type default_gateway: String

    :param netmask: The subnet mask of the network, i.e. 255.255.255.0
    :type netmask: String

    :param dns: A list of DNS servers to use
    :type dns: List

    :param user: The admin user that can configure the network
    :type user: String

    :param password: The user's password
    :type password: String

    :param logger: An object for logging messages
    :type logger: logging.LoggerAdapter
    """
    command = 'C:/Windows/System32/netsh.exe'
    ip_args = 'interface ipv4 set address name=Ethernet0 static {static_ip} {netmask} {default_gateway}'.format(static_ip=static_ip,
                                                                                                                netmask=netmask,
                                                                                                                default_gateway=default_gateway)
    dns_args = 'interface ip set dns name=Ethernet0 static {}'.format(dns[0])
    dns_args2 = ''
    if len(dns) > 1:
        dns_args2 = 'interface ip set dns name=Ethernet0 static {} index=2'.format(dns[1])
    logger.info('Settings static IP')
    run_command(vcenter, the_vm, command, user=user, password=password, arguments=ip_args)
    logger.info("Setting DNS")
    run_command(vcenter, the_vm, command, user=user, password=password, arguments=dns_args)
    if dns_args2:
        logger.info("Setting 2nd DNS server")
        run_command(vcenter, the_vm, command, user=user, password=password, arguments=dns_args2)


def _config_centos8_network(vcenter, the_vm, static_ip, default_gateway, netmask, dns, user, password, logger):
    """Configure the static network on the CentOS 8 VM

    :Returns: None

    :param vcenter: The instantiated connection to vCenter
    :type vcenter: vlab_inf_common.vmware.vCenter

    :param the_vm: The virtual machine to set a static IP on
    :type the_vm: vim.VirtualMachine

    :param static_ip: The IPv4 address to assign to the VM
    :type static_ip: String

    :param default_gateway: The IPv4 address of the network gateway
    :type default_gateway: String

    :param netmask: The subnet mask of the network, i.e. 255.255.255.0
    :type netmask: String

    :param dns: A list of DNS servers to use.
    :type dns: List

    :param user: The admin user that can configure the network
    :type user: String

    :param password: The user's password
    :type password: String

    :param logger: An object for logging messages
    :type logger: logging.LoggerAdapter
    """
    nic_config_file = '/etc/sysconfig/network-scripts/ifcfg-ens192'
    cmd = '/bin/bash'
    base_args = "-c '/bin/echo {} | /bin/sudo -S {} {}'"
    config = """\
    TYPE=Ethernet
    ONBOOT=yes
    BOOTPROTO=static
    DEFROUTE=yes
    NAME=ens192
    DEVICE=ens192
    IPADDR={}
    GATEWAY={}
    NETMASK={}
    """.format(static_ip, default_gateway, netmask)
    nic_config = '{}{}\n'.format(textwrap.dedent(config), _format_dns(dns))
    _upload_nic_config(vcenter, the_vm, nic_config, os.path.basename(nic_config_file), user, password, logger)
    _run_cmd(vcenter, the_vm, '/bin/mv', '-f /tmp/{} {}'.format(os.path.basename(nic_config_file), nic_config_file), user, password, logger)
    _run_cmd(vcenter, the_vm, '/usr/bin/systemctl', 'restart NetworkManager.service', user, password, logger)
    _run_cmd(vcenter, the_vm, '/usr/bin/nmcli', 'connection down ens192 && /usr/bin/nmcli connection up ens192', user, password, logger)
    _run_cmd(vcenter, the_vm, '/bin/hostnamectl', 'set-hostname {}'.format(the_vm.name), user, password, logger)


def _run_cmd(vcenter, the_vm, cmd, args, user, password, logger, one_shot=False):
    """A wrapper to simplify running commands with sudo power"""
    shell = '/bin/bash'
    the_args = "-c '/bin/echo {} | /bin/sudo -S {} {}'".format(password, cmd, args)
    result = run_command(vcenter,
                         the_vm,
                         shell,
                         user=user,
                         password=password,
                         arguments=the_args,
                         timeout=1800,
                         one_shot=one_shot,
                         init_timeout=1200)
    if result.exitCode:
        logger.error("failed to execute: {} {}".format(shell, the_args))


def _upload_nic_config(vcenter, the_vm, nic_config, config_name, user, password, logger):
    """Upload the NIC config file to the CentOS machine. Works even if the
    machine has no external network configured.

    :Returns: None

    :param vcenter: The instantiated connection to vCenter
    :type vcenter: vlab_inf_common.vmware.vCenter

    :param the_vm: The virtual machine to uplaod the network config to
    :type the_vm: vim.VirtualMachine

    :param nic_config: The network configuration file contents
    :param nic_config: String

    :param config_name: The name of the config file
    :type config_name: String

    :param user: The admin user that can configure the network
    :type user: String

    :param password: The user's password
    :type password: String

    :param logger: An object for logging messages
    :type logger: logging.LoggerAdapter
    """
    nic_config_bytes = nic_config.encode()
    file_size = len(nic_config_bytes)
    logger.debug("Generating creds")
    creds = vim.vm.guest.NamePasswordAuthentication(username=user,
                                                     password=password)
    logger.debug("Creating file attributes object")
    file_attributes = vim.vm.guest.FileManager.FileAttributes()
    logger.debug("Obtaining URL for uploading NIC config to new VM")
    upload_path = '/tmp/{}'.format(config_name)
    logger.info('Uploading NIC config: %s', upload_path)
    logger.debug('Uploading %s bytes', file_size)
    url = _get_upload_url(vcenter=vcenter,
                          the_vm=the_vm,
                          creds=creds,
                          upload_path=upload_path,
                          file_attributes=file_attributes,
                          file_size=file_size)
    logger.info('Uploading to URL %s', url)
    resp = requests.put(url, data=BytesIO(nic_config_bytes), verify=False)
    resp.raise_for_status()


def _format_dns(dns):
    """Create the DNS section of the NIC config file.

    :Returns: String

    :param dns: A list of DNS servers to use.
    :type dns: List
    """
    tmp = []
    for idx, dns_server in enumerate(dns):
        server_num = idx + 1
        dns_config = 'DNS{}={}'.format(server_num, dns_server)
        tmp.append(dns_config)
    return '\n'.join(tmp)


def _get_upload_url(vcenter, the_vm, creds, upload_path, file_size, file_attributes, overwrite=True):
    """Mostly to deal with race between the VM power on, and all of VMwareTools being ready.

    :Returns: String

    :param vcenter: The instantiated connection to vCenter
    :type vcenter: vlab_inf_common.vmware.vCenter

    :param the_vm: The virtual machine to upload a file to
    :type the_vm: vim.VirtualMachine

    :param creds: The username & password to use when logging into the new VM
    :type creds: vim.vm.guest.NamePasswordAuthentication

    :param file_attributes: BS that pyVmomi requires...
    :type file_attributes: vim.vm.guest.FileManager.FileAttributes

    :param file_size: How many bytes are going to be uploaded
    :type file_size: Integer

    :param overwrite: If the file already exists, write over the existing content.
    :type overwrite: Boolean
    """
    # The VM just booted, this service can take some time to be ready
    for retry_sleep in range(10):
        try:
            url = vcenter.content.guestOperationsManager.fileManager.InitiateFileTransferToGuest(vm=the_vm,
                                                                                                 auth=creds,
                                                                                                 guestFilePath=upload_path,
                                                                                                 fileAttributes=file_attributes,
                                                                                                 fileSize=file_size,
                                                                                                 overwrite=overwrite)
        except vim.fault.GuestOperationsUnavailable:
            time.sleep(retry_sleep)
        else:
            return url
    else:
        error = 'Unable to file to VM. Timed out waiting on GuestOperations to become available.'
        raise ValueError(error)


def download_vmdk(save_location, http_cookies, device, log):
    """Copy the VMDK of a virtual machine to the local filesystem.

    The returned list will be either empty (falsy), or contain an OVF object for
    the VMDK. Because the caller must construct a list of OVF objects for *all*
    devices in a VM, just extend the list in your code with what this function
    returns.

    :Returns: List

    :param save_location: The directory to save the VMDK file to.
    :type save_location: String

    :param http_cookies: The vCenter SOAP auth cookie(s) to use.
    :type http_cookies: Dictionary

    :param device: A component of the virtual machine to download.
    :type device: vim.HttpNfcLease.DeviceUrl

    :param log: An object for writing debug/progress messages.
    :type log: logging.Logger
    """
    vmdk_obj = []
    if not (device.disk and device.targetId):
        log.error("Device is not a VMDK: %s", device.url)
    else:
        vmdk_file = os.path.join(save_location, device.targetId)
        with open(vmdk_file, 'wb') as the_file:
            resp = requests.get(device.url,
                                stream=True,
                                headers={'Accept': 'application/x-vnd.vmware-streamVmdk'},
                                cookies=http_cookies,
                                verify=False)
            resp.raise_for_status()
            bytes_written = 0
            for block in resp.iter_content(chunk_size=20480):
                if block:
                    # filter out keep-alive chunks
                    the_file.write(block)
                    bytes_written += len(block)
        # Create the OVF object; needed to create the correct XML for the whole machine
        ovf_file = vim.OvfManager.OvfFile()
        ovf_file.deviceId = device.key
        ovf_file.path = device.targetId
        ovf_file.size = bytes_written
        vmdk_obj.append(ovf_file)
    return vmdk_obj


def get_vm_ovf_xml(vm, device_ovfs, vcenter):
    """Obtain the XML that defines a virtual machine's OVF.

    :Returns: String (xml)

    :param vm: The virtual machine object to obtain the OVF XML for.
    :type vm: vim.VirtualMachine

    :param device_ovfs: The device-specific OVFs of the virtual machine (vm).
    :type device_ovfs: List

    :param vcenter: A valid connection to a vCenter server.
    :type vcenter: vlab_inf_common.vmware.vCenter
    """
    ovf_params = vim.OvfManager.CreateDescriptorParams()
    ovf_params.name = vm.name
    ovf_params.ovfFiles = device_ovfs
    vm_ovf = vcenter.content.ovfManager.CreateDescriptor(obj=vm, cdp=ovf_params)
    if vm_ovf.error:
        raise vm_ovf.error[0].fault
    return vm_ovf.ovfDescriptor


class ProgressChimer(threading.Thread):
    """Keeps the lease alive while downloading a VMDK from vSphere.

    Using in a ``with`` statement ensures the lease is closed, and makes your code
    cleaner!

    :param lease: Required to export a VM to an OVA.
    :type lease: vim.HttpNfcLease

    :param log: An object for writing debug/progress messages.
    :type log: logging.Logger

    :param update_interval: How often renew/update the lease, in seconds.
    :type update_interval: Integer
    """
    def __init__(self, lease, log, update_interval=10):
        super().__init__()
        self._lease = lease
        self._keep_running = True
        self._update_interval = update_interval
        self.start()

    def __enter__(self):
        return self

    def __exit__(self, exce_type, exec_value, exce_traceback):
        self.complete()

    def complete(self):
        self._lease.HttpNfcLeaseProgress(100)
        self._lease.HttpNfcLeaseComplete()
        self._keep_running = False
        self.join()

    def run(self):
        while self._keep_running:
            self._lease.HttpNfcLeaseProgress(50)
            time.sleep(self._update_interval)


def _block_on_lease(lease):
    """Blocks execution until the lease is usable or fails

    :Returns: None

    :param lease: Required to export a VM to an OVA.
    :type lease: vim.HttpNfcLease
    """
    # this amounts to waiting upwards of 990 seconds, with linear backoff
    for i in range(45):
        if lease.state == vim.HttpNfcLease.State.ready:
            break
        elif lease.state == vim.HttpNfcLease.State.error:
            raise RuntimeError("VM Export lease error: {}".format(lease.state.error))
        else:
            time.sleep(i)
    else:
        raise RuntimeError("Lease never became ready")


def make_ova(vcenter, the_vm, template_dir, log, ova_name=''):
    """Export a virtual machine into an OVA. The returned string is the location
    of the new OVA file.

    :Returns: String

    :param vcenter: The instantiated connection to vCenter
    :type vcenter: vlab_inf_common.vmware.vCenter

    :param the_vm: The name of the VM
    :type the_vm: String

    :param template_dir: The folder to save the new OVA to.
    :type template_dir: String

    :param log: A message for writing progress/debug messages.
    :type log: logging.Logger

    :param ova_name: Optionally define the name for the OVA. Defaults to the name of the VM.
    :type ova_name: String
    """
    ova_location = ''
    power(the_vm, 'off')
    lease = the_vm.ExportVm()
    _block_on_lease(lease)
    with ProgressChimer(lease, log):
        save_location = os.path.join(template_dir, the_vm.name)
        os.makedirs(save_location, exist_ok=True)
        device_ovfs = []
        for device in lease.info.deviceUrl:
            device_ovf = download_vmdk(save_location, vcenter.cookie(), device, log)
            device_ovfs.extend(device_ovf)
    vm_ovf_xml = get_vm_ovf_xml(the_vm, device_ovfs, vcenter)
    ovf_xml_file = os.path.join(save_location, '{}.ovf'.format(the_vm.name))
    with open(ovf_xml_file, 'w') as the_file:
        the_file.write(vm_ovf_xml)
    # Convert to OVA
    if not ova_name:
        ova_name = '{}.ova'.format(the_vm.name)
    elif not ova_name.endswith('.ova'):
        ova_name = '{}.ova'.format(ova_name)
    ova_path = os.path.join(save_location, ova_name)
    ova = tarfile.open(ova_path, mode='w')
    for ova_file in os.listdir(save_location):
        ova_file_path = os.path.join(save_location, ova_file)
        ova.add(ova_file_path, arcname=ova_file)
    ova.close()
    # Move the OVA from the VM specific subdirectory into the main template directory
    ova_location = os.path.join(template_dir, ova_name)
    os.rename(ova_path, ova_location)
    shutil.rmtree(save_location)
    return ova_location


def add_vmdk(the_vm, disk_size):
    """Add a new VMDK to an existing Virtual Machine.

    :Returns: None

    :Rasies: RuntimeError

    :param the_vm: The pyVmomi Virtual machine object
    :type the_vm: vim.VirtualMachine

    :param disk_size: The number of GB to make the disk
    :type disk_size: Integer
    """
    spec = vim.vm.ConfigSpec()
    unit_number = 0
    for dev in the_vm.config.hardware.device:
        if hasattr(dev.backing, 'fileName'):
            unit_number = int(dev.unitNumber) + 1
            # unitNumber 7 is reserved for the SCSI controller
            if unit_number == 7:
                unit_number += 1
            if unit_number >= 16:
                raise RuntimeError('VMs cannot have more than 16 VMDKs')
    if unit_number == 0:
        raise RuntimeError('Unable to find any VMDKs for VM')

    dev_changes = []
    disk_spec = vim.vm.device.VirtualDeviceSpec()
    disk_spec.fileOperation = "create"
    disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
    disk_spec.device = vim.vm.device.VirtualDisk()
    disk_spec.device.backing = vim.vm.device.VirtualDisk.FlatVer2BackingInfo()
    disk_spec.device.backing.thinProvisioned = True
    disk_spec.device.backing.diskMode = 'persistent'
    disk_spec.device.unitNumber = unit_number
    disk_spec.device.capacityInKB = int(disk_size) * 1024 * 1024
    disk_spec.device.controllerKey = 1000
    dev_changes.append(disk_spec)
    spec.deviceChange = dev_changes
    consume_task(the_vm.ReconfigVM_Task(spec=spec))


def configure_network(the_vm, ip_config):
    """Set a static IP and related network settings for a Linux VM with VMware Tools installed.

    The ``ip_config`` dictionary MUST have the following keys:
        - static-ip
        - netmask
        - default-gateway
        - dns
        - domain

    :Returns: None

    :param the_vm: The pyVmomi Virtual machine object
    :type the_vm: vim.VirtualMachine

    :param ip_config: The dictionary containing the static network information.
    :type ip_config: Dictionary

    """
    # Boilerplate...
    adaptermap = vim.vm.customization.AdapterMapping()
    globalip = vim.vm.customization.GlobalIPSettings()
    adaptermap.adapter = vim.vm.customization.IPSettings()
    # Configure IP & DNS
    adaptermap.adapter.ip = vim.vm.customization.FixedIp()
    adaptermap.adapter.ip.ipAddress = ip_config['static-ip']
    adaptermap.adapter.subnetMask = ip_config['netmask']
    adaptermap.adapter.gateway = ip_config['default-gateway']
    globalip.dnsServerList = ip_config['dns']
    adaptermap.adapter.dnsDomain = ip_config['domain']
    ident = vim.vm.customization.LinuxPrep()
    ident.domain = ip_config['domain']
    ident.hostName = vim.vm.customization.FixedName()
    ident.hostName.name = the_vm.name
    # Create the configuration spec
    spec = vim.vm.customization.Specification()
    spec.nicSettingMap = [adaptermap]
    spec.globalIPSettings = globalip
    spec.identity = ident
    task = the_vm.Customize(spec=spec)
    consume_task(task)


def block_on_boot(the_vm):
    """Wait until VMware Tools is ready on a machine.

    :Returns: None

    :param the_vm: The pyVmomi Virtual machine object
    :type the_vm: vim.VirtualMachine
    """
    ready = the_vm.guest.toolsStatus == vim.vm.GuestInfo.ToolsStatus.toolsOk
    while not ready:
        time.sleep(1)
        ready = the_vm.guest.toolsStatus == vim.vm.GuestInfo.ToolsStatus.toolsOk
    # Fun fact - it's still booting. If we don't let it fully boot, then the
    # for whatever reason the network changes will be tossed out.
    # So, let's just do a dumb long sleep and hope :(
    time.sleep(300)
