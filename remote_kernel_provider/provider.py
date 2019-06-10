"""Provides base support to various remote kernel providers."""

import os
import re
import warnings

from .manager import RemoteKernelManager
from jupyter_kernel_mgmt.discovery import KernelProviderBase, KernelSpec
from jupyter_kernel_mgmt.kernelspec import NoSuchKernel
from jupyter_core.paths import jupyter_path
from traitlets.log import get_logger as get_app_logger
from traitlets.config import Application

try:
    from json import JSONDecodeError
except ImportError:
    # JSONDecodeError is new in Python 3.5, so while we support 3.4:
    JSONDecodeError = ValueError

log = get_app_logger()  # We should always be run within an application

# Note: the following "internal" methods and variables are derived directly
# from the base kernelspec implementation in jupyter_client.  Kernelspec-based
# providers are not able to extend the kernel-provider framework.  As a result,
# its easier (and cleaner) to duplicate that functionality for providers that
# still wish to use the kernelspec format.

_kernel_name_pat = re.compile(r'^[a-z0-9._\-]+$', re.IGNORECASE)


def _is_valid_kernel_name(name):
    """Check that a kernel name is valid."""
    # quote is not unicode-safe on Python 2
    return _kernel_name_pat.match(name)


_kernel_name_description = "Kernel names can only contain ASCII letters and numbers and these separators:" \
 " - . _ (hyphen, period, and underscore)."


def _is_kernel_dir(path):
    """Is ``path`` a kernel directory?"""
    return os.path.isdir(path) and os.path.isfile(os.path.join(path, 'kernel.json'))


def _list_kernels_in(directory):
    """Return a mapping of kernel names to resource directories from dir.

    If dir is None or does not exist, returns an empty dict.
    """
    if directory is None or not os.path.isdir(directory):
        return {}
    kernels = {}
    for f in os.listdir(directory):
        path = os.path.join(directory, f)
        if not _is_kernel_dir(path):
            continue
        key = f.lower()
        if not _is_valid_kernel_name(key):
            warnings.warn("Invalid kernel directory name ({dir_name}): {path}. {desc}".
                          format(dir_name=f, path=path, desc=_kernel_name_description), stacklevel=3,)
        kernels[key] = path
    return kernels


class RemoteKernelProviderBase(KernelProviderBase):

    # The following must be overridden by subclasses
    id = None
    kernels_dir = ''
    expected_process_class = None
    supported_process_classes = []

    def find_kernels(self):

        for name, resource_dir in self._find_remote_kernel_specs().items():
            try:
                spec = KernelSpec.from_resource_dir(resource_dir)
            except JSONDecodeError:
                log.warning("Failed to parse kernelspec in %s", resource_dir)
                continue

            yield name, {
                'language_info': {'name': spec.language},
                'display_name': spec.display_name,
                'resource_dir': spec.resource_dir,
                'metadata': spec.metadata,
            }

    def launch(self, kernelspec_name, cwd=None, kernel_params=None):
        """Launch a kernel, return (connection_info, kernel_manager).

        name will be one of the kernel names produced by find_kernels()

        This method launches and manages the kernel in a blocking manner.
        """
        kernelspec = self._get_kernel_spec(kernelspec_name)
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
                    log.warn("Legacy kernelspec detected with class_name: '{class_name}'.  "
                             "Please convert to new class '{expected_class}' when possible.".
                             format(class_name=proxy_info.get('class_name'), expected_class=self.expected_process_class))
                    proxy_info.update({'class_name': self.expected_process_class})
                if 'config' not in proxy_info:  # if no config stanza, add one for consistency
                    proxy_info.update({"config": {}})

        return proxy_info

    def _find_remote_kernel_specs(self):
        """Returns a dict mapping kernel names to resource directories.
        :rtype: dict
        """
        d = {}
        for kernel_dir in jupyter_path(self.kernels_dir):
            kernelspecs = _list_kernels_in(kernel_dir)
            for kname, spec_dir in kernelspecs.items():
                if kname not in d:
                    log.debug("Found remote kernel spec %s in %s", kname, kernel_dir)
                    d[kname] = spec_dir
        return d

    def _get_kernel_spec(self, kernel_name):
        """Returns a :class:`KernelSpec` instance for the given kernel_name.

        Raises :exc:`NoSuchKernel` if the given kernel name is not found.
        """
        d = self._find_remote_kernel_specs()
        try:
            resource_dir = d[kernel_name.lower()]
        except KeyError:
            raise NoSuchKernel(kernel_name)

        return KernelSpec.from_resource_dir(resource_dir)
