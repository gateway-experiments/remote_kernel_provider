"""Provides base support to various remote kernel providers."""
import asyncio
from jupyter_kernel_mgmt.discovery import KernelSpecProvider
from traitlets.log import get_logger as get_app_logger
from .manager import RemoteKernelManager


class RemoteKernelProviderBase(KernelSpecProvider):

    log = get_app_logger()  # We should always be run within an application

    # The following must be overridden by subclasses
    id = None
    kernel_file = None
    lifecycle_manager_classes = []
    app_config = None
    provider_config = None

    @asyncio.coroutine
    def find_kernels(self):
        """Offers kernel types from installed kernelspec directories.

           Subclasses can perform optional pre and post checks surrounding call to superclass.
        """
        return super(RemoteKernelProviderBase, self).find_kernels()

    async def launch(self, kernelspec_name, cwd=None, launch_params=None):
        """Launch a kernel, return (connection_info, kernel_manager).

        name will be one of the kernel names produced by find_kernels()

        This method launches and manages the kernel in a blocking manner.
        """
        kernelspec = self.ksm.get_kernel_spec(kernelspec_name)
        lifecycle_info = self._get_lifecycle_info(kernelspec)

        # Launch the kernel via the kernel manager class method, returning its connection information
        # and kernel manager.
        kwargs = dict()
        kwargs['kernelspec'] = kernelspec
        kwargs['lifecycle_info'] = lifecycle_info
        kwargs['cwd'] = cwd
        kwargs['launch_params'] = launch_params or {}
        kwargs['app_config'] = self.app_config
        kwargs['provider_config'] = self.provider_config

        return await RemoteKernelManager.launch(**kwargs)

    def load_config(self, config=None):
        # Make the appropriate application configuration (relative to provider) available during launch
        self.app_config = config or {}
        self.provider_config = self.app_config.get(self.__class__.__name__, {}).copy()

    def _get_lifecycle_info(self, kernel_spec):
        """Looks for the metadata stanza containing the process proxy information.
           This will be in the `process_proxy` stanza of the metadata.
        """
        legacy_detected = False
        lifecycle_info = kernel_spec.metadata.get('lifecycle_manager', None)
        if lifecycle_info is None:
            lifecycle_info = kernel_spec.metadata.get('process_proxy', None)
            if lifecycle_info:
                legacy_detected = True
        if lifecycle_info:
            class_name = lifecycle_info.get('class_name', None)
            if class_name is not None:
                if class_name not in self.lifecycle_manager_classes:  # Legacy check...
                    legacy_detected = True
                    lifecycle_info.update({'class_name': self.lifecycle_manager_classes[0]})
            if 'config' not in lifecycle_info:  # if no config stanza, add one for consistency
                lifecycle_info.update({"config": {}})

        if lifecycle_info is None:  # Be sure to have a class_name with empty config
            lifecycle_info = {'class_name': self.lifecycle_manager_classes[0], 'config': {}}

        if legacy_detected:
            self.log.warn("Legacy kernelspec detected with at '{resource_dir}'.  Ensure the contents of "
                          "'{kernel_json}' contain a 'lifecycle_manager' stanza within 'metadata' with field "
                          "class_name in '{expected_classes}'".
                          format(resource_dir=kernel_spec.resource_dir, kernel_json=self.kernel_file,
                                 expected_classes=self.lifecycle_manager_classes))

        return lifecycle_info
