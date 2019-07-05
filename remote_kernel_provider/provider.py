"""Provides base support to various remote kernel providers."""

from .manager import RemoteKernelManager
from jupyter_kernel_mgmt.discovery import KernelSpecProvider
from traitlets.log import get_logger as get_app_logger
from traitlets.config import Application


class RemoteKernelProviderBase(KernelSpecProvider):

    log = get_app_logger()  # We should always be run within an application

    # The following must be overridden by subclasses
    id = None
    kernel_file = None
    lifecycle_manager_classes = []

    def launch(self, kernelspec_name, cwd=None, kernel_params=None):
        """Launch a kernel, return (connection_info, kernel_manager).

        name will be one of the kernel names produced by find_kernels()

        This method launches and manages the kernel in a blocking manner.
        """
        kernelspec = self.ksm.get_kernel_spec(kernelspec_name)
        lifecycle_info = self._get_lifecycle_info(kernelspec)

        # Make the appropriate application configuration (relative to provider) available during launch
        app_config = self._get_app_config()

        # Launch the kernel via the kernel manager class method, returning its connection information
        # and kernel manager.
        kwargs = dict()
        kwargs['kernelspec'] = kernelspec
        kwargs['lifecycle_info'] = lifecycle_info
        kwargs['cwd'] = cwd
        kwargs['kernel_params'] = kernel_params or {}
        kwargs['app_config'] = app_config
        return RemoteKernelManager.launch(**kwargs)

    def launch_async(self, name, cwd=None):
        pass

    def _get_app_config(self):
        """Pulls application configuration 'section' relative to current class."""

        app_config = {}
        parent_app = Application.instance()
        if parent_app:
            # Collect config relative to our class instance.
            app_config = parent_app.config.get(self.__class__.__name__, {}).copy()
        return app_config

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
