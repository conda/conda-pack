from __future__ import print_function, division, absolute_import

import json
import glob
import os
import shutil

import pytest

from conda_pack.compat import on_win


test_dir = os.path.dirname(os.path.abspath(__file__))
env_dir = os.environ.get('CONDA_PACK_TEST_ENVS')
if env_dir is None:
    env_dir = os.path.abspath(os.path.join(test_dir, '..', '..', 'testing', 'environments'))
elif on_win:
    env_dir = os.path.abspath(env_dir).replace('/', '\\')

py27_path = os.path.join(env_dir, 'py27')
py36_path = os.path.join(env_dir, 'py36')
py36_editable_path = os.path.join(env_dir, 'py36_editable')
py36_broken_path = os.path.join(env_dir, 'py36_broken')
py36_missing_files_path = os.path.join(env_dir, 'py36_missing_files')
nopython_path = os.path.join(env_dir, 'nopython')
has_conda_path = os.path.join(env_dir, 'has_conda')
activate_scripts_path = os.path.join(env_dir, 'activate_scripts')


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
