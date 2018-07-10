# -*- coding: UTF-8 -*-
"""
A suite of tests for the ova module
"""
import unittest
from unittest.mock import patch, MagicMock

from pyVmomi import vmodl

from vlab_inf_common.vmware import ova


class TestOva(unittest.TestCase):
    """A set of test cases for the ``Ova`` object"""
    @patch.object(ova, 'tarfile')
    @patch.object(ova.Ova, '_create_file_handle')
    def test_init_extracts_ovf(self, fake_create_file_handle, fake_tarfile):
        """Ova - ``__init__`` extracts the OVF file from the OVA"""
        fake_tar = MagicMock()
        fake_tar.getnames.return_value = ['some.vmdk', 'the.ovf']
        fake_tar.extractfile.return_value.read.return_value.decode.return_value = 'woot'
        fake_tarfile.open.return_value = fake_tar
        my_ova = ova.Ova('/some/file')

        expected = 'woot'
        result = my_ova._ovf

        self.assertEqual(expected, result)

    @patch.object(ova, 'tarfile')
    @patch.object(ova.Ova, '_create_file_handle')
    def test_init_extracts_vmdks(self, fake_create_file_handle, fake_tarfile):
        """Ova - ``__init__`` extracts the OVF file from the OVA"""
        fake_tar = MagicMock()
        fake_tar.getnames.return_value = ['some.vmdk', 'the.ovf']
        fake_tar.extractfile.return_value.read.return_value.decode.return_value = 'woot'
        fake_tarfile.open.return_value = fake_tar
        my_ova = ova.Ova('/some/file')

        expected = ['some.vmdk']
        result = list(my_ova._disks.keys())

        self.assertEqual(expected, result)

    @patch.object(ova, 'FileHandle')
    @patch.object(ova.os.path, 'exists')
    @patch.object(ova, 'tarfile')
    def test_create_file_handle_filehandle(self, fake_tarfile, fake_exists, fake_filehandle):
        """Ova - ``_create_file_handle`` instantiates FileHandle if the supplied file exists"""
        fake_exists.return_value = True

        my_ova = ova.Ova("/some/file")

        self.assertTrue(fake_exists.called)
        self.assertTrue(fake_filehandle.called)

    @patch.object(ova, 'WebHandle')
    @patch.object(ova.os.path, 'exists')
    @patch.object(ova, 'tarfile')
    def test_create_file_handle_webhandle(self, fake_tarfile, fake_exists, fake_webhandle):
        """Ova - ``_create_file_handle`` instantiates WebHandle if the supplied file does not exist"""
        fake_exists.return_value = False

        my_ova = ova.Ova("http://some/file")

        self.assertTrue(fake_exists.called)
        self.assertTrue(fake_webhandle.called)

    @patch.object(ova, 'tarfile')
    @patch.object(ova.Ova, '_create_file_handle')
    def test_close(self, fake_create_file_handle, fake_tarfile):
        """Ova - ``close`` closes the file handle"""
        fake_tar = MagicMock()
        fake_tar.getnames.return_value = ['some.vmdk', 'the.ovf']
        fake_tar.extractfile.return_value.read.return_value.decode.return_value = 'woot'
        fake_tarfile.open.return_value = fake_tar
        my_ova = ova.Ova('/some/file')

        my_ova.close()

        self.assertTrue(my_ova._handle.close.called)

    @patch.object(ova, 'tarfile')
    @patch.object(ova.Ova, '_create_file_handle')
    def test_ovf_property(self, fake_create_file_handle, fake_tarfile):
        """Ova - ``ovf`` property returns the contents of the OVF file within the OVA"""
        fake_tar = MagicMock()
        fake_tar.getnames.return_value = ['some.vmdk', 'the.ovf']
        fake_tar.extractfile.return_value.read.return_value.decode.return_value = 'woot'
        fake_tarfile.open.return_value = fake_tar
        my_ova = ova.Ova('/some/file')

        expected = 'woot'
        result = my_ova.ovf

        self.assertEqual(expected, result)

    @patch.object(ova, 'tarfile')
    @patch.object(ova.Ova, '_create_file_handle')
    def test_ovf_property_ro(self, fake_create_file_handle, fake_tarfile):
        """Ova - ``ovf`` property is read-only"""
        fake_tar = MagicMock()
        fake_tar.getnames.return_value = ['some.vmdk', 'the.ovf']
        fake_tar.extractfile.return_value.read.return_value.decode.return_value = 'woot'
        fake_tarfile.open.return_value = fake_tar
        my_ova = ova.Ova('/some/file')

        with self.assertRaises(AttributeError):
            my_ova.ovf = 'doh'

    @patch.object(ova, 'tarfile')
    @patch.object(ova.Ova, '_create_file_handle')
    def test_networks_property(self, fake_create_file_handle, fake_tarfile):
        """Ova - ``networks`` property parses the OVF and returns all the network names"""
        fake_tar = MagicMock()
        fake_tar.getnames.return_value = ['some.vmdk', 'the.ovf']
        fake_tar.extractfile.return_value.read.return_value.decode.return_value = 'Network ovf:name="wooter"\nNetwork ovf:name="anotherWoot"'
        fake_tarfile.open.return_value = fake_tar
        my_ova = ova.Ova('/some/file')

        expected = ['wooter', 'anotherWoot']
        result = my_ova.networks

        self.assertEqual(expected, result)

    @patch.object(ova, 'tarfile')
    @patch.object(ova.Ova, '_create_file_handle')
    def test_networks_property_ro(self, fake_create_file_handle, fake_tarfile):
        """Ova - ``networks`` property is read-only"""
        fake_tar = MagicMock()
        fake_tar.getnames.return_value = ['some.vmdk', 'the.ovf']
        fake_tar.extractfile.return_value.read.return_value.decode.return_value = 'Network ovf:name="wooter"\nNetwork ovf:name="anotherWoot"'
        fake_tarfile.open.return_value = fake_tar
        my_ova = ova.Ova('/some/file')

        with self.assertRaises(AttributeError):
            my_ova.networks = 'doh'

    @patch.object(ova, 'tarfile')
    @patch.object(ova.Ova, '_create_file_handle')
    def test_vmdks_property(self, fake_create_file_handle, fake_tarfile):
        """Ova - ``vmdks`` property returns the disk names"""
        fake_tar = MagicMock()
        fake_tar.getnames.return_value = ['some.vmdk', 'the.ovf']
        fake_tar.extractfile.return_value.read.return_value.decode.return_value = 'woot'
        fake_tarfile.open.return_value = fake_tar
        my_ova = ova.Ova('/some/file')

        expected = ['some.vmdk']
        result = my_ova.vmdks

        self.assertEqual(expected, result)

    @patch.object(ova, 'tarfile')
    @patch.object(ova.Ova, '_create_file_handle')
    def test_vmdks_property_ro(self, fake_create_file_handle, fake_tarfile):
        """Ova - ``vmdks`` property is read-only"""
        fake_tar = MagicMock()
        fake_tar.getnames.return_value = ['some.vmdk', 'the.ovf']
        fake_tar.extractfile.return_value.read.return_value.decode.return_value = 'woot'
        fake_tarfile.open.return_value = fake_tar
        my_ova = ova.Ova('/some/file')

        with self.assertRaises(AttributeError):
            my_ova.vmdks = ['doh']

    @patch.object(ova, 'tarfile')
    @patch.object(ova.Ova, '_create_file_handle')
    def test_deploy_progress_property(self, fake_create_file_handle, fake_tarfile):
        """Ova - ``deploy_progress`` property returns the deploy progress"""
        fake_tar = MagicMock()
        fake_tar.getnames.return_value = ['some.vmdk', 'the.ovf']
        fake_tar.extractfile.return_value.read.return_value.decode.return_value = 'woot'
        fake_tarfile.open.return_value = fake_tar
        my_ova = ova.Ova('/some/file')
        my_ova._prog = 50

        result = my_ova.deploy_progress
        expected = 50

        self.assertEqual(result, expected)

    @patch.object(ova, 'tarfile')
    @patch.object(ova.Ova, '_create_file_handle')
    def test_deploy_progress_property_ro(self, fake_create_file_handle, fake_tarfile):
        """Ova - ``deploy_progress`` property is read-only"""
        fake_tar = MagicMock()
        fake_tar.getnames.return_value = ['some.vmdk', 'the.ovf']
        fake_tar.extractfile.return_value.read.return_value.decode.return_value = 'woot'
        fake_tarfile.open.return_value = fake_tar
        my_ova = ova.Ova('/some/file')

        with self.assertRaises(AttributeError):
            my_ova.deploy_progress = 1

    @patch.object(ova, 'tarfile')
    @patch.object(ova.Ova, '_create_file_handle')
    def test_get_device_url(self, fake_create_file_handle, fake_tarfile):
        """Ova - ``_get_device_url`` returns the upload URL when the import key matches"""
        fake_tar = MagicMock()
        fake_tar.getnames.return_value = ['some.vmdk', 'the.ovf']
        fake_tar.extractfile.return_value.read.return_value.decode.return_value = 'woot'
        fake_tarfile.open.return_value = fake_tar
        fake_device1 = MagicMock()
        fake_device1.importKey = 'foo'
        fake_device1.url = 'https://foo'
        fake_device2 = MagicMock()
        fake_device2.importKey = 'bar'
        fake_device2.url = 'https://bar'
        fake_lease = MagicMock()
        fake_lease.info.deviceUrl = [fake_device1, fake_device2]
        fake_file_item = MagicMock()
        fake_file_item.deviceId = 'bar'
        my_ova = ova.Ova('/some/file')
        my_ova._lease = fake_lease

        result = my_ova._get_device_url(fake_file_item)
        expected = 'https://bar'

        self.assertEqual(result, expected)

    @patch.object(ova, 'tarfile')
    @patch.object(ova.Ova, '_create_file_handle')
    def test_get_device_url_raises(self, fake_create_file_handle, fake_tarfile):
        """Ova - ``_get_device_url`` raises RuntimeError if nothing matches"""
        fake_tar = MagicMock()
        fake_tar.getnames.return_value = ['some.vmdk', 'the.ovf']
        fake_tar.extractfile.return_value.read.return_value.decode.return_value = 'woot'
        fake_tarfile.open.return_value = fake_tar
        fake_device1 = MagicMock()
        fake_device1.importKey = 'foo'
        fake_device1.url = 'https://foo'
        fake_lease = MagicMock()
        fake_lease.info.deviceUrl = [fake_device1]
        fake_file_item = MagicMock()
        fake_file_item.deviceId = 'bar'
        my_ova = ova.Ova('/some/file')
        my_ova._lease = fake_lease

        with self.assertRaises(RuntimeError):
            my_ova._get_device_url(fake_file_item)

    @patch.object(ova.Ova, '_reset')
    @patch.object(ova.Ova, '_chime_progress')
    @patch.object(ova.Ova, '_upload_disk')
    @patch.object(ova, 'tarfile')
    @patch.object(ova.Ova, '_create_file_handle')
    def test_deploy(self, fake_create_file_handle, fake_tarfile, fake_upload_disk, fake_chime_progress, fake_reset):
        """Ova - ``deploy`` happy path test"""
        fake_tar = MagicMock()
        fake_tar.getnames.return_value = ['some.vmdk', 'the.ovf']
        fake_tar.extractfile.return_value.read.return_value.decode.return_value = 'woot'
        fake_tarfile.open.return_value = fake_tar
        fake_lease = MagicMock()
        fake_deploy_spec = MagicMock()
        fake_deploy_spec.fileItem = [MagicMock()]
        my_ova = ova.Ova('/some/file')

        my_ova.deploy(fake_deploy_spec, fake_lease, 'my-vcenter-host')

        self.assertTrue(fake_upload_disk.called)
        self.assertTrue(fake_reset.called)

    @patch.object(ova.Ova, '_reset')
    @patch.object(ova.Ova, '_chime_progress')
    @patch.object(ova.Ova, '_upload_disk')
    @patch.object(ova, 'tarfile')
    @patch.object(ova.Ova, '_create_file_handle')
    def test_deploy_method_fault(self, fake_create_file_handle, fake_tarfile, fake_upload_disk, fake_chime_progress, fake_reset):
        """Ova - ``deploy`` aborts if vmold.MethodFault is raised"""
        fake_tar = MagicMock()
        fake_tar.getnames.return_value = ['some.vmdk', 'the.ovf']
        fake_tar.extractfile.return_value.read.return_value.decode.return_value = 'woot'
        fake_tarfile.open.return_value = fake_tar
        fake_lease = MagicMock()
        fake_deploy_spec = MagicMock()
        fake_deploy_spec.fileItem = [MagicMock()]
        fake_upload_disk.side_effect = vmodl.MethodFault()
        my_ova = ova.Ova('/some/file')

        with self.assertRaises(vmodl.MethodFault):
            my_ova.deploy(fake_deploy_spec, fake_lease, 'my-vcenter-host')

        self.assertTrue(fake_lease.Abort.called)

    @patch.object(ova.Ova, '_reset')
    @patch.object(ova.Ova, '_chime_progress')
    @patch.object(ova.Ova, '_upload_disk')
    @patch.object(ova, 'tarfile')
    @patch.object(ova.Ova, '_create_file_handle')
    def test_deploy_exception(self, fake_create_file_handle, fake_tarfile, fake_upload_disk, fake_chime_progress, fake_reset):
        """Ova - ``deploy`` abofts if any Exception is raised"""
        fake_tar = MagicMock()
        fake_tar.getnames.return_value = ['some.vmdk', 'the.ovf']
        fake_tar.extractfile.return_value.read.return_value.decode.return_value = 'woot'
        fake_tarfile.open.return_value = fake_tar
        fake_lease = MagicMock()
        fake_deploy_spec = MagicMock()
        fake_deploy_spec.fileItem = [MagicMock()]
        fake_upload_disk.side_effect = Exception('testing')
        my_ova = ova.Ova('/some/file')

        with self.assertRaises(Exception):
            my_ova.deploy(fake_deploy_spec, fake_lease, 'my-vcenter-host')

        self.assertTrue(fake_lease.Abort.called)

    @patch.object(ova, 'tarfile')
    @patch.object(ova.Ova, '_create_file_handle')
    def test_reset(self, fake_create_file_handle, fake_tarfile):
        """Ova - ``_reset`` preps the OVA for deployment again"""
        fake_tar = MagicMock()
        fake_tar.getnames.return_value = ['some.vmdk', 'the.ovf']
        fake_tar.extractfile.return_value.read.return_value.decode.return_value = 'woot'
        fake_tarfile.open.return_value = fake_tar
        my_ova = ova.Ova('/some/file')
        my_ova._spec = 'some spec'
        my_ova._lease = 'some lease'
        my_ova._host = 'some-vc-host'
        my_ova._prog = 100

        my_ova._reset()

        self.assertEqual(my_ova._spec, None)
        self.assertEqual(my_ova._lease, None)
        self.assertEqual(my_ova._host, None)
        self.assertEqual(my_ova._prog, None)
        self.assertTrue(my_ova._disks['some.vmdk'].seek.called)

    @patch.object(ova.Ova, '_get_device_url')
    @patch.object(ova, 'urlopen')
    @patch.object(ova, 'tarfile')
    @patch.object(ova.Ova, '_create_file_handle')
    def test_upload_disk(self, fake_create_file_handle, fake_tarfile, fake_urlopen, fake_get_device_url):
        """Ova - ``_upload_disk`` preps the OVA for deployment again"""
        fake_tar = MagicMock()
        fake_tar.getnames.return_value = ['some.vmdk', 'the.ovf']
        fake_tar.extractfile.return_value.read.return_value.decode.return_value = 'woot'
        fake_tarfile.open.return_value = fake_tar
        fake_disk = MagicMock()
        fake_disk.path = 'some.vmdk'
        fake_get_device_url.return_value = 'https://localhost'
        my_ova = ova.Ova('/some/file')

        my_ova._upload_disk(fake_disk)

        self.assertTrue(fake_urlopen.called)

    @patch.object(ova, 'urlopen')
    @patch.object(ova, 'tarfile')
    @patch.object(ova.Ova, '_create_file_handle')
    def test_upload_disk_none(self, fake_create_file_handle, fake_tarfile, fake_urlopen):
        """Ova - ``_upload_disk`` preps the OVA for deployment again"""
        fake_tar = MagicMock()
        fake_tar.getnames.return_value = ['some.vmdk', 'the.ovf']
        fake_tar.extractfile.return_value.read.return_value.decode.return_value = 'woot'
        fake_tarfile.open.return_value = fake_tar
        fake_disk = MagicMock()
        fake_disk.path = 'someOther.vmdk'
        my_ova = ova.Ova('/some/file')

        my_ova._upload_disk(fake_disk)

        self.assertFalse(fake_urlopen.called)

    def test_get_tarfile_size(self):
        """Ova - ``_get_tarfile_size`` returns size attribute on the component"""
        fake_component = MagicMock()
        fake_component.size = 10

        result = ova.Ova._get_tarfile_size(fake_component)
        expected = 10

        self.assertTrue(result, expected)

    def test_get_tarfile_size_no_attr(self):
        """Ova - ``_get_tarfile_size`` returns size of the component, even if the component has no size attribute"""
        class FakeComponent(object):
            def seek(self, a, b):
                return 15

        fake_component = FakeComponent()
        result = ova.Ova._get_tarfile_size(fake_component)
        expected = 15

        self.assertTrue(result, expected)

    @patch.object(ova, 'Timer')
    @patch.object(ova, 'tarfile')
    @patch.object(ova.Ova, '_create_file_handle')
    def test_chime_progress(self, fake_create_file_handle, fake_tarfile, fake_timer):
        """Ova - ``_chime_progress`` starts a Timer"""
        fake_tar = MagicMock()
        fake_tar.getnames.return_value = ['some.vmdk', 'the.ovf']
        fake_tar.extractfile.return_value.read.return_value.decode.return_value = 'woot'
        fake_tarfile.open.return_value = fake_tar
        my_ova = ova.Ova('/some/file')

        my_ova._chime_progress('some lease object')

        self.assertTrue(fake_timer.called)

    @patch.object(ova.Ova, '_chime_progress')
    @patch.object(ova, 'tarfile')
    @patch.object(ova.Ova, '_create_file_handle')
    def test_timer(self, fake_create_file_handle, fake_tarfile, fake_chime_progress):
        """Ova - ``_timer`` schedules another Timer while upload is still progressing"""
        fake_tar = MagicMock()
        fake_tar.getnames.return_value = ['some.vmdk', 'the.ovf']
        fake_tar.extractfile.return_value.read.return_value.decode.return_value = 'woot'
        fake_tarfile.open.return_value = fake_tar
        fake_lease = MagicMock()
        my_ova = ova.Ova('/some/file')

        my_ova._timer(fake_lease)

        self.assertTrue(fake_chime_progress.called)

    @patch.object(ova.Ova, '_chime_progress')
    @patch.object(ova, 'tarfile')
    @patch.object(ova.Ova, '_create_file_handle')
    def test_timer_done(self, fake_create_file_handle, fake_tarfile, fake_chime_progress):
        """Ova - ``_timer`` does not schedule another Timer when the upload is done"""
        fake_tar = MagicMock()
        fake_tar.getnames.return_value = ['some.vmdk', 'the.ovf']
        fake_tar.extractfile.return_value.read.return_value.decode.return_value = 'woot'
        fake_tarfile.open.return_value = fake_tar
        fake_lease = MagicMock()
        fake_lease.state = 'done'
        my_ova = ova.Ova('/some/file')

        my_ova._timer(fake_lease)

        self.assertFalse(fake_chime_progress.called)

    @patch.object(ova.Ova, '_chime_progress')
    @patch.object(ova, 'tarfile')
    @patch.object(ova.Ova, '_create_file_handle')
    def test_timer_error(self, fake_create_file_handle, fake_tarfile, fake_chime_progress):
        """Ova - ``_timer`` does not schedule another Timer when the upload has failed"""
        fake_tar = MagicMock()
        fake_tar.getnames.return_value = ['some.vmdk', 'the.ovf']
        fake_tar.extractfile.return_value.read.return_value.decode.return_value = 'woot'
        fake_tarfile.open.return_value = fake_tar
        fake_lease = MagicMock()
        fake_lease.state = 'error'
        my_ova = ova.Ova('/some/file')

        my_ova._timer(fake_lease)

        self.assertFalse(fake_chime_progress.called)

    @patch.object(ova, 'sys')
    @patch.object(ova, 'tarfile')
    @patch.object(ova.Ova, '_create_file_handle')
    def test_timer_exception(self, fake_create_file_handle, fake_tarfile, fake_sys):
        """Ova - ``_timer`` aborts the upload if there's any Exceptions"""
        fake_tar = MagicMock()
        fake_tar.getnames.return_value = ['some.vmdk', 'the.ovf']
        fake_tar.extractfile.return_value.read.return_value.decode.return_value = 'woot'
        fake_tarfile.open.return_value = fake_tar
        fake_lease = MagicMock()
        fake_lease.Progress.side_effect = [Exception('testing')]
        my_ova = ova.Ova('/some/file')

        my_ova._timer(fake_lease)

        self.assertTrue(fake_lease.Abort.called)
        self.assertTrue(fake_sys.stderr.flush.called)

    @patch.object(ova.Ova, '_chime_progress')
    @patch.object(ova, 'tarfile')
    @patch.object(ova.Ova, '_create_file_handle')
    def test_timer_race(self, fake_create_file_handle, fake_tarfile, fake_chime_progress):
        """Ova - ``_timer`` handles race between upload completion and chiming progress"""
        fake_tar = MagicMock()
        fake_tar.getnames.return_value = ['some.vmdk', 'the.ovf']
        fake_tar.extractfile.return_value.read.return_value.decode.return_value = 'woot'
        fake_tarfile.open.return_value = fake_tar
        fake_lease = MagicMock()
        fake_lease.Progress.side_effect = [vmodl.fault.ManagedObjectNotFound()]
        my_ova = ova.Ova('/some/file')

        my_ova._timer(fake_lease)

        self.assertFalse(fake_lease.Abort.called)


class TestFileHandle(unittest.TestCase):
    """A set of test cases for the ``FileHandle`` object"""
    @patch.object(ova, 'os')
    @patch.object(ova, 'open')
    def test_init(self, fake_open, fake_os):
        """FileHandle - ``__init__`` sets the st_size attribute"""
        fake_os.stat.return_value.st_size = 100
        handle = ova.FileHandle('/not/a/file')
        expected = 100

        self.assertEqual(handle.st_size, expected)

    @patch.object(ova, 'os')
    @patch.object(ova, 'open')
    def test_del(self, fake_open, fake_os):
        """FileHandle - ``__del__`` closes the file handle"""
        fake_os.stat.return_value.st_size = 100
        handle = ova.FileHandle('/not/a/file')
        del handle

        self.assertTrue(fake_open.return_value.close.called)

    @patch.object(ova, 'os')
    @patch.object(ova, 'open')
    def test_close(self, fake_open, fake_os):
        """FileHandle - ``close`` closes the file handle"""
        fake_os.stat.return_value.st_size = 100
        handle = ova.FileHandle('/not/a/file')
        handle.close()

        self.assertTrue(fake_open.return_value.close.called)

    @patch.object(ova, 'os')
    @patch.object(ova, 'open')
    def test_tell(self, fake_open, fake_os):
        """FileHandle - ``tell`` proxies call to the file handle"""
        fake_os.stat.return_value.st_size = 100
        handle = ova.FileHandle('/not/a/file')

        handle.tell()

        self.assertTrue(fake_open.return_value.tell.called)

    @patch.object(ova, 'os')
    @patch.object(ova, 'open')
    def test_seek(self, fake_open, fake_os):
        """FileHandle - ``seek`` proxies call to the file handle"""
        fake_os.stat.return_value.st_size = 100
        handle = ova.FileHandle('/not/a/file')

        handle.seek(500)

        self.assertTrue(fake_open.return_value.seek.called)

    @patch.object(ova, 'os')
    @patch.object(ova, 'open')
    def test_seek_math(self, fake_open, fake_os):
        """FileHandle - ``seek`` updates the offset correctly"""
        fake_os.stat.return_value.st_size = 100
        handle = ova.FileHandle('/not/a/file')

        handle.seek(500)
        expected = 500

        self.assertEqual(handle.offset, expected)

    @patch.object(ova, 'os')
    @patch.object(ova, 'open')
    def test_seek_whence_1(self, fake_open, fake_os):
        """FileHandle - ``seek`` sums the offset when whence is 1"""
        fake_os.stat.return_value.st_size = 100
        handle = ova.FileHandle('/not/a/file')
        handle.offset = 100

        handle.seek(500, whence=1)
        expected = 600

        self.assertEqual(handle.offset, expected)

    @patch.object(ova, 'os')
    @patch.object(ova, 'open')
    def test_seek_whence_2(self, fake_open, fake_os):
        """FileHandle - ``seek`` subtracts the size and offset when whence is 2"""
        fake_os.stat.return_value.st_size = 100
        handle = ova.FileHandle('/not/a/file')

        handle.seek(50, whence=2)
        expected = 50

        self.assertEqual(handle.offset, expected)

    @patch.object(ova, 'os')
    @patch.object(ova, 'open')
    def test_read(self, fake_open, fake_os):
        """FileHandle - ``read`` proxies to the file handle"""
        fake_os.stat.return_value.st_size = 100
        handle = ova.FileHandle('/not/a/file')

        handle.read(100)

        self.assertTrue(fake_open.return_value.read.called)

    @patch.object(ova, 'os')
    @patch.object(ova, 'open')
    def test_seekable(self, fake_open, fake_os):
        """FileHandle - ``seekable`` is True"""
        fake_os.stat.return_value.st_size = 100
        handle = ova.FileHandle('/not/a/file')

        self.assertTrue(handle.seekable())

    @patch.object(ova, 'os')
    @patch.object(ova, 'open')
    def test_progress(self, fake_open, fake_os):
        """FileHandle - ``progress`` returns how much of the file has been read"""
        fake_os.stat.return_value.st_size = 10
        handle = ova.FileHandle('/not/a/file')
        handle.offset = 5

        result = handle.progress()
        expected = 50

        self.assertEqual(result, expected)


class TestWebHandle(unittest.TestCase):
    """A set of test cases for the ``WebHandle`` object"""
    @patch.object(ova, 'urlopen')
    def test_not_found(self, fake_urlopen):
        """WebHandle - ``__init__`` raises FileNotFoundError if the HTTP response isn't OK"""
        fake_resp = MagicMock()
        fake_resp.code = 404
        fake_urlopen.return_value = fake_resp

        with self.assertRaises(FileNotFoundError):
            ova.WebHandle('http://localhost/nothing')

    @patch.object(ova, 'urlopen')
    def test_no_accept_range(self, fake_urlopen):
        """WebHandle - ``__init__`` raises RuntimeError if the HTTP server doesn't support Range header"""
        fake_resp = MagicMock()
        fake_resp.code = 200
        fake_urlopen.return_value = fake_resp

        with self.assertRaises(RuntimeError):
            ova.WebHandle('http://localhost/nothing')

    @patch.object(ova, 'urlopen')
    def test_init_ok(self, fake_urlopen):
        """WebHandle - ``__init__`` happy path test"""
        fake_resp = MagicMock()
        fake_resp.code = 200
        fake_resp.getheaders.return_value = [('content-length', '10'),('accept-ranges', 'bytes')]
        fake_urlopen.return_value = fake_resp

        handle = ova.WebHandle('http://localhost/nothing')

        self.assertTrue(isinstance(handle, ova.WebHandle))
        self.assertEqual(handle.st_size, 10)

    @patch.object(ova, 'urlopen')
    def test_tell(self, fake_urlopen):
        """WebHandle - ``tell`` returns the offset value"""
        fake_resp = MagicMock()
        fake_resp.code = 200
        fake_resp.getheaders.return_value = [('content-length', '10'),('accept-ranges', 'bytes')]
        fake_urlopen.return_value = fake_resp

        handle = ova.WebHandle('http://localhost/nothing')
        expected = 0

        self.assertEqual(handle.tell(), expected)

    @patch.object(ova, 'urlopen')
    def test_seekable(self, fake_urlopen):
        """WebHandle - ``seekable`` returns True"""
        fake_resp = MagicMock()
        fake_resp.code = 200
        fake_resp.getheaders.return_value = [('content-length', '10'),('accept-ranges', 'bytes')]
        fake_urlopen.return_value = fake_resp

        handle = ova.WebHandle('http://localhost/nothing')

        self.assertTrue(handle.seekable())

    @patch.object(ova, 'urlopen')
    def test_seek(self, fake_urlopen):
        """WebHandle - ``seek`` returns the offset attribute"""
        fake_resp = MagicMock()
        fake_resp.code = 200
        fake_resp.getheaders.return_value = [('content-length', '10'),('accept-ranges', 'bytes')]
        fake_urlopen.return_value = fake_resp

        handle = ova.WebHandle('http://localhost/nothing')
        result = handle.seek(10)
        expected = handle.offset

        self.assertEqual(result, expected)

    @patch.object(ova, 'urlopen')
    def test_seek_whence_1(self, fake_urlopen):
        """WebHandle - ``seek`` returns the summed offset when param whence is 1"""
        fake_resp = MagicMock()
        fake_resp.code = 200
        fake_resp.getheaders.return_value = [('content-length', '10'),('accept-ranges', 'bytes')]
        fake_urlopen.return_value = fake_resp

        handle = ova.WebHandle('http://localhost/nothing')
        handle.offset = 5
        result = handle.seek(10, whence=1)
        expected = 15

        self.assertEqual(result, expected)

    @patch.object(ova, 'urlopen')
    def test_seek_whence_2(self, fake_urlopen):
        """WebHandle - ``seek`` returns the st_size minus the offset when whence is 2"""
        fake_resp = MagicMock()
        fake_resp.code = 200
        fake_resp.getheaders.return_value = [('content-length', '10'),('accept-ranges', 'bytes')]
        fake_urlopen.return_value = fake_resp

        handle = ova.WebHandle('http://localhost/nothing')
        result = handle.seek(5, whence=2)
        expected = 5

        self.assertEqual(result, expected)

    @patch.object(ova, 'urlopen')
    def test_read_math(self, fake_urlopen):
        """WebHandle - ``read`` adjusts the offset correctly"""
        fake_resp = MagicMock()
        fake_resp.code = 200
        fake_resp.getheaders.return_value = [('content-length', '10'),('accept-ranges', 'bytes')]
        fake_urlopen.return_value = fake_resp

        handle = ova.WebHandle('http://localhost/nothing')
        handle.read(100)
        expected = 100

        self.assertEqual(handle.offset, expected)

    @patch.object(ova, 'urlopen')
    def test_read_closes(self, fake_urlopen):
        """WebHandle - ``read`` closes the socket automatically"""
        fake_resp = MagicMock()
        fake_resp.code = 200
        fake_resp.getheaders.return_value = [('content-length', '10'),('accept-ranges', 'bytes')]
        fake_urlopen.return_value = fake_resp

        handle = ova.WebHandle('http://localhost/nothing')
        handle.read(100)

        self.assertTrue(fake_resp.close.called)

    @patch.object(ova, 'urlopen')
    def test_close(self, fake_urlopen):
        """WebHandle - ``close`` method is callable"""
        fake_resp = MagicMock()
        fake_resp.code = 200
        fake_resp.getheaders.return_value = [('content-length', '10'),('accept-ranges', 'bytes')]
        fake_urlopen.return_value = fake_resp

        handle = ova.WebHandle('http://localhost/nothing')
        result = handle.close()
        expected = None

        self.assertEqual(result, expected)

    @patch.object(ova, 'urlopen')
    def test_progress(self, fake_urlopen):
        """WebHandle - ``progress`` returns how much of the file has been read"""
        fake_resp = MagicMock()
        fake_resp.code = 200
        fake_resp.getheaders.return_value = [('content-length', '10'),('accept-ranges', 'bytes')]
        fake_urlopen.return_value = fake_resp


        handle = ova.WebHandle('http://localhost/nothing')
        handle.offset = 5
        result = handle.progress()
        expected = 50

        self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main()
