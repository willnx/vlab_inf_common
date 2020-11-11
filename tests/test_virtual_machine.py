# -*- coding: UTF-8 -*-
"""
A unit tests for the virtual_machine functions
"""
import json

import unittest
from unittest.mock import MagicMock, PropertyMock, patch

from pyVmomi import vim

from vlab_inf_common.vmware import virtual_machine
from vlab_inf_common.vmware.exceptions import DeployFailure


class TestVirtualMachine(unittest.TestCase):
    """A set of test cases for ``virtual_machine``"""

    @patch.object(virtual_machine.OpenSSL.crypto, 'load_certificate')
    @patch.object(virtual_machine.ssl, 'get_server_certificate')
    def test_get_vm_console_url(self, fake_get_server_certificate, fake_load_certificate):
        """``virtual_machine`` - _get_vm_console_url returns the expected string"""
        fake_load_certificate.return_value.digest.return_value = b'test-thumbprint'
        item = MagicMock()
        item.key = 'VirtualCenter.FQDN'
        item.value = 'my.test.fqdn'
        vcenter = MagicMock()
        vcenter.content.about.instanceUuid = 'Test-UUID'
        vcenter.content.sessionManager.AcquireCloneTicket.return_value = 'test-session'
        vcenter.content.setting.setting = [item]
        vm = MagicMock()
        vm._moId = 'test-vm-id'
        vm.name = 'test-vm-name'

        console_url = virtual_machine._get_vm_console_url(vcenter=vcenter, the_vm=vm)
        expected_url = 'https://localhost/ui/webconsole.html?vmId=test-vm-id&vmName=test-vm-name&serverGuid=Test-UUID&locale=en_US&host=localhost&sessionTicket=test-session&thumbprint=test-thumbprint'

        self.assertEqual(console_url, expected_url)

    def test_get_vm_ips(self):
        """``virtual_machine`` - _get_vm_ips iterates over the NICs and returns a list of all IPs"""
        nic = MagicMock()
        nic.ipAddress = ['192.168.1.1']
        vm = MagicMock()
        vm.guest.net = [nic]

        ips = virtual_machine._get_vm_ips(vm, ensure_ip=False, ensure_timeout=300)
        expected_ips = ['192.168.1.1']

        self.assertEqual(ips, expected_ips)

    def test__get_vm_ips_ipv6(self):
        """``virtual_machine`` - _get_vm_ips does not return IPv6 Link Local IPs"""
        nic = MagicMock()
        nic.ipAddress = ['192.168.1.1', 'fe80::dead:beef']
        vm = MagicMock()
        vm.guest.net = [nic]

        ips = virtual_machine._get_vm_ips(vm, ensure_ip=False, ensure_timeout=300)
        expected_ips = ['192.168.1.1']

        self.assertEqual(ips, expected_ips)

    @patch.object(virtual_machine.time, 'sleep')
    def test_vm_ips_runtime_error(self, fake_sleep):
        """``virtual_machine`` - _get_vm_ips raises RuntimeError if ensure_timeout is exceeded"""
        nic = MagicMock()
        nic.ipAddress = []
        vm = MagicMock()
        vm.guest.net = []

        with self.assertRaises(RuntimeError):
            virtual_machine._get_vm_ips(vm, ensure_ip=True, ensure_timeout=5)

    @patch.object(virtual_machine, 'get_networks')
    @patch.object(virtual_machine, '_get_vm_ips')
    @patch.object(virtual_machine, '_get_vm_console_url')
    def test_get_info(self, fake_get_vm_console_url, fake_get_vm_ips, fake_get_networks):
        """``virtual_machine`` - get_info returns the expected data"""
        fake_get_vm_ips.return_value = ['192.168.1.1']
        fake_get_networks.return_value = ['network1', 'network2']
        fake_get_vm_console_url.return_value = 'https://test-vm-url'
        vm = MagicMock()
        vm.runtime.powerState = 'poweredOn'
        vm.config.annotation = '{"json": true}'
        vm._moId = 'vm-1234'
        vcenter = MagicMock()

        info = virtual_machine.get_info(vcenter, vm, 'alice')
        expected_info = {'state': 'poweredOn',
                         'console': 'https://test-vm-url',
                         'ips': ['192.168.1.1'],
                         'moid' : 'vm-1234',
                         'networks' : ['network1', 'network2'],
                         'meta': {'json': True}}

        self.assertEqual(info, expected_info)

    @patch.object(virtual_machine, 'get_networks')
    @patch.object(virtual_machine, '_get_vm_ips')
    @patch.object(virtual_machine, '_get_vm_console_url')
    def test_get_info_new_vm(self, fake_get_vm_console_url, fake_get_vm_ips, fake_get_networks):
        """``virtual_machine`` - get_info returns the expected data, even if a new VM is being deployed at the same time"""
        fake_get_vm_ips.return_value = ['192.168.1.1']
        fake_get_networks.return_value = ['network1', 'network2']
        fake_get_vm_console_url.return_value = 'https://test-vm-url'
        vm = MagicMock()
        vm.runtime.powerState = 'poweredOn'
        vm.config.annotation = ''
        vm._moId = 'vm-1234'
        vcenter = MagicMock()

        info = virtual_machine.get_info(vcenter, vm, 'alice')
        expected_info = {'state': 'poweredOn',
                         'console': 'https://test-vm-url',
                         'ips': ['192.168.1.1'],
                         'networks' : ['network1', 'network2'],
                         'moid' : 'vm-1234',
                         'meta': {'component': 'Unknown',
                                  'created': 0,
                                  'version': "Unknown",
                                  'generation': 0,
                                  'configured': False
                                 }
                        }

        self.assertEqual(info, expected_info)

    @patch.object(virtual_machine, 'get_networks')
    @patch.object(virtual_machine, '_get_vm_ips')
    @patch.object(virtual_machine, '_get_vm_console_url')
    def test_get_info_no_config(self, fake_get_vm_console_url, fake_get_vm_ips, fake_get_networks):
        """``virtual_machine`` - sets a default metadata note when there's no config available"""
        fake_get_vm_ips.return_value = ['192.168.1.1']
        fake_get_networks.return_value = ['network1', 'network2']
        fake_get_vm_console_url.return_value = 'https://test-vm-url'
        vm = MagicMock()
        vm.runtime.powerState = 'poweredOn'
        vm.config = None
        vm._moId = 'vm-1234'
        vcenter = MagicMock()

        info = virtual_machine.get_info(vcenter, vm, 'alice')
        expected_info = {'state': 'poweredOn',
                         'console': 'https://test-vm-url',
                         'ips': ['192.168.1.1'],
                         'moid' : 'vm-1234',
                         'networks' : ['network1', 'network2'],
                         'meta': {'component': 'Unknown',
                                  'created': 0,
                                  'version': 'Unknown',
                                  'generation': 0,
                                  'configured': False}}

        self.assertEqual(info, expected_info)

    @patch.object(virtual_machine, 'get_networks')
    @patch.object(virtual_machine, '_get_vm_ips')
    @patch.object(virtual_machine, '_get_vm_console_url')
    def test_get_info_note_none(self, fake_get_vm_console_url, fake_get_vm_ips, fake_get_networks):
        """``virtual_machine`` - TODO"""
        fake_get_vm_ips.return_value = ['192.168.1.1']
        fake_get_networks.return_value = ['network1', 'network2']
        fake_get_vm_console_url.return_value = 'https://test-vm-url'
        vm = MagicMock()
        vm.runtime.powerState = 'poweredOn'
        vm.config.annotation = None
        vm._moId = 'vm-1234'
        vcenter = MagicMock()

        info = virtual_machine.get_info(vcenter, vm, 'alice')
        expected_info = {'state': 'poweredOn',
                         'console': 'https://test-vm-url',
                         'ips': ['192.168.1.1'],
                         'networks' : ['network1', 'network2'],
                         'moid': 'vm-1234',
                         'meta': {'component': 'Unknown',
                                  'created': 0,
                                  'version': 'Unknown',
                                  'generation': 0,
                                  'configured': False}}

        self.assertEqual(info, expected_info)

    def test_set_meta(self):
        """``virtual_machine`` set_meta stores a JSON object as a VM annotation"""
        fake_task = MagicMock()
        fake_task.info.error = None
        fake_vm = MagicMock()
        fake_vm.ReconfigVM_Task.return_value = fake_task

        new_meta = {'component': 'Windows',
                    'version': "10",
                    'generation': 1,
                    'configured': False,
                    'created': 1234,
                    }

        virtual_machine.set_meta(fake_vm, new_meta)
        meta_obj = json.loads(fake_vm.ReconfigVM_Task.call_args[0][0].annotation)

        self.assertEqual(new_meta, meta_obj)

    def test_set_meta_raises(self):
        """``virtual_machine`` set_meta raises ValueError if supplied with a bad object"""
        fake_task = MagicMock()
        fake_task.info.error = None
        fake_vm = MagicMock()
        fake_vm.ReconfigVM_Task.return_value = fake_task

        new_meta = {}
        with self.assertRaises(ValueError):
            virtual_machine.set_meta(fake_vm, new_meta)

    def test_power_value_error(self):
        """``virtual_machine`` - power raises ValueError when supplied with invalid power state value"""
        vm = MagicMock()
        with self.assertRaises(ValueError):
            virtual_machine.power(vm, state='foo')

    def test_power_on_already(self):
        """``virtual_machine`` - power returns True if the VM is already in the requested power state"""
        vm = MagicMock()
        vm.runtime.powerState = 'poweredOn'

        result = virtual_machine.power(vm, state='on')
        expected = True

        self.assertEqual(result, expected)

    def test_power_on(self):
        """``virtual_machine`` - power can turn a VM on"""
        vm = MagicMock()
        vm.runtime.powerState = 'poweredOff'
        vm.PowerOn.return_value.info.completeTime = 1234
        vm.PowerOn.return_value.info.error = None

        result = virtual_machine.power(vm, state='on')
        expected = True

        self.assertEqual(result, expected)

    def test_power_off(self):
        """``virtual_machine`` - power can turn a VM off"""
        vm = MagicMock()
        vm.runtime.powerState = 'poweredOn'
        vm.PowerOff.return_value.info.completeTime = 1234
        vm.PowerOff.return_value.info.error = None

        result = virtual_machine.power(vm, state='off')
        expected = True

        self.assertEqual(result, expected)

    def test_power_reset(self):
        """``virtual_machine`` - power can reboot a VM"""
        vm = MagicMock()
        vm.runtime.powerState = 'poweredOn'
        vm.ResetVM_Task.return_value.info.completeTime = 1234
        vm.ResetVM_Task.return_value.info.error = None

        result = virtual_machine.power(vm, state='restart')
        expected = True

        self.assertEqual(result, expected)

    def test_power_reset_while_off(self):
        """``virtual_machine`` - power can restart a powered off VM"""
        vm = MagicMock()
        vm.runtime.powerState = 'poweredOff'
        vm.PowerOn.return_value.info.completeTime = 1234
        vm.PowerOn.return_value.info.error = None

        result = virtual_machine.power(vm, state='restart')
        expected = True

        self.assertEqual(result, expected)

    @patch.object(virtual_machine.time, 'sleep')
    def test_power_timeout(self, fake_sleep):
        """``virtual_machine`` - power returns false if the task timesout"""
        vm = MagicMock()
        vm.runtime.powerState = 'poweredOn'
        vm.ResetVM_Task.return_value.info.completeTime = None

        result = virtual_machine.power(vm, state='restart')
        expected = False

        self.assertEqual(result, expected)
        self.assertTrue(fake_sleep.called)

    @patch.object(virtual_machine, 'get_process_info')
    def test_output(self, fake_get_process_info):
        """``virtual_machine`` - run_command returns the output of get_process_info"""
        fake_info = MagicMock()
        fake_get_process_info.return_value = fake_info
        vcenter = MagicMock()
        the_vm = MagicMock()

        output = virtual_machine.run_command(vcenter, the_vm, '/bin/ls', 'bob', 'iLoveCats')

        self.assertTrue(output is fake_info)

    @patch.object(virtual_machine.time, 'sleep')
    @patch.object(virtual_machine, 'get_process_info')
    def test_init_timeout(self, fake_get_process_info, fake_sleep):
        """``virtual_machine`` - run_command raises RuntimeError if VMtools isn't available before the timeout"""
        fake_info = MagicMock()
        fake_get_process_info.return_value = fake_info
        vcenter = MagicMock()
        vcenter.content.guestOperationsManager.processManager.StartProgramInGuest.side_effect = [vim.fault.GuestOperationsUnavailable(), vim.fault.GuestOperationsUnavailable()]
        the_vm = MagicMock()

        with self.assertRaises(RuntimeError):
            output = virtual_machine.run_command(vcenter, the_vm, '/bin/ls', 'bob', 'iLoveCats', init_timeout=1)

    @patch.object(virtual_machine.time, 'sleep')
    @patch.object(virtual_machine, 'get_process_info')
    def test_command_timeout(self, fake_get_process_info, fake_sleep):
        """``virtual_machine`` - run_command raises RuntimeError if the command doesn't complete in time"""
        fake_info = MagicMock()
        fake_info.endTime = None
        fake_get_process_info.return_value = fake_info
        vcenter = MagicMock()
        the_vm = MagicMock()

        with self.assertRaises(RuntimeError):
            output = virtual_machine.run_command(vcenter, the_vm, '/bin/ls', 'bob', 'iLoveCats', timeout=1)

    def test_command_one_shot(self):
        """``virtual_machine`` - run_command returns ProcessInfo when param one_shot=True"""
        fake_vcenter = MagicMock()
        fake_vcenter.content.guestOperationsManager.processManager.StartProgramInGuest.return_value = 42
        fake_vm = MagicMock()

        output = virtual_machine.run_command(fake_vcenter, fake_vm, '/bin/ls', 'bob', 'iLoveCats', one_shot=True)

        self.assertTrue(isinstance(output, virtual_machine.vim.vm.guest.ProcessManager.ProcessInfo))

    def test_process_info(self):
        """``virtual_machine`` - get_process_info calls ListProcessesInGuest"""
        vcenter = MagicMock()
        the_vm = MagicMock()

        virtual_machine.get_process_info(vcenter, the_vm, 'alice', 'IloveDogs', 1234)

        self.assertTrue(vcenter.content.guestOperationsManager.processManager.ListProcessesInGuest.called)

    @patch.object(virtual_machine, 'power')
    @patch.object(virtual_machine, '_get_lease')
    def test_basic_deploy_from_ova(self, fake_get_lease, fake_power):
        """``virtural_machine`` - deploy_from_ova return the new VM object"""
        network_map = vim.OvfManager.NetworkMapping()
        the_vm = MagicMock()
        the_vm.name = 'newVM'
        fake_folder = MagicMock()
        fake_folder.childEntity = [the_vm]
        ova = MagicMock()
        fake_host = MagicMock()
        fake_host.name = 'host1'
        fake_host.runtime.inMaintenanceMode = False
        vcenter = MagicMock()
        vcenter.get_by_name.return_value = fake_folder
        vcenter.host_systems = {'someHost': fake_host}

        result = virtual_machine.deploy_from_ova(vcenter=vcenter,
                                                 ova=ova,
                                                 network_map=[network_map],
                                                 username='alice',
                                                 machine_name='newVM',
                                                 logger=MagicMock())
        self.assertTrue(result is the_vm)

    @patch.object(virtual_machine.random, 'choice')
    @patch.object(virtual_machine, 'power')
    @patch.object(virtual_machine, '_get_lease')
    def test_deploy_from_ova_random_ds_choice(self, fake_get_lease, fake_power, fake_choice):
        """``virtural_machine`` - deploy_from_ova picks a defined datastore to use by random"""
        # pseudo-random choice is effectively round-robbin over a long enough
        # period of time/ with enough choices made
        network_map = vim.OvfManager.NetworkMapping()
        the_vm = MagicMock()
        the_vm.name = 'newVM'
        fake_folder = MagicMock()
        fake_folder.childEntity = [the_vm]
        ova = MagicMock()
        fake_host = MagicMock()
        fake_host.name = 'host1'
        vcenter = MagicMock()
        vcenter.get_by_name.return_value = fake_folder
        vcenter.host_systems.values.return_value = [fake_host]

        virtual_machine.deploy_from_ova(vcenter=vcenter,
                                        ova=ova,
                                        network_map=[network_map],
                                        username='alice',
                                        machine_name='newVM',
                                        logger=MagicMock())

        expected_calls = 2 # 1 for the datastore, 1 for the ESXi host
        actual_calls = fake_choice.call_count

        self.assertEqual(expected_calls, actual_calls)

    @patch.object(virtual_machine, '_get_lease')
    def test_deploy_from_ova_runtimeerror(self, fake_get_lease):
        """``virtural_machine`` - deploy_from_ova raises RuntimeError if it cannot find the new created VM"""
        network_map = vim.OvfManager.NetworkMapping()
        the_vm = MagicMock()
        the_vm.name = 'newVM'
        fake_folder = MagicMock()
        ova = MagicMock()
        fake_host = MagicMock()
        fake_host.name = 'host1'
        fake_host.runtime.inMaintenanceMode = False
        vcenter = MagicMock()
        vcenter.get_by_name.return_value = fake_folder
        vcenter.host_systems = {'someHost': fake_host}

        with self.assertRaises(RuntimeError):
            virtual_machine.deploy_from_ova(vcenter=vcenter,
                                            ova=ova,
                                            network_map=[network_map],
                                            username='alice',
                                            machine_name='newVM',
                                            logger=MagicMock())

    @patch.object(virtual_machine, '_get_lease')
    def test_deploy_from_ova_list(self, fake_get_lease):
        """``virtural_machine`` - deploy_from_ova param network_map must be list"""
        network_map = vim.OvfManager.NetworkMapping()
        the_vm = MagicMock()
        the_vm.name = 'newVM'
        fake_folder = MagicMock()
        fake_folder.childEntity = [the_vm]
        ova = MagicMock()
        fake_host = MagicMock()
        fake_host.name = 'host1'
        vcenter = MagicMock()
        vcenter.get_by_name.return_value = fake_folder
        vcenter.host_systems.values.return_value = [fake_host]

        with self.assertRaises(ValueError):
            virtual_machine.deploy_from_ova(vcenter=vcenter,
                                            ova=ova,
                                            network_map=network_map,
                                            username='alice',
                                            machine_name='newVM',
                                            logger=MagicMock())

    def test_get_lease(self):
        """``virtual_machine`` - _get_lease returns a VM deployment lease"""
        fake_lease = MagicMock()
        fake_lease.error = None
        fake_lease.state = 'ready'
        fake_resource_pool = MagicMock()
        fake_resource_pool.ImportVApp.return_value = fake_lease

        result = virtual_machine._get_lease(resource_pool=fake_resource_pool,
                                            import_spec=MagicMock(),
                                            folder=MagicMock(),
                                            host=MagicMock())

        self.assertTrue(result is fake_lease)

    def test_get_lease_error(self):
        """``virtual_machine`` - _get_lease raises ValueError upon error"""
        fake_lease = MagicMock()
        fake_lease.error.msg = 'doh'
        fake_lease.state = 'ready'
        fake_resource_pool = MagicMock()
        fake_resource_pool.ImportVApp.return_value = fake_lease

        with self.assertRaises(ValueError):
            virtual_machine._get_lease(resource_pool=fake_resource_pool,
                                       import_spec=MagicMock(),
                                       folder=MagicMock(),
                                       host=MagicMock())

    @patch.object(virtual_machine, 'time') # so test runs faster
    def test_get_lease_timeout(self, fake_time):
        """``virtual_machine`` - _get_lease raises DeployFailure upon error"""
        fake_lease = MagicMock()
        fake_lease.error = None
        fake_lease.state = 'not ready'
        fake_resource_pool = MagicMock()
        fake_resource_pool.ImportVApp.return_value = fake_lease

        with self.assertRaises(DeployFailure):
            virtual_machine._get_lease(resource_pool=fake_resource_pool,
                                       import_spec=MagicMock(),
                                       folder=MagicMock(),
                                       host=MagicMock())

    @patch.object(virtual_machine, 'consume_task')
    def test_adjust_ram(self, fake_consume_task):
        """``virtual_machine`` - 'adjust_ram' reconfigures the VM"""
        the_vm = MagicMock()

        mb_of_ram = 1024
        virtual_machine.adjust_ram(the_vm, mb_of_ram=mb_of_ram)

        the_args, _ = the_vm.Reconfigure.call_args
        config_spec = the_args[0]

        self.assertTrue(the_vm.Reconfigure.called)
        self.assertEqual(mb_of_ram, config_spec.memoryMB)

    @patch.object(virtual_machine, 'consume_task')
    def test_adjust_cpu(self, fake_consume_task):
        """``virtual_machine`` - 'adjust_cpu' reconfigures the VM"""
        the_vm = MagicMock()
        cpu_count = 8
        virtual_machine.adjust_cpu(the_vm, cpu_count=cpu_count)

        the_args, _ = the_vm.Reconfigure.call_args
        config_spec = the_args[0]

        self.assertTrue(the_vm.Reconfigure.called)
        self.assertEqual(cpu_count, config_spec.numCPUs)

    @patch.object(virtual_machine.vim.vm, 'ConfigSpec')
    @patch.object(virtual_machine.vim.vm.device.VirtualDevice, 'ConnectInfo')
    @patch.object(virtual_machine.vim.vm.device.VirtualEthernetCard, 'DistributedVirtualPortBackingInfo')
    @patch.object(virtual_machine.vim.dvs, 'PortConnection')
    @patch.object(virtual_machine.vim.vm.device, 'VirtualDeviceSpec')
    @patch.object(virtual_machine, 'consume_task')
    def test_change_network(self, fake_consume_task, fake_VirtualDeviceSpec, fake_PortConnection,
                            fake_DistributedVirtualPortBackingInfo, fake_ConnectInfo,
                            fake_ConfigSpec):
        """``virtual_machine`` - 'change_network' returns None upon success"""
        fake_network = MagicMock()
        fake_nic = MagicMock()
        fake_nic.deviceInfo.label = 'Network adapter 1'
        the_vm = MagicMock()
        the_vm.config.hardware.device = [fake_nic]

        result = virtual_machine.change_network(the_vm, fake_network)
        expected = None

        self.assertTrue(result is None)

    @patch.object(virtual_machine, 'consume_task')
    def test_change_network_no_adapter(self, fake_consume_task):
        """``virtual_machine`` - 'change_network' returns None upon success"""
        fake_network = MagicMock()
        fake_nic = MagicMock()
        fake_nic.deviceInfo.label = 'Network adapter 7'
        the_vm = MagicMock()
        the_vm.config.hardware.device = [fake_nic]

        with self.assertRaises(RuntimeError):
            virtual_machine.change_network(the_vm, fake_network)

    def test_get_networks(self):
        """``virtual_machine`` - 'get_networks' Returns a List"""
        fake_vcenter = MagicMock()
        fake_vm = MagicMock()
        fake_vm.name = 'someVM'
        fake_network = MagicMock()
        fake_network.vm = [fake_vm]
        fake_vcenter.networks = {'bill_someNetwork' : fake_network}

        result = virtual_machine.get_networks(fake_vcenter, fake_vm, 'bill')
        expected = ['someNetwork']

        self.assertEqual(result, expected)


class TestConfigStaticIP(unittest.TestCase):
    """A suite of test cases for the ``config_static_ip`` function"""

    @patch.object(virtual_machine, '_config_windows_network')
    def test_windows(self, fake_config_windows_network):
        """``config_static_ip`` support Windows operating system"""
        virtual_machine.config_static_ip(vcenter=MagicMock(),
                                         the_vm=MagicMock(),
                                         static_ip='1.2.3.4',
                                         default_gateway='1.2.3.1',
                                         subnet_mask='255.255.255.0',
                                         dns=['1.2.3.2'],
                                         user='someAdminUser',
                                         password='IloveKatz!',
                                         logger=MagicMock(),
                                         os='windows')

        self.assertTrue(fake_config_windows_network.called)

    @patch.object(virtual_machine, '_config_centos8_network')
    def test_centos8(self, fake_config_centos8_network):
        """``config_static_ip`` support CentOS operating system"""
        virtual_machine.config_static_ip(vcenter=MagicMock(),
                                         the_vm=MagicMock(),
                                         static_ip='1.2.3.4',
                                         default_gateway='1.2.3.1',
                                         subnet_mask='255.255.255.0',
                                         dns=['1.2.3.2'],
                                         user='someAdminUser',
                                         password='IloveKatz!',
                                         logger=MagicMock(),
                                         os='centos8')

        self.assertTrue(fake_config_centos8_network.called)

    def test_unsupports_os(self):
        """``config_static_ip`` raises ValueError when supplied with an unsupported OS"""
        with self.assertRaises(ValueError):
            virtual_machine.config_static_ip(vcenter=MagicMock(),
                                             the_vm=MagicMock(),
                                             static_ip='1.2.3.4',
                                             default_gateway='1.2.3.1',
                                             subnet_mask='255.255.255.0',
                                             dns=['1.2.3.2'],
                                             user='someAdminUser',
                                             password='IloveKatz!',
                                             logger=MagicMock(),
                                             os='blorgOS')

    @patch.object(virtual_machine, 'run_command')
    def test_config_windows_network(self, fake_run_command):
        """``_config_windows_network`` Runs ``netsh.exe`` to set the IP"""
        virtual_machine._config_windows_network(vcenter=MagicMock(),
                                                the_vm=MagicMock(),
                                                static_ip='1.2.3.4',
                                                default_gateway='1.2.3.1',
                                                netmask='255.255.255.0',
                                                dns=['1.2.3.2'],
                                                user='someAdminUser',
                                                password='IloveKatz!',
                                                logger=MagicMock())
        the_args, _ = fake_run_command.call_args
        cmd_ran = the_args[-1]
        expected = 'C:/Windows/System32/netsh.exe'

        self.assertEqual(cmd_ran, expected)

    @patch.object(virtual_machine, 'run_command')
    def test_config_windows_network_2_dns(self, fake_run_command):
        """``_config_windows_network`` Runs ``netsh.exe`` to set the IP"""
        virtual_machine._config_windows_network(vcenter=MagicMock(),
                                                the_vm=MagicMock(),
                                                static_ip='1.2.3.4',
                                                default_gateway='1.2.3.1',
                                                netmask='255.255.255.0',
                                                dns=['1.2.3.2', '1.2.3.3'],
                                                user='someAdminUser',
                                                password='IloveKatz!',
                                                logger=MagicMock())

        self.assertEqual(fake_run_command.call_count, 3)

    @patch.object(virtual_machine, '_upload_nic_config')
    @patch.object(virtual_machine, '_format_dns')
    @patch.object(virtual_machine, '_run_cmd')
    def test_config_centos8_network_dns(self, fake_run_cmd, fake_format_dns, fake_upload_nic_config):
        """``_config_centos8_network`` Adds the ifcfg formatted DNS parts to the config file"""
        virtual_machine._config_centos8_network(vcenter=MagicMock(),
                                               the_vm=MagicMock(),
                                               static_ip='1.2.3.4',
                                               default_gateway='1.2.3.1',
                                               netmask='255.255.255.0',
                                               dns=['1.2.3.2', '1.2.3.3'],
                                               user='someAdminUser',
                                               password='IloveKatz!',
                                               logger=MagicMock())

        self.assertTrue(fake_format_dns.called)

    @patch.object(virtual_machine, '_upload_nic_config')
    @patch.object(virtual_machine, '_format_dns')
    @patch.object(virtual_machine, '_run_cmd')
    def test_config_centos8_network_upload(self, fake_run_cmd, fake_format_dns, fake_upload_nic_config):
        """``_config_centos8_network`` Uploads the ifcfg formatted config file to the VM"""
        virtual_machine._config_centos8_network(vcenter=MagicMock(),
                                               the_vm=MagicMock(),
                                               static_ip='1.2.3.4',
                                               default_gateway='1.2.3.1',
                                               netmask='255.255.255.0',
                                               dns=['1.2.3.2', '1.2.3.3'],
                                               user='someAdminUser',
                                               password='IloveKatz!',
                                               logger=MagicMock())

        self.assertTrue(fake_upload_nic_config.called)

    @patch.object(virtual_machine, '_upload_nic_config')
    @patch.object(virtual_machine, '_format_dns')
    @patch.object(virtual_machine, '_run_cmd')
    def test_config_centos8_network_run_cmd(self, fake_run_cmd, fake_format_dns, fake_upload_nic_config):
        """``_config_centos8_network`` Runs 3 command to set the network"""
        virtual_machine._config_centos8_network(vcenter=MagicMock(),
                                               the_vm=MagicMock(),
                                               static_ip='1.2.3.4',
                                               default_gateway='1.2.3.1',
                                               netmask='255.255.255.0',
                                               dns=['1.2.3.2', '1.2.3.3'],
                                               user='someAdminUser',
                                               password='IloveKatz!',
                                               logger=MagicMock())

        self.assertEqual(fake_run_cmd.call_count, 4)

    @patch.object(virtual_machine, 'run_command')
    def test_run_cmd(self, fake_run_command):
        """``_run_cmd`` Executes a shell command with sudo"""
        virtual_machine._run_cmd(vcenter=MagicMock(),
                                 the_vm=MagicMock(),
                                 cmd='/bin/ls',
                                 args='-la /tmp',
                                 user='sally',
                                 password='DogzAreGreat!',
                                 logger=MagicMock())

        the_args, the_kwargs = fake_run_command.call_args
        full_command = '{} {}'.format(the_args[-1], the_kwargs['arguments'])
        expected = "/bin/bash -c '/bin/echo DogzAreGreat! | /bin/sudo -S /bin/ls -la /tmp'"

        self.assertEqual(full_command, expected)

    @patch.object(virtual_machine.requests, 'put')
    def test_upload_nic_config_http_put(self, fake_put):
        """``_upload_nic_config`` Uploads the file via the PUT method"""
        fake_vcenter = MagicMock()
        fake_the_vm = MagicMock()
        fake_logger = MagicMock()
        nic_config = 'TYPE=Ethernet'
        config_name = 'eth0'

        virtual_machine._upload_nic_config(fake_vcenter, fake_the_vm, nic_config, config_name, 'root', 'a', fake_logger)

        self.assertTrue(fake_put.called)

    @patch.object(virtual_machine.requests, 'put')
    def test_upload_nic_config_checks_http_status(self, fake_put):
        """``_upload_nic_config`` Checks the HTTP response status of the upload"""
        fake_vcenter = MagicMock()
        fake_the_vm = MagicMock()
        fake_resp = MagicMock()
        fake_logger = MagicMock()
        nic_config = 'TYPE=Ethernet'
        config_name = 'eth0'
        fake_put.return_value = fake_resp

        virtual_machine._upload_nic_config(fake_vcenter, fake_the_vm, nic_config, config_name, 'root', 'a', fake_logger)

        self.assertTrue(fake_resp.raise_for_status.called)

    def test_format_dns(self):
        """``_format_dns`` Can format the DNS section for an ifcfg file for multiple DNS servers"""
        result = virtual_machine._format_dns(['1.1.1.1', '8.8.8.8'])
        expected = "DNS1=1.1.1.1\nDNS2=8.8.8.8"

        self.assertEqual(result, expected)


    @patch.object(virtual_machine.time, 'sleep')
    def test_get_upload_url(self, fake_sleep):
        """``_get_upload_url`` retries while the VM is booting up"""
        fake_vm = MagicMock()
        fake_creds = MagicMock()
        fake_upload_path = '/home/foo.sh'
        fake_file_size = 9001
        fake_file_attributes = MagicMock()
        fake_vcenter = MagicMock()
        fake_vcenter.content.guestOperationsManager.fileManager.InitiateFileTransferToGuest.side_effect = [virtual_machine.vim.fault.GuestOperationsUnavailable(),
                                                                                                           virtual_machine.vim.fault.GuestOperationsUnavailable(),
                                                                                                           'https://some-url.org']
        virtual_machine._get_upload_url(fake_vcenter,
                                        fake_vm,
                                        fake_creds,
                                        fake_upload_path,
                                        fake_file_size,
                                        fake_file_attributes)

        # one for every vmware.vim.fault.GuestOperationsUnavailable() side_effect
        self.assertEqual(fake_sleep.call_count, 2)

    @patch.object(virtual_machine.time, 'sleep')
    def test_get_upload_url(self, fake_sleep):
        """``_get_upload_url`` Raises ValueError if the VM is never ready for the file upload"""
        fake_vm = MagicMock()
        fake_creds = MagicMock()
        fake_upload_path = '/home/foo.sh'
        fake_file_size = 9001
        fake_file_attributes = MagicMock()
        fake_vcenter = MagicMock()
        fake_vcenter.content.guestOperationsManager.fileManager.InitiateFileTransferToGuest.side_effect = [virtual_machine.vim.fault.GuestOperationsUnavailable(),
                                                                                                           virtual_machine.vim.fault.GuestOperationsUnavailable(),
                                                                                                           virtual_machine.vim.fault.GuestOperationsUnavailable(),
                                                                                                           virtual_machine.vim.fault.GuestOperationsUnavailable(),
                                                                                                           virtual_machine.vim.fault.GuestOperationsUnavailable(),
                                                                                                           virtual_machine.vim.fault.GuestOperationsUnavailable(),
                                                                                                           virtual_machine.vim.fault.GuestOperationsUnavailable(),
                                                                                                           virtual_machine.vim.fault.GuestOperationsUnavailable(),
                                                                                                           virtual_machine.vim.fault.GuestOperationsUnavailable(),
                                                                                                           virtual_machine.vim.fault.GuestOperationsUnavailable(),]

        with self.assertRaises(ValueError):
            virtual_machine._get_upload_url(fake_vcenter,
                                            fake_vm,
                                            fake_creds,
                                            fake_upload_path,
                                            fake_file_size,
                                            fake_file_attributes)

class TestVMExportFunctions(unittest.TestCase):
    """A suite of test cases for functions used to create an OVA from an virtual machine"""

    @patch.object(virtual_machine, 'open')
    @patch.object(virtual_machine.requests, 'get')
    def test_download_vmdk(self, fake_get, fake_open):
        """``download_vmdk`` - Returns a list with a vim.OvfManager.OvfFile object when everything works as expected"""
        fake_log = MagicMock()
        fake_device = MagicMock()
        fake_device.targetId = 'foo.vmdk'
        fake_device.key = 'someKey'
        fake_resp = MagicMock()
        fake_resp.iter_content.return_value = [b'some', b'data']
        fake_get.return_value = fake_resp
        save_location = '/tmp'
        http_cookies = {}

        output = virtual_machine.download_vmdk(save_location, http_cookies, fake_device, fake_log)

        self.assertEqual(1, len(output))
        self.assertTrue(isinstance(output[0], virtual_machine.vim.OvfManager.OvfFile))

    @patch.object(virtual_machine, 'open')
    @patch.object(virtual_machine.requests, 'get')
    def test_download_vmdk_error(self, fake_get, fake_open):
        """``download_vmdk`` - Returns an empty list if the device is not a VMDK"""
        fake_log = MagicMock()
        fake_device = MagicMock()
        fake_device.targetId = ''
        fake_device.disk = False
        fake_device.key = 'someKey'
        fake_resp = MagicMock()
        fake_resp.iter_content.return_value = [b'some', b'data']
        fake_get.return_value = fake_resp
        save_location = '/tmp'
        http_cookies = {}

        output = virtual_machine.download_vmdk(save_location, http_cookies, fake_device, fake_log)

        self.assertEqual(0, len(output))

    @patch.object(virtual_machine, 'open')
    @patch.object(virtual_machine.requests, 'get')
    def test_download_vmdk_skips_keepalive_blocks(self, fake_get, fake_open):
        """``download_vmdk`` - Does not write empty blocks as the result of HTTP keepalives"""
        fake_log = MagicMock()
        fake_device = MagicMock()
        fake_device.targetId = 'foo.vmdk'
        fake_device.key = 'someKey'
        fake_resp = MagicMock()
        fake_resp.iter_content.return_value = [b'some', b'', b'data']
        fake_get.return_value = fake_resp
        save_location = '/tmp'
        http_cookies = {}

        virtual_machine.download_vmdk(save_location, http_cookies, fake_device, fake_log)
        write_count = fake_open.return_value.__enter__.return_value.write.call_count
        expected = 2

        self.assertEqual(write_count, expected)

    @patch.object(virtual_machine.vim.OvfManager, 'CreateDescriptorParams')
    def test_get_vm_ovf_xml(self, fake_CreateDescriptorParams):
        """``get_vm_ovf_xml`` returns a string when everything works as expected"""
        fake_vm_ovf = MagicMock()
        fake_vm_ovf.error = []
        fake_vm_ovf.ovfDescriptor = '<some>xml</some>'
        fake_vcenter = MagicMock()
        fake_vcenter.content.ovfManager.CreateDescriptor.return_value = fake_vm_ovf
        fake_vm = MagicMock()
        fake_vm.name = 'myVM'
        fake_device_ovfs = [MagicMock(), MagicMock()]

        output = virtual_machine.get_vm_ovf_xml(fake_vm, fake_device_ovfs, fake_vcenter)
        expected = fake_vm_ovf.ovfDescriptor

        self.assertEqual(output, expected)

    @patch.object(virtual_machine.vim.OvfManager, 'CreateDescriptorParams')
    def test_get_vm_ovf_xml_error(self, fake_CreateDescriptorParams):
        """``get_vm_ovf_xml`` Raises an exception when unable to create the OVF xml"""
        fake_vm_ovf = MagicMock()
        fake_error = MagicMock()
        fake_error.fault = RuntimeError("testing")
        fake_vm_ovf.error = [fake_error]
        fake_vm_ovf.ovfDescriptor = '<some>xml</some>'
        fake_vcenter = MagicMock()
        fake_vcenter.content.ovfManager.CreateDescriptor.return_value = fake_vm_ovf
        fake_vm = MagicMock()
        fake_vm.name = 'myVM'
        fake_device_ovfs = [MagicMock(), MagicMock()]

        with self.assertRaises(RuntimeError):
            virtual_machine.get_vm_ovf_xml(fake_vm, fake_device_ovfs, fake_vcenter)

    @patch.object(virtual_machine.time, 'sleep')
    def test_progress_chimer(self, fake_sleep):
        """``ProgressChimer`` - Thread starts upon creation."""
        fake_lease = MagicMock()
        fake_log = MagicMock()
        chimer = virtual_machine.ProgressChimer(fake_lease, fake_log)

        self.assertTrue(chimer.isAlive())
        chimer.complete()

    @patch.object(virtual_machine.time, 'sleep')
    def test_progress_chimer_completes(self, fake_sleep):
        """``ProgressChimer`` - 'complete' blocks until the thread terminates"""
        fake_lease = MagicMock()
        fake_log = MagicMock()
        chimer = virtual_machine.ProgressChimer(fake_lease, fake_log)

        chimer.complete()

        self.assertFalse(chimer.isAlive())

    @patch.object(virtual_machine.time, 'sleep')
    def test_progress_chimer_with_statement(self, fake_sleep):
        """``ProgressChimer`` - support auto start/stop in a 'with' statement"""
        fake_lease = MagicMock()
        fake_log = MagicMock()

        with virtual_machine.ProgressChimer(fake_lease, fake_log) as chimer:
            self.assertTrue(chimer.isAlive())
        self.assertFalse(chimer.isAlive())

    @patch.object(virtual_machine.time, 'sleep')
    def test_progress_chimer_lease_complete(self, fake_sleep):
        """``ProgressChimer`` - complete terminates the NFC lease"""
        fake_lease = MagicMock()
        fake_log = MagicMock()
        chimer = virtual_machine.ProgressChimer(fake_lease, fake_log)
        chimer.complete()

        self.assertTrue(chimer._lease.HttpNfcLeaseComplete.called)

    @patch.object(virtual_machine.time, 'sleep')
    def test_block_on_lease(self, fake_sleep):
        """``_block_on_lease`` - waits for the NFS lease to be ready"""
        fake_lease = MagicMock()
        fake_lease.state = virtual_machine.vim.HttpNfcLease.State.ready

        virtual_machine._block_on_lease(fake_lease)

        self.assertFalse(fake_sleep.called)

    @patch.object(virtual_machine.time, 'sleep')
    def test_block_on_lease_blocks(self, fake_sleep):
        """``_block_on_lease`` - blocks until the NFS lease is ready"""
        fake_lease = MagicMock()
        type(fake_lease).state = PropertyMock(side_effect=['', virtual_machine.vim.HttpNfcLease.State.ready, virtual_machine.vim.HttpNfcLease.State.ready])

        virtual_machine._block_on_lease(fake_lease)

        self.assertEqual(fake_sleep.call_count, 1)

    @patch.object(virtual_machine.time, 'sleep')
    def test_block_on_lease_error(self, fake_sleep):
        """``_block_on_lease`` - Raises RuntimeError if the lease state is an error"""
        fake_lease = MagicMock()
        fake_lease.state = virtual_machine.vim.HttpNfcLease.State.error

        with self.assertRaises(RuntimeError):
            virtual_machine._block_on_lease(fake_lease)

    @patch.object(virtual_machine.time, 'sleep')
    def test_block_on_lease_never_ready(self, fake_sleep):
        """``_block_on_lease`` - raises RuntimeError if the lease is never ready or an error"""
        fake_lease = MagicMock()
        fake_lease.state = 'foo'

        with self.assertRaises(RuntimeError):
            virtual_machine._block_on_lease(fake_lease)

    @patch.object(virtual_machine.time, 'sleep')
    def test_block_on_lease_never_ready(self, fake_sleep):
        """``_block_on_lease`` - raises RuntimeError if the lease is never ready or an error"""
        fake_lease = MagicMock()
        fake_lease.state = 'foo'

        try:
            virtual_machine._block_on_lease(fake_lease)
        except RuntimeError:
            pass

        sleep_call_count = fake_sleep.call_count
        expected_call_count = 45
        slept_for = sum([x[0][0] for x in fake_sleep.call_args_list])
        expected_slept_for = 990 # seconds

        self.assertEqual(sleep_call_count, expected_call_count)
        self.assertEqual(slept_for, expected_slept_for)

    @patch.object(virtual_machine, '_block_on_lease')
    @patch.object(virtual_machine, 'get_vm_ovf_xml')
    @patch.object(virtual_machine, 'download_vmdk')
    @patch.object(virtual_machine, 'tarfile')
    @patch.object(virtual_machine.os, 'makedirs')
    @patch.object(virtual_machine.time, 'sleep')
    @patch.object(virtual_machine, 'open')
    @patch.object(virtual_machine.os, 'rename')
    @patch.object(virtual_machine.os, 'listdir')
    @patch.object(virtual_machine.shutil, 'rmtree')
    def test_make_ova(self, fake_rmtree, fake_listdir, fake_rename, fake_open,
        fake_sleep, fake_makedirs, fake_tarfile, fake_downlaod_vmdk, fake_get_vm_ovf_xml,
        fake_block_on_lease):
        """``make_ova`` - Returns the location of the new OVA file"""
        fake_vcenter = MagicMock()
        fake_vm = MagicMock()
        fake_vm.name = 'myVM'
        fake_log = MagicMock()

        output = virtual_machine.make_ova(fake_vcenter, fake_vm, '/save/ova/here', fake_log)
        expected = '/save/ova/here/myVM.ova'

        self.assertEqual(output, expected)

    @patch.object(virtual_machine, '_block_on_lease')
    @patch.object(virtual_machine, 'get_vm_ovf_xml')
    @patch.object(virtual_machine, 'download_vmdk')
    @patch.object(virtual_machine, 'tarfile')
    @patch.object(virtual_machine.os, 'makedirs')
    @patch.object(virtual_machine.time, 'sleep')
    @patch.object(virtual_machine, 'open')
    @patch.object(virtual_machine.os, 'rename')
    @patch.object(virtual_machine.os, 'listdir')
    @patch.object(virtual_machine.shutil, 'rmtree')
    def test_make_ova_downloads_all_vmdks(self, fake_rmtree, fake_listdir, fake_rename, fake_open,
        fake_sleep, fake_makedirs, fake_tarfile, fake_download_vmdk, fake_get_vm_ovf_xml,
        fake_block_on_lease):
        """``make_ova`` - Downloads all the VMDKs of a virtual machine"""
        fake_vcenter = MagicMock()
        fake_vm = MagicMock()
        fake_vm.name = 'myVM'
        fake_vm.ExportVm.return_value.info.deviceUrl = ['https://foo.com', 'https://bar.com']
        fake_log = MagicMock()

        virtual_machine.make_ova(fake_vcenter, fake_vm, '/save/ova/here', fake_log)
        vmdks_downloaded = fake_download_vmdk.call_count
        expected = 2

        self.assertEqual(vmdks_downloaded, expected)

    @patch.object(virtual_machine, '_block_on_lease')
    @patch.object(virtual_machine, 'get_vm_ovf_xml')
    @patch.object(virtual_machine, 'download_vmdk')
    @patch.object(virtual_machine, 'tarfile')
    @patch.object(virtual_machine.os, 'makedirs')
    @patch.object(virtual_machine.time, 'sleep')
    @patch.object(virtual_machine, 'open')
    @patch.object(virtual_machine.os, 'rename')
    @patch.object(virtual_machine.os, 'listdir')
    @patch.object(virtual_machine.shutil, 'rmtree')
    def test_make_ova_adds_all_files(self, fake_rmtree, fake_listdir, fake_rename, fake_open,
        fake_sleep, fake_makedirs, fake_tarfile, fake_download_vmdk, fake_get_vm_ovf_xml,
        fake_block_on_lease):
        """``make_ova`` - adds all files to the OVA"""
        fake_vcenter = MagicMock()
        fake_vm = MagicMock()
        fake_vm.name = 'myVM'
        fake_log = MagicMock()
        fake_listdir.return_value = ['myVM.ovf', 'disk-0.vmdk']

        virtual_machine.make_ova(fake_vcenter, fake_vm, '/save/ova/here', fake_log)
        files_added_to_ova = fake_tarfile.open.return_value.add.call_count
        expected = 2

        self.assertEqual(files_added_to_ova, expected)


if __name__ == '__main__':
    unittest.main()
