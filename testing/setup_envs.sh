#!/usr/bin/env bash

set -Eeo pipefail

echo Setting up environments for testing

CONDA_CLEAN_P=$1

# GitHub action specific items. These are no-ops locally
[ "$RUNNER_OS" == "Windows" ] && CONDA_EXE="$CONDA/Scripts/conda.exe"

cwd=$(cd $(dirname ${BASH_SOURCE[0]}) && pwd)
ymls=$cwd/env_yamls
if [[ "$CONDA_ROOT" != "" ]]; then
    mkdir -p $CONDA_ROOT
    croot=$(cd $CONDA_ROOT && pwd)
else
    croot=$cwd/conda
fi
envs=$croot/envs

# Use $croot/pkgs so package cache is included in testbed cache
# Set this BEFORE any conda operations to ensure packages go to the right location
# If CONDA_PKGS_DIRS is already set (e.g., from workflow), use that, otherwise use $croot/pkgs
if [ -z "$CONDA_PKGS_DIRS" ]; then
    export CONDA_PKGS_DIRS="$croot/pkgs"
fi
mkdir -p "$CONDA_PKGS_DIRS"

if [ ! -d $croot/conda-meta ]; then
    ${CONDA_EXE:-conda} create -y -p $croot conda python=3.9
fi

source $croot/etc/profile.d/conda.sh

if [ -d $croot/envs/activate_scripts/conda-meta ]; then
    conda info
    ls -l $croot/envs
    exit 0
fi

mkdir -p $envs

echo Creating basic_python environment
env=$envs/basic_python
conda env create -f $ymls/basic_python.yml -p $env
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

echo Creating basic_python_missing_files environment
env=$envs/basic_python_missing_files
conda env create -f $ymls/basic_python.yml -p $env
if [ -f $env/python.exe ]; then
    rm $env/lib/site-packages/toolz/*.py
else
    rm $env/lib/python3.9/site-packages/toolz/*.py
fi

echo Creating py310 environment
env=$envs/py310
conda env create -f $ymls/py310.yml -p $env
# Remove this package from the cache for testing -> test_missing_package_cache
rm -rf "$CONDA_PKGS_DIRS/conda_pack_test_lib2"*py310*

echo Creating baisc_python_editable environment
env=$envs/basic_python_editable
conda env create -f $ymls/basic_python.yml -p $env
pushd $cwd/test_packages/conda_pack_test_lib1
if [ -f $env/python.exe ]; then
    $env/python.exe setup.py develop
else
    $env/bin/python setup.py develop
fi
popd

echo Creating basic_python_broken environment
env=$envs/basic_python_broken
conda env create -f $ymls/basic_python_broken.yml -p $env

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

conda info
ls -l $croot/envs
