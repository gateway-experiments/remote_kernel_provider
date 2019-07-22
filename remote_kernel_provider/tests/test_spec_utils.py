from remote_kernel_provider import spec_utils

from os import path
import glob
import pytest
import shutil
import tempfile

temp_dir = None


@pytest.fixture(scope='function')
def create_temp_dir(request):
    global temp_dir
    temp_dir = tempfile.mkdtemp()

    def delete_temp_dir():
        shutil.rmtree(temp_dir)

    request.addfinalizer(delete_temp_dir)


def test_staging_directory(create_temp_dir):
    # Create two staging dirs, one in the temp location, the other with no parent.
    staging_dir = spec_utils.create_staging_directory(parent_dir=temp_dir)
    assert path.isdir(staging_dir)
    assert path.basename(staging_dir).startswith("staging_")

    staging_dir2 = spec_utils.create_staging_directory()
    assert path.isdir(staging_dir2)
    assert path.basename(staging_dir2).startswith("staging_")

    # Ensure the two directories differ
    assert staging_dir != staging_dir2

    # Remove the staging dirs
    spec_utils.delete_staging_directory(staging_dir2)
    assert not path.exists(staging_dir2)

    spec_utils.delete_staging_directory(staging_dir)
    assert not path.exists(staging_dir)
    assert path.isdir(temp_dir)


def test_copy_python_launcher(create_temp_dir):
    kernel_name = 'python_kernel'

    staging_dir = spec_utils.create_staging_directory(parent_dir=temp_dir)
    spec_dir = path.join(staging_dir, kernel_name)

    # use this opportunity to use a bogus launch-type...
    with pytest.raises(ValueError) as ve:
        assert spec_utils.copy_kernelspec_files(spec_dir, launcher_type='bogus-type')
    assert str(ve.value).startswith("Invalid launcher_type 'bogus-type'")

    # and a bogus resource-type...
    with pytest.raises(ValueError) as ve:
        assert spec_utils.copy_kernelspec_files(spec_dir, launcher_type='python', resource_type='bogus-type')
    assert str(ve.value).startswith("Invalid resource_type 'bogus-type'")

    spec_utils.copy_kernelspec_files(spec_dir)  # exercise defaulted param

    assert path.isdir(spec_dir)
    scripts_dir = path.join(spec_dir, 'scripts')
    assert path.isdir(scripts_dir)
    launcher_file = path.join(spec_dir, 'scripts', 'launch_ipykernel.py')
    assert path.isfile(launcher_file)

    spec_utils.delete_staging_directory(staging_dir)
    assert not path.exists(launcher_file)
    assert not path.exists(scripts_dir)
    assert not path.exists(spec_dir)


def test_copy_r_launcher(create_temp_dir):
    kernel_name = 'r_kernel'

    staging_dir = spec_utils.create_staging_directory(parent_dir=temp_dir)
    spec_dir = path.join(staging_dir, kernel_name)

    spec_utils.copy_kernelspec_files(spec_dir, launcher_type='r')

    assert path.isdir(spec_dir)
    scripts_dir = path.join(spec_dir, 'scripts')
    assert path.isdir(scripts_dir)
    launcher_file = path.join(spec_dir, 'scripts', 'launch_IRkernel.R')
    assert path.isfile(launcher_file)
    gateway_file = path.join(spec_dir, 'scripts', 'gateway_listener.py')
    assert path.isfile(gateway_file)

    spec_utils.delete_staging_directory(staging_dir)
    assert not path.exists(gateway_file)
    assert not path.exists(launcher_file)
    assert not path.exists(scripts_dir)
    assert not path.exists(spec_dir)


def test_copy_scala_launcher(create_temp_dir):
    kernel_name = 'scala_kernel'

    staging_dir = spec_utils.create_staging_directory(parent_dir=temp_dir)
    spec_dir = path.join(staging_dir, kernel_name)

    spec_utils.copy_kernelspec_files(spec_dir, launcher_type='scala')

    assert path.isdir(spec_dir)
    lib_dir = path.join(spec_dir, 'lib')
    assert path.isdir(lib_dir)
    launcher_file = path.join(spec_dir, 'lib', 'toree-launcher_*')
    matches = glob.glob(launcher_file)
    assert len(matches) == 1
    launcher_file = matches[0]
    assert path.isfile(launcher_file)

    toree_jar = path.join(spec_dir, 'lib', 'toree-assembly-*')
    matches = glob.glob(toree_jar)
    assert len(matches) == 1
    toree_jar = matches[0]
    assert path.isfile(toree_jar)

    spec_utils.delete_staging_directory(staging_dir)
    assert not path.exists(toree_jar)
    assert not path.exists(launcher_file)
    assert not path.exists(lib_dir)
    assert not path.exists(spec_dir)


def test_copy_kubernetes_launcher(create_temp_dir):
    kernel_name = 'k8s_kernel'

    staging_dir = spec_utils.create_staging_directory(parent_dir=temp_dir)
    spec_dir = path.join(staging_dir, kernel_name)

    spec_utils.copy_kernelspec_files(spec_dir, launcher_type='kubernetes', resource_type='r')

    assert path.isdir(spec_dir)
    scripts_dir = path.join(spec_dir, 'scripts')
    assert path.isdir(scripts_dir)
    launcher_file = path.join(spec_dir, 'scripts', 'launch_kubernetes.py')
    assert path.isfile(launcher_file)
    pod_template = path.join(spec_dir, 'scripts', 'kernel-pod.yaml.j2')
    assert path.isfile(pod_template)

    spec_utils.delete_staging_directory(staging_dir)
    assert not path.exists(pod_template)
    assert not path.exists(launcher_file)
    assert not path.exists(scripts_dir)
    assert not path.exists(spec_dir)


def test_copy_docker_launcher(create_temp_dir):
    kernel_name = 'docker_kernel'

    staging_dir = spec_utils.create_staging_directory(parent_dir=temp_dir)
    spec_dir = path.join(staging_dir, kernel_name)

    spec_utils.copy_kernelspec_files(spec_dir, launcher_type='docker', resource_type='tensorflow')

    assert path.isdir(spec_dir)
    scripts_dir = path.join(spec_dir, 'scripts')
    assert path.isdir(scripts_dir)
    launcher_file = path.join(spec_dir, 'scripts', 'launch_docker.py')
    assert path.isfile(launcher_file)

    spec_utils.delete_staging_directory(staging_dir)
    assert not path.exists(launcher_file)
    assert not path.exists(scripts_dir)
    assert not path.exists(spec_dir)
