# -*- coding: UTF-8 -*-
"""
A unit tests for the virtual_machine functions
"""
import unittest
from unittest.mock import MagicMock, patch

from pyVmomi import vim

from vlab_inf_common.vmware import virtual_machine


class TestVirtualMachine(unittest.TestCase):
    """A set of test cases for ``virtual_machine``"""

    @patch.object(virtual_machine.OpenSSL.crypto, 'load_certificate')
    @patch.object(virtual_machine.ssl, 'get_server_certificate')
    def test_get_vm_console_url(self, fake_get_server_certificate, fake_load_certificate):
        """``virtual_machine`` - _get_vm_console_url returns the expected string"""
        fake_load_certificate.return_value.digest.return_value = 'test-thumbprint'
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
        expected_url = 'https://localhost:9443/vsphere-client/webconsole.html?vmId=test-vm-id&vmName=test-vm-name&serverGuid=Test-UUID&locale=en_US&host=localhost:443&sessionTicket=test-session&thumbprint=test-thumbprint'

        self.assertEqual(console_url, expected_url)

    def test_get_vm_ips(self):
        """``virtual_machine`` - _get_vm_ips iterates over the NICs and returns a list of all IPs"""
        nic = MagicMock()
        nic.ipAddress = ['192.168.1.1']
        vm = MagicMock()
        vm.guest.net = [nic]

        ips = virtual_machine._get_vm_ips(vm)
        expected_ips = ['192.168.1.1']

        self.assertEqual(ips, expected_ips)

    @patch.object(virtual_machine, '_get_vm_ips')
    @patch.object(virtual_machine, '_get_vm_console_url')
    def test_get_info(self, fake_get_vm_console_url, fake_get_vm_ips):
        """``virtual_machine`` - get_info returns the expected data"""
        fake_get_vm_ips.return_value = ['192.168.1.1']
        fake_get_vm_console_url.return_value = 'https://test-vm-url'
        vm = MagicMock()
        vm.runtime.powerState = 'on'
        vm.config.annotation = 'some note'
        vcenter = MagicMock()

        info = virtual_machine.get_info(vcenter, vm)
        expected_info = {'note': 'some note', 'console': 'https://test-vm-url', 'ips': ['192.168.1.1'], 'state': 'on'}

        self.assertEqual(info, expected_info)

    def test_power_value_error(self):
        """``virtual_machine`` - power raises ValueError when supplied with invalid power state value"""
        vm = MagicMock()
        with self.assertRaises(ValueError):
            virtual_machine.power(vm, state='foo')

    def test_power_on_already(self):
        """``virtual_machine`` - power returns True if the VM is already in the requested power state"""
        vm = MagicMock()
        vm.runtime.powerState = 'on'

        result = virtual_machine.power(vm, state='on')
        expected = True

        self.assertEqual(result, expected)

    def test_power_on(self):
        """``virtual_machine`` - power can turn a VM on"""
        vm = MagicMock()
        vm.runtime.powerState = 'off'
        vm.PowerOn.return_value.info.completeTime = 1234
        vm.PowerOn.return_value.info.error = None

        result = virtual_machine.power(vm, state='on')
        expected = True

        self.assertEqual(result, expected)

    def test_power_off(self):
        """``virtual_machine`` - power can turn a VM off"""
        vm = MagicMock()
        vm.runtime.powerState = 'on'
        vm.PowerOff.return_value.info.completeTime = 1234
        vm.PowerOff.return_value.info.error = None

        result = virtual_machine.power(vm, state='off')
        expected = True

        self.assertEqual(result, expected)

    def test_power_reset(self):
        """``virtual_machine`` - power can reboot a VM"""
        vm = MagicMock()
        vm.runtime.powerState = 'off'
        vm.ResetVM_Task.return_value.info.completeTime = 1234
        vm.ResetVM_Task.return_value.info.error = None

        result = virtual_machine.power(vm, state='restart')
        expected = True

        self.assertEqual(result, expected)

    @patch.object(virtual_machine.time, 'sleep')
    def test_power_timeout(self, fake_sleep):
        """``virtual_machine`` - power returns false if the task timesout"""
        vm = MagicMock()
        vm.runtime.powerState = 'off'
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
        """``virtual_machine`` - run_command returns the output of get_process_info"""
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
        vcenter = MagicMock()
        vcenter.get_by_name.return_value = fake_folder
        vcenter.host_systems.values.return_value = [fake_host]

        result = virtual_machine.deploy_from_ova(vcenter=vcenter,
                                                 ova=ova,
                                                 network_map=[network_map],
                                                 username='alice',
                                                 machine_name='newVM',
                                                 logger=MagicMock())
        self.assertTrue(result is the_vm)



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
        vcenter = MagicMock()
        vcenter.get_by_name.return_value = fake_folder
        vcenter.host_systems.values.return_value = [fake_host]

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
        """``virtual_machine`` - _get_lease raises ValueError upon error"""
        fake_lease = MagicMock()
        fake_lease.error = None
        fake_lease.state = 'not ready'
        fake_resource_pool = MagicMock()
        fake_resource_pool.ImportVApp.return_value = fake_lease

        with self.assertRaises(RuntimeError):
            virtual_machine._get_lease(resource_pool=fake_resource_pool,
                                       import_spec=MagicMock(),
                                       folder=MagicMock(),
                                       host=MagicMock())

if __name__ == '__main__':
    unittest.main()
