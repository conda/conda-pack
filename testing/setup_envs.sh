#/usr/bin/env bash
echo "== Setting up environments for testing =="

current_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "Creating py27 environment"
conda env create -f "${current_dir}/env_yamls/py27.yml" -p "${current_dir}/environments/py27" $@

echo "Creating py36 environment"
conda env create -f "${current_dir}/env_yamls/py36.yml" -p "${current_dir}/environments/py36" $@
# Create unmanaged conda-related files for conda-pack to remove
if [[ "$OS" == "Windows_NT" ]]; then
	touch ${current_dir}/environments/py36/Scripts/activate
	touch ${current_dir}/environments/py36/Scripts/activate.bat
	touch ${current_dir}/environments/py36/Scripts/deactivate
	touch ${current_dir}/environments/py36/Scripts/deactivate.bat
	touch ${current_dir}/environments/py36/Scripts/conda
	touch ${current_dir}/environments/py36/Scripts/conda.bat
else
	touch ${current_dir}/environments/py36/bin/activate
	touch ${current_dir}/environments/py36/bin/deactivate
	touch ${current_dir}/environments/py36/bin/conda
fi

echo "Creating py36_editable environment"
py36_editable="${current_dir}/environments/py36_editable"
conda env create -f "${current_dir}/env_yamls/py36.yml" -p $py36_editable $@
source activate $py36_editable
pushd "${current_dir}/.." && python setup.py develop && popd
source deactivate

echo "Creating py36_broken environment"
conda env create -f "${current_dir}/env_yamls/py36_broken.yml" -p "${current_dir}/environments/py36_broken" $@

echo "Creating nopython environment"
conda env create -f "${current_dir}/env_yamls/nopython.yml" -p "${current_dir}/environments/nopython" $@

echo "Creating conda environment"
conda env create -f "${current_dir}/env_yamls/has_conda.yml" -p "${current_dir}/environments/has_conda" $@

echo "Creating activate_scripts environment"
activate_scripts="${current_dir}/environments/activate_scripts"
conda env create -f "${current_dir}/env_yamls/activate_scripts.yml" -p $activate_scripts $@
mkdir -p "${activate_scripts}/etc/conda/activate.d"
mkdir -p "${activate_scripts}/etc/conda/deactivate.d"
if [[ "$OS" == "Windows_NT" ]]; then
  cp "${current_dir}/extra_scripts/conda_pack_test_activate.bat" "${activate_scripts}/etc/conda/activate.d/"
  cp "${current_dir}/extra_scripts/conda_pack_test_deactivate.bat" "${activate_scripts}/etc/conda/deactivate.d/"
else
  cp "${current_dir}/extra_scripts/conda_pack_test_activate.sh" "${activate_scripts}/etc/conda/activate.d/"
  cp "${current_dir}/extra_scripts/conda_pack_test_deactivate.sh" "${activate_scripts}/etc/conda/deactivate.d/"
fi
