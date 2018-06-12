from __future__ import print_function, division, absolute_import

import json
import glob
import os
import shutil

import pytest

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
