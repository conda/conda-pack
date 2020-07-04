#/usr/bin/env bash

set -Eeo pipefail

echo Setting up environments for testing

cwd=$(cd $(dirname ${BASH_SOURCE[0]}) && pwd)
ymls=$cwd/env_yamls
if [[ "$CONDA_PACK_TEST_ENVS" != "" ]]; then
    envs=$CONDA_PACK_TEST_ENVS
else
    envs=$cwd/environments
fi

echo Creating py27 environment
env=$envs/py27
conda env create -f $ymls/py27.yml -p $env

echo Creating py36 environment
env=$envs/py36
conda env create -f $ymls/py36.yml -p $env
# Create unmanaged conda-related files for conda-pack to remove
if [ -f $env/python.exe ]; then
    touch $env/Scripts/activate
    touch $env/Scripts/activate.bat
    touch $env/Scripts/deactivate
    touch $env/Scripts/deactivate.bat
    touch $env/Scripts/conda
    touch $env/Scripts/conda.bat
else
    touch $env/bin/activate
    touch $env/bin/deactivate
    touch $env/bin/conda
fi

echo Creating py36_editable environment
env=$envs/py36_editable
conda env create -f $ymls/py36.yml -p $env
pushd $cwd/test_packages/conda_pack_test_lib1
if [ -f $env/python.exe ]; then
    $env/python.exe setup.py develop
else
    $env/bin/python setup.py develop
fi
popd

echo Creating py36_broken environment
env=$envs/py36_broken
conda env create -f $ymls/py36_broken.yml -p $env

echo Creating py36_missing_files environment
env=$envs/py36_missing_files
conda env create -f $ymls/py36.yml -p $env
if [ -f $env/python.exe ]; then
    rm $env/lib/site-packages/toolz/__init__.py
else
    rm $env/lib/python3.6/site-packages/toolz/__init__.py
fi

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
if [ -f $env/python.exe ]; then
    cp $cwd/extra_scripts/conda_pack_test_activate.bat $env/etc/conda/activate.d
    cp $cwd/extra_scripts/conda_pack_test_deactivate.bat $env/etc/conda/deactivate.d
else
    cp $cwd/extra_scripts/conda_pack_test_activate.sh $env/etc/conda/activate.d
    cp $cwd/extra_scripts/conda_pack_test_deactivate.sh $env/etc/conda/deactivate.d
fi
