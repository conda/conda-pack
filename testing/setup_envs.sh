#/usr/bin/env bash
echo "== Setting up environments for testing =="

current_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "Creating py27 environment"
conda env create --force -f "${current_dir}/env_yamls/py27.yml" -p "${current_dir}/environments/py27"

echo "Creating py36 environment"
conda env create --force -f "${current_dir}/env_yamls/py36.yml" -p "${current_dir}/environments/py36"
