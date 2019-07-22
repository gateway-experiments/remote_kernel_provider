import json
import os
import re

import jupyter_kernel_mgmt

from os.path import join as pjoin
from jupyter_core import paths
from uuid import UUID
from .utils import test_env
from ..provider import RemoteKernelProviderBase
from ..manager import RemoteKernelManager
from ..lifecycle_manager import RemoteKernelLifecycleManager


sample_kernel_json = {'argv': ['cat', '{kernel_id}', '{response_address}'], 'display_name': 'Test kernel', }

foo_kernel_json = {'argv': ['cat', '{kernel_id}', '{response_address}'], 'display_name': 'Test foo kernel', }

bar_kernel_json = {'argv': ['cat', '{kernel_id}', '{response_address}'], 'display_name': 'Test bar kernel', }

foo_connection_info = {'stdin_port': 47557, 'ip': '172.16.18.82', 'control_port': 55288,
                       'hb_port': 55562, 'signature_scheme': 'hmac-sha256',
                       'key': 'e75863c2-4a8a-49b0-b6d2-9e23837d5bd1', 'comm_port': 36458,
                       'kernel_name': '', 'shell_port': 58031, 'transport': 'tcp', 'iopub_port': 52229}


def install_sample_kernel(kernels_dir,
                          kernel_name='sample',
                          kernel_file='kernel.json',
                          json_content=sample_kernel_json):

    """install a sample kernel in a kernels directory"""
    sample_kernel_dir = pjoin(kernels_dir, kernel_name)
    os.makedirs(sample_kernel_dir, exist_ok=True)
    json_file = pjoin(sample_kernel_dir, kernel_file)
    with open(json_file, 'w') as f:
        json.dump(json_content, f)


def is_uuid(uuid_to_test):
    try:
        UUID(uuid_to_test, version=4)
    except ValueError:
        return False
    return True


def is_response_address(addr_to_test):
    return re.match(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}:[0-9]{4,5}$", addr_to_test) is not None


class FooKernelLifecycleManager(RemoteKernelLifecycleManager):
    """A fake kernel provider for testing KernelFinder"""
    connection_info = None

    def launch_process(self, kernel_cmd, **kwargs):
        assert is_uuid(kernel_cmd[1])
        assert is_response_address(kernel_cmd[2])
        self.confirm_remote_startup()
        return self

    def confirm_remote_startup(self):
        self.connection_info = foo_connection_info
        return True

    def shutdown_listener(self):
        pass

    def kill(self):
        pass


class BarKernelLifecycleManager(FooKernelLifecycleManager):
    pass  # Full inheritance from FooKernelLifecycleManager


class FooKernelProvider(RemoteKernelProviderBase):
    """A fake kernelspec provider subclass for testing"""
    id = 'foo'
    kernel_file = 'foo_kspec.json'
    lifecycle_manager_classes = ['remote_kernel_provider.tests.test_provider.FooKernelLifecycleManager']


class BarKernelProvider(RemoteKernelProviderBase):
    """A fake kernelspec provider subclass for testing"""
    id = 'bar'
    kernel_file = 'bar_kspec.json'
    lifecycle_manager_classes = ['remote_kernel_provider.tests.test_provider.BarKernelLifecycleManager']


class TestRemoteKernelProvider:

    env_patch = None
    kernel_finder = None

    @classmethod
    def setup_class(cls):
        cls.env_patch = test_env()
        cls.env_patch.start()
        install_sample_kernel(pjoin(paths.jupyter_data_dir(), 'kernels'))
        install_sample_kernel(pjoin(paths.jupyter_data_dir(), 'kernels'),
                              'foo_kspec', 'foo_kspec.json', foo_kernel_json)
        install_sample_kernel(pjoin(paths.jupyter_data_dir(), 'kernels'),
                              'foo_kspec2', 'foo_kspec.json', foo_kernel_json)

        # This kspec overlaps with foo/foo_kspec.  Will be located as bar/foo_kspec
        install_sample_kernel(pjoin(paths.jupyter_data_dir(), 'kernels'),
                              'foo_kspec', 'bar_kspec.json', bar_kernel_json)

        cls.kernel_finder = jupyter_kernel_mgmt.discovery.KernelFinder(providers=[FooKernelProvider(),
                                                                                  BarKernelProvider()])

    @classmethod
    def teardown_class(cls):
        cls.env_patch.stop()

    def test_find_remote_kernel_provider(self):
        fake_kspecs = list(TestRemoteKernelProvider.kernel_finder.find_kernels())
        assert len(fake_kspecs) == 3

        foo_kspecs = 0
        for name, spec in fake_kspecs:
            assert name.startswith('/foo_kspec', 3)
            assert spec['argv'] == foo_kernel_json['argv']
            if name.startswith('foo/'):
                foo_kspecs += 1
                assert spec['display_name'] == foo_kernel_json['display_name']
            else:
                assert spec['display_name'] == bar_kernel_json['display_name']
        assert foo_kspecs == 2

    def test_launch_remote_kernel_provider(self):
        conn_info, manager = TestRemoteKernelProvider.kernel_finder.launch('foo/foo_kspec')
        assert isinstance(manager, RemoteKernelManager)
        assert conn_info == foo_connection_info
        assert manager.kernel_id is not None
        assert is_uuid(manager.kernel_id)

        manager.kill()
        assert manager.lifecycle_manager is not None
        assert isinstance(manager.lifecycle_manager, FooKernelLifecycleManager)
        manager.cleanup()
        assert manager.lifecycle_manager is None
