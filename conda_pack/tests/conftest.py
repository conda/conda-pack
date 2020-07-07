from __future__ import print_function, division, absolute_import

import os

test_dir = os.path.dirname(os.path.abspath(__file__))
croot = os.environ.get('CONDA_ROOT')
if croot is None:
    croot = os.path.join(test_dir, '..', '..', 'testing', 'conda')
env_dir = os.path.join(os.path.abspath(croot), 'envs')

py27_path = os.path.join(env_dir, 'py27')
py36_path = os.path.join(env_dir, 'py36')
py36_editable_path = os.path.join(env_dir, 'py36_editable')
py36_broken_path = os.path.join(env_dir, 'py36_broken')
py36_missing_files_path = os.path.join(env_dir, 'py36_missing_files')
nopython_path = os.path.join(env_dir, 'nopython')
has_conda_path = os.path.join(env_dir, 'has_conda')
activate_scripts_path = os.path.join(env_dir, 'activate_scripts')
