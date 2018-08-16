#/usr/bin/env bash
echo "== Setting up environments for testing =="

current_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "Creating py27 environment"
conda env create --force -f "${current_dir}/env_yamls/py27.yml" -p "${current_dir}/environments/py27"

echo "Creating py36 environment"
conda env create --force -f "${current_dir}/env_yamls/py36.yml" -p "${current_dir}/environments/py36"

echo "Creating py36_editable environment"
py36_editable="${current_dir}/environments/py36_editable"
conda env create --force -f "${current_dir}/env_yamls/py36.yml" -p $py36_editable
source activate $py36_editable
pushd "${current_dir}/.." && python setup.py develop && popd
source deactivate

echo "Creating py36_broken environment"
conda env create --force -f "${current_dir}/env_yamls/py36_broken.yml" -p "${current_dir}/environments/py36_broken"

echo "Creating nopython environment"
conda env create --force -f "${current_dir}/env_yamls/nopython.yml" -p "${current_dir}/environments/nopython"
