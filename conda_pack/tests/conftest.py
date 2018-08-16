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
py36_editable_path = os.path.join(env_dir, 'py36_editable')
py36_broken_path = os.path.join(env_dir, 'py36_broken')


def pytest_addoption(parser):
    parser.addoption(
        "--runslow", action="store_true", default=False, help="run slow tests"
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runslow"):
        # --runslow given in cli: do not skip slow tests
        return
    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)


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
