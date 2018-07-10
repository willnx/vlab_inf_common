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

        console_url = virtual_machine._get_vm_console_url(vcenter=vcenter, virtual_machine=vm)
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
        """TODO"""
        fake_get_vm_ips.return_value = ['192.168.1.1']
        fake_get_vm_console_url.return_value = 'https://test-vm-url'
        vm = MagicMock()
        vm.runtime.powerState = 'on'
        vcenter = MagicMock()

        info = virtual_machine.get_info(vcenter, vm)
        expected_info = {'console': 'https://test-vm-url', 'ips': ['192.168.1.1'], 'state': 'on'}

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

        result = virtual_machine.power(vm, state='on')
        expected = True

        self.assertEqual(result, expected)

    def test_power_off(self):
        """``virtual_machine`` - power can turn a VM off"""
        vm = MagicMock()
        vm.runtime.powerState = 'on'
        vm.PowerOff.return_value.info.completeTime = 1234

        result = virtual_machine.power(vm, state='off')
        expected = True

        self.assertEqual(result, expected)

    def test_power_reset(self):
        """``virtual_machine`` - power reboot a VM"""
        vm = MagicMock()
        vm.runtime.powerState = 'off'
        vm.ResetVM.return_value.info.completeTime = 1234

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

        vcenter.content.guestOperationsManager.processManager.ListProcessesInGuest.assert_called()


if __name__ == '__main__':
    unittest.main()
