@echo off

set cwd=%~dp0
set cwd=%cwd:~0,-1%
set ymls=%cwd%\env_yamls
set envs=%cwd%\environments

echo Setting up environments for testing

echo Creating py27 environment
set env=%envs%\py27
call conda.bat env create -f %ymls%\py27.yml -p %env%

echo Creating py36 environment
set env=%envs%\py36
call conda.bat env create -f %ymls%\py36.yml -p %env%
REM Create unmanaged conda-related files for conda-pack to remove
echo hi > %env%\Scripts\activate
echo hi > %env%\Scripts\activate.bat
echo hi > %env%\Scripts\deactivate
echo hi > %env%\Scripts\deactivate.bat
echo hi > %env%\Scripts\conda
echo hi > %env%\Scripts\conda.bat

echo Creating py36_editable environment
set env=%envs%\py36_editable
call conda.bat env create -f %ymls%\py36.yml -p %env%
cd %cwd%\test_packages\conda_pack_test_lib1
%env%\python.exe setup.py develop
cd %cwd%

echo Creating py36_broken environment
set env=%envs%\py36_broken
call conda.bat env create -f %ymls%\py36_broken.yml -p %env%

echo Creating py36_missing_files environment
set env=%envs%\py36_missing_files
call conda.bat env create -f %ymls%\py36.yml -p %env%
del %env%\Lib\site-packages\toolz\__init__.py

echo Creating nopython environment
set env=%envs%\nopython
call conda.bat env create -f %ymls%\nopython.yml -p %env%

echo Creating conda environment
set env=%envs%\has_conda
call conda.bat env create -f %ymls%\has_conda.yml -p %env%

echo Creating activate_scripts environment
set env=%envs%\activate_scripts
call conda.bat env create -f %ymls%\activate_scripts.yml -p %env%
mkdir %env%\etc\conda\activate.d
mkdir %env%\etc\conda\deactivate.d
copy %cwd%\extra_scripts\conda_pack_test_activate.bat %env%\etc\conda\activate.d
copy %cwd%\extra_scripts\conda_pack_test_deactivate.bat %env%\etc\conda\deactivate.d
