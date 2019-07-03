"""Testing utils for jupyter_client tests

"""
import os
pjoin = os.path.join
import sys
try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

import pytest

from ipython_genutils.tempdir import TemporaryDirectory


skip_win32 = pytest.mark.skipif(sys.platform.startswith('win'), reason="Windows")


class test_env(object):
    """Set Jupyter path variables to a temporary directory

    Useful as a context manager or with explicit start/stop
    """
    def start(self):
        self.test_dir = td = TemporaryDirectory()
        self.env_patch = patch.dict(os.environ, {
            'JUPYTER_CONFIG_DIR': pjoin(td.name, 'jupyter'),
            'JUPYTER_DATA_DIR': pjoin(td.name, 'jupyter_data'),
            'JUPYTER_RUNTIME_DIR': pjoin(td.name, 'jupyter_runtime'),
            'IPYTHONDIR': pjoin(td.name, 'ipython'),
        })
        self.env_patch.start()

    def stop(self):
        self.env_patch.stop()
        self.test_dir.cleanup()

    def __enter__(self):
        self.start()
        return self.test_dir.name

    def __exit__(self, *exc_info):
        self.stop()
