##########################
vLab Infrastructure Common
##########################

This library centralizes logic for working with virtual infrastructure providers.

******
VMware
******

Builds upon the `pyVmomi <https://github.com/vmware/pyvmomi>`_ API bindings for vSphere
to create more *human friendly* objects like:

vCenter
=======

It's called vCenter because that's the ``host`` you'll connect to. This object
focuses more on interacting with Virtual Machines, than configuring the system.


Here's an example of what using the ``vCenter`` object is like:

.. code-block:: python

   from vlab_inf_common.vmware import vCenter, vim
   vc = vCenter(user='Alice', password='iLoveDogs', host='some-vcenter-server.corp')
   vc.networks
   {'front-end': 'vim.Network:network-14'}    # mapping of name -> object
   vc.create_vm_folder(path='/some/new/path') # recursively creates the whole path
   vms = vc.get_by_type(vim.VirtualMachine)
   vms
   (ManagedObject) [
   'vim.VirtualMachine:vm-15'
   ]


Ova
===

This object abstracts use of an OVA file when creating new Virtual Machines.
It handles both local paths and URLs for the OVA file location. Deploying the
OVA is a single method call (once you've obtained a spec and lease).

Here's an example of using the ``Ova`` object:

.. code-block:: python

   from vlab_inf_common.vmware import Ova
   ova = Ova('https://some-server/myMachine.ova')
   ova.networks
   ['eth0']
   ova.vmdks
   ['disk-1.vmdk', 'disk-2.vmdk']
   hasattr(ova, 'ovf') # b/c the ovf XML is too long to put in an example
   True


Here's an example using ``Ova`` and ``vCenter`` to deploy a new Virtual Machine
It's a bit long, but pyVmomi doesn't make it easy...

.. code-block:: python

   import time
   from vlab_inf_common.vmware import Ova, vCenter, vim
   vc = vCenter(user='Alice', password='iLoveDogs', host='some-vsphere-server.corp')
   ova = Ova('/some/path/myMachine.ova')
   my_folder = vc.get_vm_folder('/users/alice')
   network_map = vim.OvfManager.NetworkMapping()
   network_map.name = ova.networks[0]
   network_map.network = vc.networks['front-end'] # assuming you have a network named 'frond-end'
   resouce_pool = vc.resource_pool['users']       # assuming your pool name is 'users'
   datastore = vc.datastores['general']           # another assumption!
   host = list(vc.host_systems.values())[0]       # if you don't care which host you upload to
   spec_params = vim.OvfManager.CreateImportSpecParams(entityName='myNewVM', networkMapping=[network_map])
   spec = vc.ovf_manager.CreateImportSpec(ovfDescriptor=ova.ovf,
            resourcePool=resouce_pool, datastore=datastore, cisp=spec_params)
   lease = resource_pool.ImportVApp(spec.importSpec, folder=my_folder, host=host)
   for _ in range(30):
     if lease.state != 'ready':
       time.sleep(1)
     else:
       break
   print('starting deploy')
   ova.deploy(spec, lease, host.name)
   print('Upload complete')
   ova.close()


FAQ
===

**How do I deal with self-signed TLS certs in vCenter?**

Set the environment variable ``INF_VCENTER_VERIFY_CERT`` to anything, and
we'll use the default context created by the Python ssl lib. By default, we'll
ignore self-signed certs.
