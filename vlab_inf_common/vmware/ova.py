# -*- coding: UTF-8 -*-
"""
This module is for working with, and manipulating OVA files.
"""
import re
import os
import sys
import tarfile
import traceback
from threading import Timer
from urllib.request import urlopen, Request

from pyVmomi import vmodl

from vlab_inf_common.ssl_context import get_context


class Ova(object):
    """
    Represents an OVA file, and the contents within it.
    """
    def __init__(self, ovafile):
        """Performs necessary initialization, opening the OVA file,
        processing the files and reading the embedded ovf file.

        :param ovafile: **Required** The file path or URL of an OVA file
        :type ovafile: String
        """
        self._spec = None
        self._lease = None
        self._host = None
        self._handle = self._create_file_handle(ovafile)
        self._tar = tarfile.open(fileobj=self._handle)
        self._ovf = None
        self._prog = None
        self._disks = {}
        for file_item in self._tar.getnames():
            if file_item.endswith('.vmdk'):
                self._disks[file_item] = self._tar.extractfile(file_item)
            elif file_item.endswith('.ovf'):
                self._ovf = self._tar.extractfile(file_item).read().decode()

    def _create_file_handle(self, ovafile):
        """Abstraction so file paths and URLs can both work

        :param ovafile: **Required** The file path or URL of an OVA file
        :type ovafile: String
        """
        if os.path.exists(ovafile):
            return FileHandle(ovafile)
        else:
            return WebHandle(ovafile)

    def close(self):
        """Close the connection to the OVA file.

        Once called, you must create a new OVA object in order for the ``deploy``
        method to work.
        """
        self._handle.close()

    @property
    def ovf(self):
        """Return the XML that describes the OVA"""
        return self._ovf

    @property
    def networks(self):
        """Return a list of network names that a VM has configured"""
        # This is actually easier than dealing with XML namespaces...
        ntwks = re.findall('Network ovf:name=[\w\ \"]{1,50}', self.ovf)
        # Gives us output like this
        # ['Network ovf:name="some network name"']
        # so let's hack the name out of that string
        return [x.split('=')[1].replace('"', '') for x in ntwks]

    @property
    def vmdks(self):
        """Return a list of VMDK file names within the OVA"""
        return list(self._disks.keys())

    @property
    def deploy_progress(self):
        """Display the current progress of deploying a VM/vApp from the OVA"""
        return self._prog

    def _get_device_url(self, file_item):
        """Obtain the URL to use when uploading a specific VM/vApp component

        :param disk: **Required** The VMDK to get the upload URL for
        :type disk: String: vim.OvfManager.FileItem
        """
        for device_url in self._lease.info.deviceUrl:
            if device_url.importKey == file_item.deviceId:
                return device_url.url
        else:
            err = "Failed to find deviceUrl for file {}".format(file_item.path)
            raise RuntimeError(err)

    def deploy(self, deploy_spec, lease, host):
        """Create a new VM based off the OVA

        :param deploy_spec: **Required** The OVA deployment spec
        :type deploy_spec: vim.OvfManager.CreateImportSpecResult

        :param lease: **Required** The vSphere lease that enables VM/vApp creation
        :type lease: vim.HttpNfcLease

        :param host: **Required** The FQDN for vSphere
        :type host: String
        """
        self._spec = deploy_spec
        self._lease = lease
        self._host = host
        try:
            self._chime_progress(lease)
            for file_item in self._spec.fileItem:
                self._upload_disk(file_item)
            self._lease.Progress(100)
            self._lease.Complete()
        except vmodl.MethodFault as doh:
            lease.Abort(doh)
            raise
        except Exception as doh:
            lease.Abort(vmodl.fault.SystemError(reason=str(doh)))
            raise
        finally:
            self._reset()

    def _reset(self):
        """Reset after deployment"""
        self._spec = None
        self._lease = None
        self._host = None
        self._prog = None
        for disk in self._disks.values():
            disk.seek(0, 0)

    def _upload_disk(self, disk):
        """
        Upload an individual disk from the OVA

        :param disk: **Required** The name of the disk within the OVF file
        :type disk: String
        """
        vmdk = self._disks.get(disk.path, None)
        if vmdk is None:
            return
        url = self._get_device_url(disk)
        headers = {'Content-length': self._get_tarfile_size(vmdk),
                   'Content-Type': 'application/x-vnd.vmware-streamVmdk'}
        # Create the request object
        req = Request(url, method='POST', data=vmdk, headers=headers)
        # Start uploading the disk
        urlopen(req, context=get_context())

    @staticmethod
    def _get_tarfile_size(component):
        """Enables accurate reporting of the Content-Length header when uploading a VM/vApp component

        :param component: The name of the VM/vApp component
        :type component: String
        """
        if hasattr(component, 'size'):
            size = component.size
        else:
            size = component.seek(0, 2)
            # set the cursor back to the start of the file
            component.seek(0, 0)
        return size

    def _chime_progress(self, lease):
        """
        A simple way to keep updating progress while the vmdks are uploading.
        """
        Timer(5, self._timer, args=[lease]).start()

    def _timer(self, lease):
        """
        Update the progress and reschedule the timer if not complete.
        """
        try:
            prog = self._handle.progress()
            lease.Progress(prog)
            if lease.state not in ('done', 'error'):
                self._chime_progress(lease)
            self._prog = prog
        except vmodl.fault.ManagedObjectNotFound:
            # race between upload completing, and Timer chiming
            pass
        except Exception:
            # Don't start a new chimer, write the traceback to the console,
            # and kill the deploy. Might take a few moments for the deploy
            # method to terminate
            doh = traceback.format_exc()
            sys.stderr.write('{}\n'.format(doh))
            sys.stderr.flush()
            lease.Abort(vmodl.fault.SystemError(reason='Lease chimer failure:\n{}'.format(doh)))


class FileHandle(object):
    """A local file based location for an OVA file.

    Enables the Ova object to treat local and remote OVAs the same.
    """
    def __init__(self, filename):
        self.filename = filename
        self.fh = open(filename, 'rb')

        self.st_size = os.stat(filename).st_size
        self.offset = 0

    def __del__(self):
        self.close()

    def close(self):
        self.fh.close()

    def tell(self):
        return self.fh.tell()

    def seek(self, offset, whence=0):
        if whence == 0:
            self.offset = offset
        elif whence == 1:
            self.offset += offset
        elif whence == 2:
            self.offset = self.st_size - offset

        return self.fh.seek(offset, whence)

    def seekable(self):
        return True

    def read(self, amount):
        self.offset += amount
        result = self.fh.read(amount)
        return result

    # A slightly more accurate percentage
    def progress(self):
        return int(100.0 * self.offset / self.st_size)


class WebHandle(object):
    """A remote HTTP based location for an OVA file

    Enables the Ova object to treat local and remote OVAs the same.
    """
    def __init__(self, url):
        self.url = url
        r = urlopen(url)
        if r.code != 200:
            version = os.path.splitext(os.path.basename(url))[0]
            error = 'Unknown version supplied: {}'.format(version)
            raise FileNotFoundError(error)
        self.headers = self._headers_to_dict(r)
        if 'accept-ranges' not in self.headers:
            err = "Server hosting remote OVA file does not support 'Accept-Ranges' HTTP header"
            raise RuntimeError(err)
        self.st_size = int(self.headers['content-length'])
        self.offset = 0

    def _headers_to_dict(self, resp):
        return {x.lower(): y.strip() for x,y in resp.getheaders()}

    def tell(self):
        return self.offset

    def seek(self, offset, whence=0):
        if whence == 0:
            self.offset = offset
        elif whence == 1:
            self.offset += offset
        elif whence == 2:
            self.offset = self.st_size - offset
        return self.offset

    def seekable(self):
        return True

    def read(self, amount):
        start = self.offset
        end = self.offset + amount - 1
        req = Request(self.url,
                      headers={'Range': 'bytes=%d-%d' % (start, end)})
        r = urlopen(req)
        self.offset += amount
        result = r.read(amount)
        r.close()
        return result

    def close(self):
        """For API parody with the the FileHandle class

        This method doesn't actually do anything. The URL socket is closed automatically.
        """
        pass

    # A slightly more accurate percentage
    def progress(self):
        return int(100.0 * self.offset / self.st_size)
