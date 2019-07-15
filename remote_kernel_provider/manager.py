# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Kernel managers that operate against a remote process."""

import getpass
import os
import signal
import re
import sys
import uuid

from .lifecycle_manager import RemoteKernelLifecycleManager, LocalKernelLifecycleManager

from jupyter_kernel_mgmt.managerabc import KernelManagerABC
from ipython_genutils.importstring import import_item
from traitlets.log import get_logger


class RemoteKernelManager(KernelManagerABC):
    """
    This class is responsible for detecting that a remote kernel is desired, then launching the
    appropriate class (previously pulled from the kernel spec).  The lifecycle manager is
    returned - upon which methods of poll(), wait(), send_signal(), and kill() can be called.
    """

    # TODO - fix this - add traits???
    remote_kernel_manager_class_default = "remote_kernel_provider.manager.RemoteKernelManager"
    remote_kernel_manager_class_name = os.getenv("REMOTE_KERNEL_MANAGER_CLASS", remote_kernel_manager_class_default)

    def __init__(self, **kwargs):
        self.kernel = None
        self.lifecycle_manager = None
        self.response_address = None
        self.sigint_value = None
        self.port_range = None
        self.user_overrides = {}
        self.restarting = False  # need to track whether we're in a restart situation or not
        self.log = get_logger()
        self.kernel_spec = kwargs.get('kernelspec')
        self.lifecycle_info = kwargs.get('lifecycle_info')
        self.cwd = kwargs.get('cwd')
        self.app_config = kwargs.get('app_config', {})
        self.kernel_params = kwargs.get('kernel_params', {})
        self.env = self.kernel_spec.env.copy()  # Seed env from kernelspec
        self.env.update(self._capture_user_overrides(kwargs.get('env', {}), self.kernel_params.get('env', {})))

        self.kernel_id = RemoteKernelManager.get_kernel_id(self.env)
        self.kernel_username = RemoteKernelManager.get_kernel_username(self.env)
        self.shutdown_wait_time = 5.0  # TODO - handle this better

    @classmethod
    def launch(cls, **kwargs):
        remote_kernel_manager_class = import_item(RemoteKernelManager.remote_kernel_manager_class_name)
        kernel_manager = remote_kernel_manager_class(**kwargs)
        kernel_manager.start_kernel()
        return kernel_manager.lifecycle_manager.connection_info, kernel_manager

    @classmethod
    def get_kernel_id(cls, env):
        # Ensure KERNEL_ID is set
        kernel_id = env.get('KERNEL_ID')
        if kernel_id is None:
            kernel_id = str(uuid.uuid4())
            env['KERNEL_ID'] = kernel_id
        return kernel_id

    @classmethod
    def get_kernel_username(cls, env):
        # Ensure KERNEL_USERNAME is set
        kernel_username = env.get('KERNEL_USERNAME')
        if kernel_username is None:
            kernel_username = getpass.getuser()
            env['KERNEL_USERNAME'] = kernel_username
        return kernel_username

    def start_kernel(self):
        """Starts a kernel in a separate process.

        Where the started kernel resides depends on the configured lifecycle manager.

        Parameters
        ----------
        `**kwargs` : optional
             keyword arguments that are passed down to build the kernel_cmd
             and launching the kernel (e.g. Popen kwargs).
        """

        lifecycle_manager_class_name = self.lifecycle_info.get('class_name')
        self.log.debug("Instantiating kernel '{}' with lifecycle manager: {}".
                       format(self.kernel_spec.display_name, lifecycle_manager_class_name))
        lifecycle_manager_class = import_item(lifecycle_manager_class_name)
        self.lifecycle_manager = lifecycle_manager_class(kernel_manager=self,
                                                         lifecycle_config=self.lifecycle_info.get('config', {}))

        # format command
        kernel_cmd = self.format_kernel_cmd()

        self.log.debug("Launching kernel: {} with command: {}".format(self.kernel_spec.display_name, kernel_cmd))
        self.kernel = self.lifecycle_manager.launch_process(kernel_cmd, env=self.env)

    def is_alive(self):
        """Check whether the kernel is currently alive (e.g. the process exists)
        """
        return self.kernel.poll() is None

    def wait(self, timeout):
        """Wait for the kernel process to exit.

        If timeout is a number, it is a maximum time in seconds to wait.
        timeout=None means wait indefinitely.

        Returns True if the kernel is still alive after waiting, False if it
        exited (like is_alive()).
        """
        self.kernel.wait()  # TODO - how to handle timeout

    def signal(self, signum):
        """Send a signal to the kernel."""
        if self.kernel:
            if signum == signal.SIGINT:
                if self.sigint_value is None:
                    # If we're interrupting the kernel, check if kernelspec's env defines
                    # an alternate interrupt signal.  We'll do this once per interrupted kernel.
                    # This is required for kernels whose language may prevent signals across
                    # process/user boundaries (Scala, for example).
                    self.sigint_value = signum  # use default
                    alt_sigint = self.kernel_spec.env.get('EG_ALTERNATE_SIGINT')
                    if alt_sigint:
                        try:
                            sig_value = getattr(signal, alt_sigint)
                            if type(sig_value) is int:  # Python 2
                                self.sigint_value = sig_value
                            else:  # Python 3
                                self.sigint_value = sig_value.value
                            self.log.debug(
                                "Converted EG_ALTERNATE_SIGINT '{}' to value '{}' to use as interrupt signal.".
                                format(alt_sigint, self.sigint_value))
                        except AttributeError:
                            self.log.warning("Error received when attempting to convert EG_ALTERNATE_SIGINT of "
                                             "'{}' to a value. Check kernelspec entry for kernel '{}' - using "
                                             "default 'SIGINT'".
                                             format(alt_sigint, self.kernel_spec.display_name))
                self.kernel.send_signal(self.sigint_value)
            else:
                self.kernel.send_signal(signum)
        else:
            raise RuntimeError("Cannot signal kernel. No kernel is running!")

    def interrupt(self):
        """Interrupt the kernel by sending it a signal or similar event

        Kernels can request to get interrupts as messages rather than signals.
        The manager is *not* expected to handle this.
        :meth:`.KernelClient2.interrupt` should send an interrupt_request or
        call this method as appropriate.
        """
        self.signal(signal.SIGINT)

    def kill(self):
        """Forcibly terminate the kernel.

        This method may be used to dispose of a kernel that won't shut down.
        Working kernels should usually be shut down by sending shutdown_request
        from a client and giving it some time to clean up.
        """

        # If we're using a remote proxy, we need to send the launcher indication that we're
        # shutting down so it can exit its listener thread, if its using one.  Note this will
        # occur after the initial (message-based) request to shutdown has been sent.
        if self.lifecycle_manager:
            if isinstance(self.lifecycle_manager, RemoteKernelLifecycleManager):
                self.lifecycle_manager.shutdown_listener()

        self.kernel.kill()

    def cleanup(self):
        """Clean up any resources, such as files created by the manager."""

        # Note we must use `lifecycle_manager` here rather than `kernel`, although they're the same value.
        # The reason is because if the kernel shutdown sequence has triggered its "forced kill" logic
        # then that method (jupyter_client/manager.py/_kill_kernel()) will set `self.kernel` to None,
        # which then prevents lifecycle manager cleanup.
        if self.lifecycle_manager:
            if isinstance(self.lifecycle_manager, RemoteKernelLifecycleManager):
                self.lifecycle_manager.shutdown_listener()

            self.lifecycle_manager.cleanup()
            self.lifecycle_manager = None

    def _capture_user_overrides(self, legacy_env, kernel_params_env):
        """
           Make a copy of any whitelist or KERNEL_ env values provided by user.  These will be injected
           back into the env after the kernelspec env has been applied.  This enables defaulting behavior
           of the kernelspec env stanza that would have otherwise overridden the user-provided values.
        """
        user_overrides = {}
        user_overrides.update({key: value for key, value in legacy_env.items()
                               if key.startswith('KERNEL_') or
                               key in self.app_config.get('env_process_whitelist', []) or
                               key in self.app_config.get('env_whitelist', [])})
        user_overrides.update({key: value for key, value in kernel_params_env.items()
                               if key.startswith('KERNEL_') or
                               key in self.app_config.get('env_process_whitelist', []) or
                               key in self.app_config.get('env_whitelist', [])})
        return user_overrides

    def format_kernel_cmd(self):
        """ Replace templated args (e.g. {response_address}, {port_range}, or {kernel_id}). """
        extra_arguments = self.kernel_params.get('extra_arguments', [])
        cmd = self.kernel_spec.argv + extra_arguments

        if cmd and cmd[0] in {'python',
                              'python%i' % sys.version_info[0],
                              'python%i.%i' % sys.version_info[:2]}:
            # executable is 'python' or 'python3', use sys.executable.
            # These will typically be the same,
            # but if the current process is in an env
            # and has been launched by abspath without
            # activating the env, python on PATH may not be sys.executable,
            # but it should be.
            cmd[0] = sys.executable

        ns = dict(prefix=sys.prefix,
                  resource_dir=self.kernel_spec.resource_dir,
                  response_address=self.response_address,
                  port_range=self.port_range,
                  kernel_id=self.kernel_id, )

        # Let any parameters be available for substitutions.
        params = self.kernel_params.copy()
        ns.update(params)

        pat = re.compile(r'\{([A-Za-z0-9_]+)\}')

        def from_ns(match):
            """Get the key out of ns if it's there, otherwise no change."""
            return ns.get(match.group(1), match.group())

        return [pat.sub(from_ns, arg) for arg in cmd]

    # TODO - this method no longer exists - need to send shutdown-listener request somehow
    def request_shutdown(self, restart=False):
        """ Send a shutdown request via control channel and lifecycle manager (if remote). """
        super(RemoteKernelManager, self).request_shutdown(restart)

        # If we're using a remote proxy, we need to send the launcher indication that we're
        # shutting down so it can exit its listener thread, if its using one.
        if isinstance(self.lifecycle_manager, RemoteKernelLifecycleManager):
            self.lifecycle_manager.shutdown_listener()

    # TODO - this needs to be addressed
    def restart_kernel(self, now=False, **kwargs):
        """Restarts a kernel with the arguments that were used to launch it.

        This is an automatic restart request (now=True) AND this is associated with a
        remote kernel, check the active connection count.  If there are zero connections, do
        not restart the kernel.

        Parameters
        ----------
        now : bool, optional
            If True, the kernel is forcefully restarted *immediately*, without
            having a chance to do any cleanup action.  Otherwise the kernel is
            given 1s to clean up before a forceful restart is issued.

            In all cases the kernel is restarted, the only difference is whether
            it is given a chance to perform a clean shutdown or not.

        `**kwargs` : optional
            Any options specified here will overwrite those used to launch the
            kernel.
        """
        self.restarting = True

        # Check if this is a remote lifecycle manager and if now = True. If so, check its connection count. If no
        # connections, shutdown else perform the restart.  Note: auto-restart sets now=True, but handlers use
        # the default value (False).
        if isinstance(self.lifecycle_manager, RemoteKernelLifecycleManager) and now:
            if self.parent._kernel_connections.get(self.kernel_id, 0) == 0:
                self.log.warning("Remote kernel ({}) will not be automatically restarted since there are no "
                                 "clients connected at this time.".format(self.kernel_id))
                # Use the parent mapping kernel manager so activity monitoring and culling is also shutdown
                self.parent.shutdown_kernel(self.kernel_id, now=now)
                return
        super(RemoteKernelManager, self).restart_kernel(now, **kwargs)
        if isinstance(self.lifecycle_manager, RemoteKernelLifecycleManager):  # for remote kernels...
            # Re-establish activity watching...
            if self._activity_stream:
                self._activity_stream.close()
                self._activity_stream = None
            self.parent.start_watching_activity(self.kernel_id)
        # Refresh persisted state.
        self.parent.parent.kernel_session_manager.refresh_session(self.kernel_id)
        self.restarting = False

    # TODO - Is this necessary now?
    def write_connection_file(self):
        """Write connection info to JSON dict in self.connection_file if the kernel is local.

        If this is a remote kernel that's using a response address or we're restarting, we should skip the
        write_connection_file since it will create 5 useless ports that would not adhere to port-range
        restrictions if configured.
        """
        if (isinstance(self.lifecycle_manager, LocalKernelLifecycleManager) or not self.response_address) \
                and not self.restarting:
            # However, since we *may* want to limit the selected ports, go ahead and get the ports using
            # the lifecycle manager (will be LocalPropcessProxy for default case) since the port selection will
            # handle the default case when the member ports aren't set anyway.
            ports = self.lifecycle_manager.select_ports(5)
            self.shell_port = ports[0]
            self.iopub_port = ports[1]
            self.stdin_port = ports[2]
            self.hb_port = ports[3]
            self.control_port = ports[4]

            return super(RemoteKernelManager, self).write_connection_file()
