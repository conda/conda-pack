import os
import pytest

from conda_pack import CondaEnv, CondaPackException
from conda_pack.core import name_to_prefix


test_dir = os.path.dirname(os.path.abspath(__file__))

rel_env_dir = os.path.join(test_dir, '..', '..', 'testing', 'environments')
env_dir = os.path.abspath(rel_env_dir)

py27_env = os.path.join(env_dir, 'py27')
py36_env = os.path.join(env_dir, 'py36')


def test_name_to_prefix():
    # Smoketest on default name
    name_to_prefix()

    with pytest.raises(CondaPackException):
        name_to_prefix("this_is_probably_not_a_real_env_name")


def test_from_prefix():
    env = CondaEnv.from_prefix(os.path.join(rel_env_dir, 'py36'))
    assert len(env)
    # relative path is normalized
    assert env.prefix == py36_env

    # Path is missing
    with pytest.raises(CondaPackException):
        CondaEnv.from_prefix(os.path.join(env_dir, "this_path_doesnt_exist"))

    # Path exists, but isn't a conda environment
    with pytest.raises(CondaPackException):
        CondaEnv.from_prefix(os.path.join(env_dir))


def test_missing_package_cache():
    with pytest.warns(UserWarning) as record:
        env = CondaEnv.from_prefix(py27_env)

    assert len(env)

    assert len(record) == 1
    msg = str(record[0].message)
    assert 'conda_pack_test_lib2' in msg

    with pytest.raises(CondaPackException):
        CondaEnv.from_prefix(py27_env, on_missing_cache='raise')
