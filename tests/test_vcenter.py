# -*- coding: UTF-8 -*-
"""
A unit tests for the vCenter object
"""
import unittest
from unittest.mock import MagicMock, patch

from vlab_inf_common.vmware import vcenter


class FakeObj(object):
    """An object with arbitrary names and values for testing"""
    def __init__(self, **kwargs):
        for name, value in kwargs.items():
            setattr(self, name, value)


class TestMapObject(unittest.TestCase):
    """
    A suite of test cases for the ``_map_object`` function
    """

    def test_ok(self):
        """Verify that ``_map_object`` key is the object name, and the value is the object"""
        obj = FakeObj(name='bar')

        result = vcenter._map_object([obj])
        expected = {'bar' : obj}

        self.assertEqual(result, expected)


class vCenterBase(unittest.TestCase):
    @staticmethod
    def _fake_conn_factory(fake_entity):
        """For mocking away vCenter._conn"""
        fake_conn = MagicMock()
        fake_conn.RetrieveContent.return_value.viewManager.CreateContainerView.return_value = fake_entity
        return fake_conn


class TestvCenter(vCenterBase):
    """
    A suite of test cases for the vCenter object
    """
    @patch.object(vcenter, 'connect')
    def test_with(self, fake_connect):
        """vCenter - supports use of the ``with`` statement"""
        with vcenter.vCenter(host='localhost', user='bob', password='iLoveKats') as vc:
            pass

        self.assertTrue(fake_connect.Disconnect.called)

    @patch.object(vcenter, 'connect')
    def test_get_by_type_non_iterable(self, fake_connect):
        """vCenter - get_by_type works when given a non-iterable object"""
        fake_entity = MagicMock()
        fake_entity.view = 'woot'
        vc = vcenter.vCenter(host='localhost', user='bob', password='iLoveKats')
        vc._conn = self._fake_conn_factory(fake_entity)

        result = vc.get_by_type(vcenter.vim.Network)
        expected = 'woot'

        self.assertEqual(result, expected)

    @patch.object(vcenter, 'connect')
    def test_get_by_type(self, fake_connect):
        """vCenter - get_by_type works when given an iterable object"""
        fake_entity = MagicMock()
        fake_entity.view = 'woot'
        vc = vcenter.vCenter(host='localhost', user='bob', password='iLoveKats')
        vc._conn = self._fake_conn_factory(fake_entity)

        result = vc.get_by_type([vcenter.vim.Network])
        expected = 'woot'

        self.assertEqual(result, expected)

    @patch.object(vcenter, 'connect')
    def test_get_by_name(self, fake_connect):
        """vCenter - get_by_name when param ``parent`` is None"""
        fake_obj = FakeObj(name='foo')
        fake_entity = MagicMock()
        fake_entity.view = [fake_obj]
        vc = vcenter.vCenter(host='localhost', user='bob', password='iLoveKats')
        vc._conn = self._fake_conn_factory(fake_entity)

        result = vc.get_by_name(vimtype=vcenter.vim.Network, name='foo')

        self.assertEqual(result, fake_obj)

    @patch.object(vcenter, 'connect')
    def test_get_by_name_value_error(self, fake_connect):
        """vCenter - get_by_name raises ValueError when the object is not found"""
        fake_obj = FakeObj(name='foo')
        fake_entity = MagicMock()
        fake_entity.view = [fake_obj]
        vc = vcenter.vCenter(host='localhost', user='bob', password='iLoveKats')
        vc._conn = self._fake_conn_factory(fake_entity)

        self.assertRaises(ValueError, vc.get_by_name, vimtype=vcenter.vim.Network, name='bar')

    @patch.object(vcenter, 'connect')
    def test_get_by_name_parent(self, fake_connect):
        """vCenter - get_by_name when param ``parent`` is defined"""
        fake_obj1 = FakeObj(name='foo')
        fake_obj2 = FakeObj(name='bar', childEntity=[fake_obj1])
        fake_entity = MagicMock()
        fake_entity.view = [fake_obj1, fake_obj2]
        vc = vcenter.vCenter(host='localhost', user='bob', password='iLoveKats')
        vc._conn = self._fake_conn_factory(fake_entity)

        result = vc.get_by_name(vimtype=vcenter.vim.Network, name='foo', parent='bar')

        self.assertEqual(result, fake_obj1)

    @patch.object(vcenter, 'connect')
    def test_create_vm_folder(self, fake_connect):
        """vCenter - ``create_vm_folder`` can create a root folder"""
        fake_entity = MagicMock()
        vc = vcenter.vCenter(host='localhost', user='bob', password='iLoveKats')
        vc._conn = self._fake_conn_factory(fake_entity)

        result = vc.create_vm_folder('/foo')

        self.assertEqual(result, None)

    @patch.object(vcenter.vCenter, 'get_by_name')
    @patch.object(vcenter, 'connect')
    def test_create_vm_folder_datacenter(self, fake_connect, fake_get_by_name):
        """vCenter - ``create_vm_folder`` accepts the datacenter as a param"""
        fake_entity = MagicMock()
        fake_entity.name = 'someDC'
        vc = vcenter.vCenter(host='localhost', user='bob', password='iLoveKats')
        vc._conn = self._fake_conn_factory(fake_entity)
        vc.content.rootFolder.childEntity = [fake_entity]

        result = vc.create_vm_folder('/foo/bar', datacenter='someDC')

        self.assertEqual(result, None)

    @patch.object(vcenter.vCenter, 'get_by_name')
    @patch.object(vcenter, 'connect')
    def test_create_vm_folder_runtime_error(self, fake_connect, fake_get_by_name):
        """vCenter - ``create_vm_folder`` raises RuntimeError if no datacenter found"""
        fake_entity = MagicMock()
        fake_entity.name = 'someOtherDC'
        vc = vcenter.vCenter(host='localhost', user='bob', password='iLoveKats')
        vc._conn = self._fake_conn_factory(fake_entity)
        vc.content.rootFolder.childEntity = [fake_entity]

        with self.assertRaises(RuntimeError):
            vc.create_vm_folder('/foo/bar', datacenter='someDC')

    @patch.object(vcenter.vCenter, 'get_by_name')
    @patch.object(vcenter, 'connect')
    def test_get_vm_folder_raises(self, fake_connect, fake_get_by_name):
        """vCenter - ``get_vm_folder`` raises FileNotFoundError when the folder doesn't exist"""
        fake_entity = MagicMock()
        vc = vcenter.vCenter(host='localhost', user='bob', password='iLoveKats')
        vc._conn = self._fake_conn_factory(fake_entity)

        with self.assertRaises(FileNotFoundError):
            vc.get_vm_folder('/foo/bar')


class TestvCenterProperties(vCenterBase):

    @patch.object(vcenter, 'connect')
    def _verify_read_only(self, the_property, fake_connect):
        """Reduce boiler plate in testing read-only properites"""
        fake_entity = MagicMock()
        vc = vcenter.vCenter(host='localhost', user='bob', password='iLoveKats')
        vc._conn = self._fake_conn_factory(fake_entity)

        with self.assertRaises(AttributeError):
            setattr(vc, the_property, 'woot')

    @patch.object(vcenter, 'connect')
    def _verify_mapped_objects(self, the_property, fake_connect):
        """Reduce boiler plate in testing properties that return a dict of objects"""
        fake_entity = MagicMock()
        obj = FakeObj(name='bar')
        fake_entity.view = [obj]
        vc = vcenter.vCenter(host='localhost', user='bob', password='iLoveKats')
        vc._conn = self._fake_conn_factory(fake_entity)

        result = getattr(vc, the_property)
        expected = {'bar': obj}

        self.assertEqual(result, expected)

    @patch.object(vcenter, 'connect')
    def test_content_property(self, fake_connect):
        """vCenter - ``content`` property returns RetrieveContent"""
        fake_entity = MagicMock()
        vc = vcenter.vCenter(host='localhost', user='bob', password='iLoveKats')
        vc._conn = self._fake_conn_factory(fake_entity)

        vc.content

        self.assertTrue(vc._conn.RetrieveContent.called)

    @patch.object(vcenter, 'connect')
    def test_ovf_manager_property(self, fake_connect):
        """vCenter - ``ovf_manager`` pulls the ovfManager property off the content"""
        fake_entity = MagicMock()
        vc = vcenter.vCenter(host='localhost', user='bob', password='iLoveKats')
        vc._conn = self._fake_conn_factory(fake_entity)

        result = vc.ovf_manager

        self.assertEqual(vc._conn.content.ovfManager, result)

    def test_data_centers_property(self):
        """vCenter - ``data_centers`` returns a dictionary"""
        self._verify_mapped_objects('data_centers')

    @patch.object(vcenter, 'connect')
    def test_resource_pools_property(self, fake_connect):
        """vCenter - ``resource_pools`` returns a dictionary"""
        fake_entity = MagicMock()
        obj = FakeObj(name='bar')
        obj.resourcePool = 'baz'
        fake_entity.view = [obj]
        vc = vcenter.vCenter(host='localhost', user='bob', password='iLoveKats')
        vc._conn = self._fake_conn_factory(fake_entity)

        result = vc.resource_pools
        expected = {'bar': 'baz'}

        self.assertEqual(result, expected)

    def test_datastores_property(self):
        """vCenter - ``datastores`` returns a dictionary"""
        self._verify_mapped_objects('datastores')

    def test_host_systems_property(self):
        """vCenter - ``host_systems`` returns a dictionary"""
        self._verify_mapped_objects('host_systems')

    def test_networks_property(self):
        """vCenter - ``networks`` returns a dictionary"""
        self._verify_mapped_objects('networks')

    def test_content_property_ro(self):
        """vCenter - ``content`` is a read-only property"""
        self._verify_read_only('content')

    def test_data_centers_property_ro(self):
        """vCenter - ``data_centers`` is a read-only property"""
        self._verify_read_only('data_centers')

    def test_resource_pools_property_ro(self):
        """vCenter - ``resource_pools`` is a read-only property"""
        self._verify_read_only('resource_pools')

    def test_datastores_property_ro(self):
        """vCenter - ``datastores`` is a read-only property"""
        self._verify_read_only('datastores')

    def test_host_systems_property_ro(self):
        """vCenter - ``host_systems`` is a read-only property"""
        self._verify_read_only('host_systems')

    def test_networks_property_ro(self):
        """vCenter - ``networks`` is a read-only property"""
        self._verify_read_only('networks')

    def test_ovf_manager_property_ro(self):
        """vCenter - ``ovf_manager`` is a read-only property"""
        self._verify_read_only('ovf_manager')

    def test_switches_property(self):
        """vCenter - ``dv_switches`` returns a dictionary"""
        self._verify_mapped_objects('dv_switches')

    def test_switches_property_ro(self):
        """vCenter - ``dv_switches`` is a read-only property"""
        self._verify_read_only('dv_switches')


if __name__ == '__main__':
    unittest.main()
