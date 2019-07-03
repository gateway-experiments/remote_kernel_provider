"""Utilities for launching kernels"""

# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import os
from subprocess import Popen, PIPE
from traitlets.log import get_logger


def launch_kernel(cmd, stdin=None, stdout=None, stderr=None, env=None,
                  cwd=None, **kw):
    """ Launches a localhost kernel, binding to the specified ports.

    Parameters
    ----------
    cmd : Popen list,
        A string of Python code that imports and executes a kernel entry point.

    stdin, stdout, stderr : optional (default None)
        Standards streams, as defined in subprocess.Popen.

    env: dict, optional
        Environment variables passed to the kernel

    cwd : path, optional
        The working dir of the kernel process (default: cwd of this process).

    **kw: optional
        Additional arguments for Popen

    Returns
    -------

    Popen instance for the kernel subprocess
    """

    # Popen will fail (sometimes with a deadlock) if stdin, stdout, and stderr
    # are invalid. Unfortunately, there is in general no way to detect whether
    # they are valid.  The following two blocks redirect them to (temporary)
    # pipes in certain important cases.

    # If this process has been backgrounded, our stdin is invalid. Since there
    # is no compelling reason for the kernel to inherit our stdin anyway, we'll
    # place this one safe and always redirect.
    _stdin = PIPE if stdin is None else stdin
    _stdout, _stderr = stdout, stderr

    env = env if (env is not None) else os.environ.copy()

    kwargs = kw.copy()
    main_args = dict(
        stdin=_stdin,
        stdout=_stdout,
        stderr=_stderr,
        cwd=cwd,
        env=env,
    )
    kwargs.update(main_args)

    # Spawn a kernel.
    # Create a new session.
    # This makes it easier to interrupt the kernel,
    # because we want to interrupt the whole process group.
    # We don't use setpgrp, which is known to cause problems for kernels starting
    # certain interactive subprocesses, such as bash -i.
    kwargs['start_new_session'] = True

    try:
        proc = Popen(cmd, **kwargs)
    except Exception:
        msg = (
            "Failed to run command:\n{}\n"
            "    PATH={!r}\n"
            "    with kwargs:\n{!r}\n"
        )
        # exclude environment variables,
        # which may contain access tokens and the like.
        without_env = {key: value for key, value in kwargs.items() if key != 'env'}
        msg = msg.format(cmd, env.get('PATH', os.defpath), without_env)
        get_logger().error(msg)
        raise

    # Clean up pipes created to work around Popen bug.
    if stdin is None:
        proc.stdin.close()

    return proc


__all__ = [
    'launch_kernel',
]
