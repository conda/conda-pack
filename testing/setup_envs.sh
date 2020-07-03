#/usr/bin/env bash

set -Eeo pipefail

echo Setting up environments for testing

cwd=$(cd $(dirname ${BASH_SOURCE[0]}) && pwd)
ymls=$cwd/env_yamls
envs=$cwd/environments

echo Creating py27 environment
env=$envs/py27
conda env create -f $ymls/py27.yml -p $env

echo Creating py36 environment
env=$envs/py36
conda env create -f $ymls/py36.yml -p $env
# Create unmanaged conda-related files for conda-pack to remove
touch $env/bin/activate
touch $env/bin/deactivate
touch $env/bin/conda

echo Creating py36_editable environment
env=$envs/py36_editable
conda env create -f $ymls/py36.yml -p $env
pushd $cwd/test_packages/conda_pack_test_lib1
$env/bin/python setup.py develop
popd

echo Creating py36_broken environment
env=$envs/py36_broken
conda env create -f $ymls/py36_broken.yml -p $env

echo Creating py36_missing_files environment
env=$envs/py36_missing_files
conda env create -f $ymls/py36.yml -p $env
rm $env/lib/python3.6/site-packages/toolz/__init__.py

echo Creating nopython environment
env=$envs/nopython
conda env create -f $ymls/nopython.yml -p $env

echo Creating conda environment
env=$envs/has_conda
conda env create -f $ymls/has_conda.yml -p $env

echo Creating activate_scripts environment
env=$envs/activate_scripts
conda env create -f $ymls/activate_scripts.yml -p $env
mkdir -p $env/etc/conda/activate.d $env/etc/conda/deactivate.d
cp $cwd/extra_scripts/conda_pack_test_activate.sh $env/etc/conda/activate.d
cp $cwd/extra_scripts/conda_pack_test_deactivate.sh $env/etc/conda/deactivate.d

echo Creating nested environment
conda env create -f $ymls/nopython.yml" -p $envs/py36/envs/nested
