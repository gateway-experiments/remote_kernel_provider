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
    expected_process_class = None
    supported_process_classes = []

    def launch(self, kernelspec_name, cwd=None, kernel_params=None):
        """Launch a kernel, return (connection_info, kernel_manager).

        name will be one of the kernel names produced by find_kernels()

        This method launches and manages the kernel in a blocking manner.
        """
        kernelspec = self.ksm.get_kernel_spec(kernelspec_name)
        proxy_info = self._get_proxy_info(kernelspec)
        if proxy_info is None:
            raise RuntimeError("Process information could not be found in kernelspec file for kernel '{}'!  "
                               "Check the kernelspec file and try again.".format(kernelspec_name))

        # Make the appropriate application configuration (relative to provider) available during launch
        app_config = self._get_app_config()

        # Launch the kernel via the kernel manager class method, returning its connection information
        # and kernel manager.
        kwargs = dict()
        kwargs['kernelspec'] = kernelspec
        kwargs['proxy_info'] = proxy_info
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

    def _get_proxy_info(self, kernelspec):
        """Looks for the metadata stanza containing the process proxy information.
           This will be in the `process_proxy` stanza of the metadata.
        """
        proxy_info = kernelspec.metadata.get('process_proxy', None)
        if proxy_info:
            class_name = proxy_info.get('class_name', None)
            if class_name is not None and class_name in self.supported_process_classes:
                if class_name != self.expected_process_class:  # Legacy check...
                    self.log.warn("Legacy kernelspec detected with class_name: '{class_name}'.  "
                             "Please convert to new class '{expected_class}' when possible.".
                             format(class_name=proxy_info.get('class_name'), expected_class=self.expected_process_class))
                    proxy_info.update({'class_name': self.expected_process_class})
                if 'config' not in proxy_info:  # if no config stanza, add one for consistency
                    proxy_info.update({"config": {}})

        return proxy_info
