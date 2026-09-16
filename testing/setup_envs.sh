#!/usr/bin/env bash

set -Eeo pipefail

echo "Setting up environments for testing"

CONDA_CLEAN_P=$1

# GitHub action specific items. These are no-ops locally
[ "$RUNNER_OS" == "Windows" ] && CONDA_EXE="$CONDA/Scripts/conda.exe"

cwd=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ymls="$cwd/env_yamls"

if [[ "$CONDA_ROOT" != "" ]]; then
    mkdir -p "$CONDA_ROOT"
    croot=$(cd "$CONDA_ROOT" && pwd)
else
    croot="$cwd/conda"
fi

envs="$croot/envs"

# Use $croot/pkgs so package cache is included in testbed cache.
# Set this BEFORE any conda operations to ensure packages go to the right location.
if [ -z "$CONDA_PKGS_DIRS" ]; then
    export CONDA_PKGS_DIRS="$croot/pkgs"
fi

# CONDA_PKGS_DIRS may contain multiple directories separated by : (Unix) or ; (Windows)
# Extract the first directory only.
FIRST_CONDA_PKG_DIR=$(echo "$CONDA_PKGS_DIRS" | cut -d':' -d';' -f1)
mkdir -p "$FIRST_CONDA_PKG_DIR"

# Create the root conda environment only if it doesn't already exist.
if [ ! -d "$croot/conda-meta" ]; then
    "${CONDA_EXE:-conda}" create -y -p "$croot" conda python=3.9
fi

source "$croot/etc/profile.d/conda.sh"

mkdir -p "$envs"

# Create all environments defined by a matching yml.
for yml in "$ymls"/*.yml; do
    name=$(basename "$yml" .yml)
    env="$envs/$name"

    # Skip environments that already exist.
    if [ -d "$env/conda-meta" ]; then
        echo "Skipping $name environment; already exists"
        continue
    fi

    echo "Creating $name environment"
    conda env create -f "$yml" -p "$env"

    if [ "$name" = "basic_python" ]; then
        # Create unmanaged conda-related files for conda-pack to remove.
        if [ -f "$env/python.exe" ]; then
            touch "$env/Scripts/activate"
            touch "$env/Scripts/activate.bat"
            touch "$env/Scripts/deactivate"
            touch "$env/Scripts/deactivate.bat"
            touch "$env/Scripts/conda"
            touch "$env/Scripts/conda.bat"
        else
            touch "$env/bin/activate"
            touch "$env/bin/deactivate"
            touch "$env/bin/conda"
        fi
    fi

    if [ "$name" = "py310" ]; then
        # Remove this package from the cache for testing -> test_missing_package_cache.
        rm -rf "$FIRST_CONDA_PKG_DIR/conda_pack_test_lib2"*py310* 2>/dev/null || true
    fi

    if [ "$name" = "activate_scripts" ]; then
        mkdir -p \
            "$env/etc/conda/activate.d" \
            "$env/etc/conda/deactivate.d"

        if [ -f "$env/python.exe" ]; then
            cp "$cwd/extra_scripts/conda_pack_test_activate.bat" \
                "$env/etc/conda/activate.d"
            cp "$cwd/extra_scripts/conda_pack_test_deactivate.bat" \
                "$env/etc/conda/deactivate.d"
        else
            cp "$cwd/extra_scripts/conda_pack_test_activate.sh" \
                "$env/etc/conda/activate.d"
            cp "$cwd/extra_scripts/conda_pack_test_deactivate.sh" \
                "$env/etc/conda/deactivate.d"
        fi
    fi
done

# basic_python_missing_files: derived from basic_python.yml with files removed.
env="$envs/basic_python_missing_files"

if [ -d "$env/conda-meta" ]; then
    echo "Skipping basic_python_missing_files environment; already exists"
else
    echo "Creating basic_python_missing_files environment"
    conda env create -f "$ymls/basic_python.yml" -p "$env"

    if [ -f "$env/python.exe" ]; then
        rm "$env/lib/site-packages/toolz/"*.py
    else
        rm "$env/lib/python3.9/site-packages/toolz/"*.py
    fi
fi

# basic_python_editable: derived from basic_python.yml with editable install.
env="$envs/basic_python_editable"

if [ -d "$env/conda-meta" ]; then
    echo "Skipping basic_python_editable environment; already exists"
else
    echo "Creating basic_python_editable environment"
    conda env create -f "$ymls/basic_python.yml" -p "$env"

    pushd "$cwd/test_packages/conda_pack_test_lib1"

    if [ -f "$env/python.exe" ]; then
        "$env/python.exe" setup.py develop
    else
        "$env/bin/python" setup.py develop
    fi

    popd
fi

conda info
ls -l "$envs"
