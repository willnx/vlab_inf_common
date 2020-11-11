# -*- coding: UTF-8 -*-
"""
This module abstracts pyVmomi API to provide a human-friendly object for working
with vCenter.
"""
import collections

from pyVim import connect
from pyVmomi import vim

from vlab_inf_common.constants import const
from vlab_inf_common.ssl_context import get_context


def _map_object(result):
    """Return a more human friendly pyVmomi object, by creating a mapping of
    the objects name to the literal object.

    :Returns: Dictionary

    :param result: A series of pyVmomi objects, like vim.Network or vim.Datastore
    :type result: List
    """
    return {x.name: x for x in result}


class vCenter(object):
    """
    Interacts with the vSphere API via pyVmomi.
    The focus of this class is to make working with the vSphere API simpler, this
    comes a the cost of performance optimizations for correctness.

    :param host: **Required** The IP/FDQN to the vCenter server
    :type host: String

    :param user: **Required** The user account to authenticate with on the vCenter server
    :type user: String

    :param password: **Required** The user accounts password
    :type password: String

    :param port: The port to use when connecting to the vCenter server. Default is 443
    :type port: Integer

    :param verify: Set to False if you're using a self-signed TLS cert for vCenter
    :type verify: Boolean

    :param base_dir: The root directory to use when looking for objects. Defaults
                     to the main root directory in vCenter, or the value of the
                     environment variable ``INF_VCENTER_TOP_LVL_DIR``.
    :type base_dir: String
    """

    def __init__(self, host, user, password, port=443, base_dir=None):
        self._conn = connect.SmartConnect(host=host, user=user, pwd=password,
                                         port=port, sslContext=get_context())
        self._base_dir = base_dir if base_dir else const.INF_VCENTER_TOP_LVL_DIR
        self._net_cache = None

    def close(self):
        """
        Terminate the session to the vCenter server
        """
        connect.Disconnect(self._conn)

    def create_vm_folder(self, path, datacenter=None):
        """Make a folder to help organize virtual machines.

        .. note::

           Does not respect the ``base_dir`` attribute. Creates from the from root directory.

        :Returns: None

        :param path: The path to create. All folders will be created recursively
                     as needed. The path is always treated as an absolute path
                     from the root of a data center.
        :type path: String

        :param datacenter: The name of the data center to create the VM folder
                           under. If no value is supplied, the first data center
                           found will be used.
        :type datacenter: String
        """
        dir_names = path.strip('/').split('/')
        if datacenter is None:
            dc = self.content.rootFolder.childEntity[0]
        else:
            dc = [x for x in self.content.rootFolder.childEntity if x.name == datacenter]
            if dc:
                # b/c I want the object, not a list
                dc = dc[0]
        if not dc:
            raise RuntimeError('No datacenter named {}'.format(datacenter))

        current_dir = dc.vmFolder
        for folder in dir_names:
            for directory in current_dir.childEntity:
                if isinstance(directory, vim.Folder):
                    if folder == directory.name:
                        current_dir = directory
                        break
                    else:
                        # Folder, but not the name we're looking for
                        continue
            else:
                # no matching folder names, must be a new one!
                new_dir = current_dir.CreateFolder(folder)
                current_dir = new_dir

    def get_vm_folder(self, path, datacenter=None):
        """Recursive search through the provided path to find a specific VM folder.

        .. note::

           Does not respect the ``base_dir`` attribute. Searches from the from root directory.

        :Returns: vim.Folder

        :param path: The path to create. All folders will be created recursively
                     as needed. The path is always treated as an absolute path
                     from the root of a data center.
        :type path: String

        :param datacenter: The name of the data center to create the VM folder
                           under. If no value is supplied, the first data center
                           found will be used.
        :type datacenter: String

        """
        dir_names = path.strip('/').split('/')
        if datacenter is None:
            dc = self.content.rootFolder.childEntity[0]
        else:
            dc = [x for x in self.content.rootFolder.childEntity if x.name == datacenter]
            if dc:
                dc = dc[0]
        if not dc:
            raise RuntimeError('No datacenter named {}'.format(datacenter))

        current_dir = dc.vmFolder
        for folder in dir_names:
            for directory in current_dir.childEntity:
                if isinstance(directory, vim.Folder):
                    if folder == directory.name:
                        current_dir = directory
                        break
                    else:
                        # Folder, but not the name we're looking for
                        continue
            else:
                if path != '/':
                    msg = 'No such folder {} in path {}'.format(folder, path)
                    raise FileNotFoundError(msg)
        return current_dir

    def get_by_name(self, vimtype, name, parent=None):
        """
        Find an object in vCenter by object name from the defined base_dir

        :param vimtype: The category of object to find
        :type vimtype: pyVmomi.VmomiSupport.LazyType

        :param name: The name of the object
        :type name: String

        :param parent: (Optional) Filter under a parent folder below the base_dir
        :type parent: String
        """
        if parent is None:
            bucket = self.get_by_type(vimtype, root=self._base_dir)
        else:
            bucket = self.get_by_name(vim.Folder, parent).childEntity
        for item in bucket:
            if item.name == name:
                return item
        else:
            raise ValueError('Unable to locate object named {}'.format(name))

    def get_by_type(self, vimtype, root=None):
        """Find an object in vCenter by object type

        :Returns: pyVmomi.VmomiSupport.ManagedObject

        :param vimtype: The category of object to find
        :type vimtype: pyVmomi.VmomiSupport.LazyType

        :param root: The root directory to look for objects in. Defaults to searching
                     from the vCenter root directory.
        :type root: String
        """
        if not isinstance(vimtype, collections.Iterable):
            vimtype = [vimtype]
        if root is None:
            folder = self.content.rootFolder
        else:
            folder = self.get_vm_folder(path=self._base_dir)
        entity = self.content.viewManager.CreateContainerView(container=folder,
                                                              type=vimtype,
                                                              recursive=True)
        answer = entity.view
        entity.DestroyView()
        return answer

    @property
    def content(self):
        """
        The fleeting state of vCenter objects

        :Returns: pyVmomi.VmomiSupport.vim.ServiceInstanceContent
        """
        return self._conn.RetrieveContent()

    @property
    def data_centers(self):
        """The different datacenters configured within vSphere. The returned
        object is a mapping between the datacenter name, and the usable object
        vim.Datacenter.

        :Returns: Dictionary
        """
        return _map_object(self.get_by_type(vim.Datacenter))

    @property
    def resource_pools(self):
        """The different resource pools that VMs can be assigned to. The returned
        dictionary is a mapping between the pool name, and the usable object
        vim.ResourcePool.

        :Returns: Dictionary
        """
        pools = self.get_by_type(vim.ResourcePool)
        compute_clusters = self.get_by_type(vim.ComputeResource)
        mapping = _map_object(pools)
        compute_map = {x.name: x.resourcePool for x in compute_clusters}
        mapping.update(compute_map)
        return mapping

    @property
    def datastores(self):
        """The different storage locations that VMs can use. The dictionary returned
        is a mapping of the storage's name and the usable object vim.Datastore.

        :Returns: Dictionary
        """
        return _map_object(self.get_by_type(vim.StoragePod))

    @property
    def host_systems(self):
        """Basically, these are the different ESXi hosts. The dictionary returned
        is a mapping of the host name and the usable object vim.HostSystem.

        :Returns: Dictionary
        """
        return _map_object(self.get_by_type(vim.HostSystem))

    @property
    def networks(self):
        """The different networks that virtual machines can use. The dictionary
        returned is a mapping of the network name, and the usable object vim.Network.

        :Returns: Dictionary
        """
        if self._net_cache:
            return self._net_cache
        else:
            self._net_cache =_map_object(self.get_by_type(vim.Network))
            return self._net_cache

    @property
    def dv_switches(self):
        """The Distributed Virtual Switches configured. the dictionary returned
        is a mapping of the switch name, and the usable object vim.DistributedVirtualSwitch.

        :Returns: Dictionary
        """
        return _map_object(self.get_by_type(vim.DistributedVirtualSwitch))

    @property
    def ovf_manager(self):
        """
        An object for working with OVFs in vCenter

        :Returns: vim.OvfManager
        """
        return self._conn.content.ovfManager

    def cookie(self):
        """Obtain the cookie used to validate/authorize the connection to vCenter.

        :Returns: Dictionary
        """
        soap_cookie = self._conn._stub.cookie.split(';')[0]
        name, value = soap_cookie.split('=')
        value = value.replace('"', '') # the cookie value is surrounded by quotas.
        return {name: value}


    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
