import shutil
import tempfile

from os import path
from distutils import dir_util

kernel_launchers_dir = path.join(path.dirname(__file__), 'kernel-launchers')


def create_staging_directory(parent_dir=None):
    """Creates a temporary staging directory at the specified location.
       If no `parent_dir` is specified, the platform-specific "temp" directory is used.
    """
    return tempfile.mkdtemp(prefix="staging_", dir=parent_dir)


def delete_staging_directory(dir_name):
    """Deletes the specified staging directory."""
    shutil.rmtree(dir_name)


def copy_python_launcher(dir_name):
    """Copies the Python launcher files to the specified directory."""

    python_dir = path.join(kernel_launchers_dir, 'python')
    dir_util.copy_tree(src=python_dir, dst=dir_name)


def copy_r_launcher(dir_name):
    """Copies the R launcher files to the specified directory."""

    r_dir = path.join(kernel_launchers_dir, 'R')
    dir_util.copy_tree(src=r_dir, dst=dir_name)


def copy_scala_launcher(dir_name):
    """Copies the Scala launcher files to the specified directory."""

    scala_dir = path.join(kernel_launchers_dir, 'scala')
    dir_util.copy_tree(src=scala_dir, dst=dir_name)


def copy_kubernetes_launcher(dir_name):
    """Copies the Kubernetes launcher files to the specified directory."""

    k8s_dir = path.join(kernel_launchers_dir, 'kubernetes')
    dir_util.copy_tree(src=k8s_dir, dst=dir_name)


def copy_docker_launcher(dir_name):
    """Copies the Docker launcher files to the specified directory."""

    docker_dir = path.join(kernel_launchers_dir, 'docker')
    dir_util.copy_tree(src=docker_dir, dst=dir_name)
