import glob
import json
import os
import shutil
import subprocess
import tarfile

import pytest

from conda_pack import CondaEnv, CondaPackException
from conda_pack.core import name_to_prefix, File


test_dir = os.path.dirname(os.path.abspath(__file__))

rel_env_dir = os.path.join(test_dir, '..', '..', 'testing', 'environments')
env_dir = os.path.abspath(rel_env_dir)

py27_path = os.path.join(env_dir, 'py27')
py36_path = os.path.join(env_dir, 'py36')


@pytest.fixture
def broken_package_cache():
    metas = glob.glob(os.path.join(py27_path, 'conda-meta',
                                   'conda_pack_test_lib2*.json'))

    if len(metas) != 1:
        raise ValueError("%d metadata files found for conda_pack_test_lib2, "
                         "expected only 1" % len(metas))

    with open(os.path.join(metas[0])) as fil:
        info = json.load(fil)
    pkg = info['link']['source']

    if os.path.exists(pkg):
        shutil.rmtree(pkg)


@pytest.fixture(scope="module")
def py36_env():
    return CondaEnv.from_prefix(py36_path)


def test_name_to_prefix():
    # Smoketest on default name
    name_to_prefix()

    with pytest.raises(CondaPackException):
        name_to_prefix("this_is_probably_not_a_real_env_name")


def test_from_prefix():
    env = CondaEnv.from_prefix(os.path.join(rel_env_dir, 'py36'))
    assert len(env)
    # relative path is normalized
    assert env.prefix == py36_path

    # Path is missing
    with pytest.raises(CondaPackException):
        CondaEnv.from_prefix(os.path.join(env_dir, "this_path_doesnt_exist"))

    # Path exists, but isn't a conda environment
    with pytest.raises(CondaPackException):
        CondaEnv.from_prefix(os.path.join(env_dir))


def test_missing_package_cache(broken_package_cache):
    with pytest.warns(UserWarning) as record:
        env = CondaEnv.from_prefix(py27_path)

    assert len(env)

    assert len(record) == 1
    msg = str(record[0].message)
    assert 'conda_pack_test_lib2' in msg

    with pytest.raises(CondaPackException):
        CondaEnv.from_prefix(py27_path, on_missing_cache='raise')


def test_env_properties(py36_env):
    assert py36_env.name == 'py36'
    assert py36_env.prefix == py36_path

    # Env has a length
    assert len(py36_env) == len(py36_env.files)

    # Env is iterable
    assert len(list(py36_env)) == len(py36_env)

    # Smoketest repr
    assert 'CondaEnv<' in repr(py36_env)


def test_load_environment_ignores(py36_env):
    lk = {f.target: f for f in py36_env}

    for path in ['bin/conda', 'conda-meta']:
        assert path not in lk

    # activate/deactivate exist, but aren't from conda
    assert not lk['bin/activate'].source.startswith(py36_path)
    assert not lk['bin/deactivate'].source.startswith(py36_path)


def test_file():
    f = File('/root/path/to/foo/bar', 'foo/bar')
    # smoketest repr
    repr(f)


def test_loaded_file_properties(py36_env):
    lk = {f.target: f for f in py36_env}

    # Pip installed entrypoint
    fil = lk['bin/pytest']
    assert not fil.is_conda
    assert fil.file_mode == 'unknown'
    assert fil.prefix_placeholder is None

    # Conda installed noarch entrypoint
    fil = lk['bin/conda-pack-test-lib1']
    assert fil.is_conda
    assert fil.file_mode == 'text'
    assert fil.prefix_placeholder != py36_env.prefix

    # Conda installed entrypoint
    fil = lk['bin/conda-pack-test-lib2']
    assert fil.is_conda
    assert fil.file_mode == 'text'
    assert fil.prefix_placeholder != py36_env.prefix

    # Conda installed file
    fil = lk['lib/python3.6/site-packages/conda_pack_test_lib1/cli.py']
    assert fil.is_conda
    assert fil.file_mode is None
    assert fil.prefix_placeholder is None


def test_include_exclude(py36_env):
    old_len = len(py36_env)
    env2 = py36_env.exclude("*.pyc")
    # No mutation
    assert len(py36_env) == old_len
    assert env2 is not py36_env

    assert len(env2) < len(py36_env)

    # Re-add the removed files, envs are equivalent
    assert len(env2.include("*.pyc")) == len(py36_env)

    env3 = env2.exclude("lib/python3.6/site-packages/conda_pack_test_lib1/*")
    env4 = env3.include("lib/python3.6/site-packages/conda_pack_test_lib1/cli.py")
    assert len(env3) + 1 == len(env4)


def test_output_and_format(py36_env):
    output, format = py36_env._output_and_format()
    assert output == 'py36.tar.gz'
    assert format == 'tar.gz'

    for format in ['tar.gz', 'tar.bz2', 'tar', 'zip']:
        output = os.extsep.join([py36_env.name, format])

        o, f = py36_env._output_and_format(format=format)
        assert f == format
        assert o == output

        o, f = py36_env._output_and_format(output=output)
        assert o == output
        assert f == format

        o, f = py36_env._output_and_format(output='foo.zip', format=format)
        assert f == format
        assert o == 'foo.zip'

    with pytest.raises(CondaPackException):
        py36_env._output_and_format(format='foo')

    with pytest.raises(CondaPackException):
        py36_env._output_and_format(output='foo.bar')


def test_roundtrip(tmpdir, py36_env):
    out_path = os.path.join(str(tmpdir), 'py36.tar')
    py36_env.pack(out_path)
    assert os.path.exists(out_path)
    assert tarfile.is_tarfile(out_path)

    with tarfile.open(out_path) as fil:
        # Check all files are relative paths
        for member in fil.getnames():
            assert not member.startswith(os.path.sep)

        extract_path = str(tmpdir)
        fil.extractall(extract_path)

    # Shebang rewriting happens before prefixes are fixed
    textfile = os.path.join(extract_path, 'bin', 'conda-pack-test-lib1')
    with open(textfile, 'r') as fil:
        shebang = fil.readline().strip()
        assert shebang == '#!/usr/bin/env python'

    # Check bash scripts all don't error
    command = (". {path}/bin/activate && "
               "conda-unpack && "
               ". {path}/bin/deactivate && "
               "echo 'Done'").format(path=extract_path)

    out = subprocess.check_output(['/usr/bin/env', 'bash', '-c', command],
                                  stderr=subprocess.STDOUT).decode()
    assert out == 'Done\n'
