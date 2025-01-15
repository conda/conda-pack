import os

test_dir = os.path.dirname(os.path.abspath(__file__))
croot = os.environ.get('CONDA_ROOT')
if croot is None:
    croot = os.path.join(test_dir, '..', '..', 'testing', 'conda')
env_dir = os.path.join(os.path.abspath(croot), 'envs')

basic_python_path = os.path.join(env_dir, "basic_python")
basic_python_editable_path = os.path.join(env_dir, "basic_python_editable")
basic_python_broken_path = os.path.join(env_dir, "basic_python_broken")
basic_python_missing_files_path = os.path.join(env_dir, "basic_python_missing_files")
py310_path = os.path.join(env_dir, "py310")
nopython_path = os.path.join(env_dir, "nopython")
has_conda_path = os.path.join(env_dir, "has_conda")
activate_scripts_path = os.path.join(env_dir, "activate_scripts")
