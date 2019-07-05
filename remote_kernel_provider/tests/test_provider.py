import json
import os
import re
import unittest

from os.path import join as pjoin
from jupyter_kernel_mgmt import discovery
from jupyter_core import paths
from uuid import UUID
from .utils import test_env
from ..provider import RemoteKernelProviderBase
from ..manager import RemoteKernelManager
from ..lifecycle_manager import RemoteKernelLifecycleManager


sample_kernel_json = {'argv': ['cat', '{kernel_id}', '{response_address}'],
                      'display_name': 'Test kernel', }

dummy_connection_info = {'stdin_port': 47557, 'ip': '172.16.18.82', 'control_port': 55288,
                         'hb_port': 55562, 'signature_scheme': 'hmac-sha256',
                         'key': 'e75863c2-4a8a-49b0-b6d2-9e23837d5bd1', 'comm_port': 36458,
                         'kernel_name': '', 'shell_port': 58031, 'transport': 'tcp', 'iopub_port': 52229}


def install_sample_kernel(kernels_dir, kernel_name='sample', kernel_file='kernel.json'):
    """install a sample kernel in a kernels directory"""
    sample_kernel_dir = pjoin(kernels_dir, kernel_name)
    os.makedirs(sample_kernel_dir)
    json_file = pjoin(sample_kernel_dir, kernel_file)
    with open(json_file, 'w') as f:
        json.dump(sample_kernel_json, f)
    return sample_kernel_dir


def is_uuid(uuid_to_test):
    try:
        UUID(uuid_to_test, version=4)
    except ValueError:
        return False
    return True


def is_response_address(addr_to_test):
    return re.match(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\:[0-9]{4,5}$", addr_to_test) is not None


class DummyKernelLifecycleManager(RemoteKernelLifecycleManager):
    """A dummy kernel provider for testing KernelFinder"""
    connection_info = None

    def launch_process(self, kernel_cmd, **kwargs):
        assert is_uuid(kernel_cmd[1])
        assert is_response_address(kernel_cmd[2])
        self.confirm_remote_startup()
        return self

    def confirm_remote_startup(self):
        self.connection_info = dummy_connection_info
        return True

    def shutdown_listener(self):
        pass

    def kill(self):
        pass


class DummyKernelProvider(RemoteKernelProviderBase):
    """A dummy kernelspec provider subclass for testing"""
    id = 'dummy'
    kernel_file = 'dummy_kspec.json'
    lifecycle_manager_classes = ['remote_kernel_provider.tests.test_provider.DummyKernelLifecycleManager']


class RemoteKernelProviderTests(unittest.TestCase):

    def setUp(self):
        self.env_patch = test_env()
        self.env_patch.start()
        self.sample_kernel_dir = install_sample_kernel(
            pjoin(paths.jupyter_data_dir(), 'kernels'))
        self.prov_sample1_kernel_dir = install_sample_kernel(
            pjoin(paths.jupyter_data_dir(), 'kernels'), 'dummy_kspec1', 'dummy_kspec.json')
        self.prov_sample2_kernel_dir = install_sample_kernel(
            pjoin(paths.jupyter_data_dir(), 'kernels'), 'dummy_kspec2', 'dummy_kspec.json')

        self.kernel_finder = discovery.KernelFinder(providers=[DummyKernelProvider()])

    def tearDown(self):
        self.env_patch.stop()

    def test_find_remote_kernel_provider(self):
        dummy_kspecs = list(self.kernel_finder.find_kernels())
        assert len(dummy_kspecs) == 2

        for name, spec in dummy_kspecs:
            assert name.startswith('dummy/dummy_kspec')
            assert spec['argv'] == sample_kernel_json['argv']

    def test_launch_remote_kernel_provider(self):
        conn_info, manager = self.kernel_finder.launch('dummy/dummy_kspec1')
        assert isinstance(manager, RemoteKernelManager)
        assert conn_info == dummy_connection_info
        assert manager.kernel_id is not None
        assert is_uuid(manager.kernel_id)

        manager.kill()
        assert manager.lifecycle_manager is not None
        assert isinstance(manager.lifecycle_manager, DummyKernelLifecycleManager)
        manager.cleanup()
        assert manager.lifecycle_manager is None
