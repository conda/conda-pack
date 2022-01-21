from __future__ import absolute_import, division, print_function

import os

test_dir = os.path.dirname(os.path.abspath(__file__))
croot = os.environ.get('CONDA_ROOT')
if croot is None:
    croot = os.path.join(test_dir, '..', '..', 'testing', 'conda')
env_dir = os.path.join(os.path.abspath(croot), 'envs')

py37_path = os.path.join(env_dir, 'py37')
py37_editable_path = os.path.join(env_dir, 'py37_editable')
py37_broken_path = os.path.join(env_dir, 'py37_broken')
py37_missing_files_path = os.path.join(env_dir, 'py37_missing_files')
py310_path = os.path.join(env_dir, 'py310')
nopython_path = os.path.join(env_dir, 'nopython')
has_conda_path = os.path.join(env_dir, 'has_conda')
activate_scripts_path = os.path.join(env_dir, 'activate_scripts')
