from __future__ import absolute_import, print_function, division

import json
import os
import re
import subprocess
import tarfile
from glob import glob

import pytest

from conda_pack import CondaEnv, CondaPackException, pack
from conda_pack.compat import on_win, load_source
from conda_pack.core import name_to_prefix, File, BIN_DIR

from .conftest import (py36_path, py36_editable_path, py36_broken_path,
                       py27_path, nopython_path, has_conda_path, rel_env_dir,
                       activate_scripts_path, env_dir)

BIN_DIR_L = BIN_DIR.lower()
SP_36 = 'Lib\\site-packages' if on_win else 'lib/python3.6/site-packages'
SP_36_L = SP_36.lower().replace('\\', '/')


if on_win:
    def normpath(f):
        return os.path.normcase(f).replace('\\', '/')
else:
    def normpath(f):
        return f


@pytest.fixture(scope="module")
def py36_env():
    return CondaEnv.from_prefix(py36_path)


@pytest.fixture
def bad_conda_exe(tmpdir_factory, monkeypatch):
    tmpdir = str(tmpdir_factory.mktemp('bin'))
    fake_conda = os.path.join(tmpdir, 'conda.bat' if on_win else 'conda')
    with open(fake_conda, 'w') as f:
        f.write('ECHO Failed\r\nEXIT /B 1' if on_win else 'echo "Failed"\nexit 1')
    os.chmod(fake_conda, os.stat(fake_conda).st_mode | 0o111)

    monkeypatch.setenv('PATH', tmpdir, prepend=os.pathsep)
    monkeypatch.delenv('CONDA_EXE', raising=False)


def test_name_to_prefix():
    # Smoketest on default name
    name_to_prefix()

    with pytest.raises(CondaPackException):
        name_to_prefix("this_is_probably_not_a_real_env_name")


def test_from_prefix():
    env = CondaEnv.from_prefix(os.path.join(rel_env_dir, 'py36'))
    assert len(env)
    # relative path is normalized
    assert env.prefix == py36_path

    # Path is missing
    with pytest.raises(CondaPackException):
        CondaEnv.from_prefix(os.path.join(env_dir, "this_path_doesnt_exist"))

    # Path exists, but isn't a conda environment
    with pytest.raises(CondaPackException):
        CondaEnv.from_prefix(os.path.join(env_dir))


def test_missing_package_cache(broken_package_cache):
    with pytest.warns(UserWarning) as record:
        env = CondaEnv.from_prefix(py27_path)

    assert len(env)

    assert len(record) == 1
    msg = str(record[0].message)
    assert 'conda_pack_test_lib2' in msg

    with pytest.raises(CondaPackException):
        CondaEnv.from_prefix(py27_path, on_missing_cache='raise')


def test_errors_editable_packages():
    with pytest.raises(CondaPackException) as exc:
        CondaEnv.from_prefix(py36_editable_path)

    assert "Editable packages found" in str(exc.value)


def test_ignore_errors_editable_packages():
    CondaEnv.from_prefix(py36_editable_path, ignore_editable_packages=True)


def test_errors_pip_overwrites():
    with pytest.raises(CondaPackException) as exc:
        CondaEnv.from_prefix(py36_broken_path)

    msg = str(exc.value)
    assert "pip" in msg
    assert "toolz" in msg


def test_errors_conda_missing(bad_conda_exe):
    with pytest.raises(CondaPackException) as exc:
        CondaEnv.from_name('probably_fake_env')

    assert 'Failed to determine path to environment' in str(exc.value)


def test_env_properties(py36_env):
    assert py36_env.name == 'py36'
    assert py36_env.prefix == py36_path

    # Env has a length
    assert len(py36_env) == len(py36_env.files)

    # Env is iterable
    assert len(list(py36_env)) == len(py36_env)

    # Smoketest repr
    assert 'CondaEnv<' in repr(py36_env)


def test_load_environment_ignores(py36_env):
    lk = {normpath(f.target): f for f in py36_env}
    for fname in ('conda', 'conda.bat'):
        assert '{}/{}'.format(BIN_DIR_L, fname) not in lk
    for fname in ('activate', 'activate.bat', 'deactivate', 'deactivate.bat'):
        fpath = '{}/{}'.format(BIN_DIR_L, fname)
        assert fpath not in lk or not lk[fpath].source.startswith(py36_path)


def test_file():
    f = File('/root/path/to/foo/bar', 'foo/bar')
    # smoketest repr
    repr(f)


def test_loaded_file_properties(py36_env):
    lk = {normpath(f.target): f for f in py36_env}

    # Pip installed entrypoint
    exe_suffix = '.exe' if on_win else ''
    fil = lk['{}/pytest{}'.format(BIN_DIR_L, exe_suffix)]
    assert not fil.is_conda
    assert fil.file_mode == 'unknown'
    assert fil.prefix_placeholder is None

    # Conda installed noarch entrypoint
    fil = lk['{}/conda-pack-test-lib1'.format(BIN_DIR_L)]
    assert fil.is_conda
    assert fil.file_mode == 'text'
    assert fil.prefix_placeholder != py36_env.prefix

    # Conda installed entrypoint
    suffix = '-script.py' if on_win else ''
    fil = lk['{}/conda-pack-test-lib2{}'.format(BIN_DIR_L, suffix)]
    assert fil.is_conda
    assert fil.file_mode == 'text'
    assert fil.prefix_placeholder != py36_env.prefix

    # Conda installed file
    fil = lk['{}/conda_pack_test_lib1/cli.py'.format(SP_36_L)]
    assert fil.is_conda
    assert fil.file_mode is None
    assert fil.prefix_placeholder is None


def test_works_with_no_python():
    # Collection doesn't require python
    env = CondaEnv.from_prefix(nopython_path)
    # non-empty
    assert len(env)


def test_include_exclude(py36_env):
    old_len = len(py36_env)
    env2 = py36_env.exclude("*.pyc")
    # No mutation
    assert len(py36_env) == old_len
    assert env2 is not py36_env
    assert len(env2) < len(py36_env)

    # Re-add the removed files, envs are equivalent
    assert len(env2.include("*.pyc")) == len(py36_env)

    env3 = env2.exclude(os.path.join(SP_36, "conda_pack_test_lib1", "*"))
    env4 = env3.include(os.path.join(SP_36, "conda_pack_test_lib1", "cli.py"))
    assert len(env3) + 1 == len(env4)


def test_output_and_format(py36_env):
    output, format = py36_env._output_and_format()
    assert output == 'py36.tar.gz'
    assert format == 'tar.gz'

    for format in ['tar.gz', 'tar.bz2', 'tar', 'zip']:
        output = os.extsep.join([py36_env.name, format])

        o, f = py36_env._output_and_format(format=format)
        assert f == format
        assert o == output

        o, f = py36_env._output_and_format(output=output)
        assert o == output
        assert f == format

        o, f = py36_env._output_and_format(output='foo.zip', format=format)
        assert f == format
        assert o == 'foo.zip'

    with pytest.raises(CondaPackException):
        py36_env._output_and_format(format='foo')

    with pytest.raises(CondaPackException):
        py36_env._output_and_format(output='foo.bar')


def test_roundtrip(tmpdir, py36_env):
    out_path = os.path.join(str(tmpdir), 'py36.tar')
    py36_env.pack(out_path)
    assert os.path.exists(out_path)
    assert tarfile.is_tarfile(out_path)

    with tarfile.open(out_path) as fil:
        # Check all files are relative paths
        for member in fil.getnames():
            assert not member.startswith(os.path.sep)

        extract_path = str(tmpdir.join('env'))
        fil.extractall(extract_path)

    # Shebang rewriting happens before prefixes are fixed
    textfile = os.path.join(extract_path, BIN_DIR, 'conda-pack-test-lib1')
    with open(textfile, 'r') as fil:
        shebang = fil.readline().strip()
        assert shebang == '#!/usr/bin/env python'

    # Check conda-unpack --help and --version
    if on_win:
        binary_name = 'conda-unpack.exe'
        script_name = 'conda-unpack-script.py'
    else:
        binary_name = script_name = 'conda-unpack'
    conda_unpack = os.path.join(extract_path, BIN_DIR, binary_name)
    conda_unpack_script = os.path.join(extract_path, BIN_DIR, script_name)
    out = subprocess.check_output([conda_unpack, '--help'],
                                  stderr=subprocess.STDOUT).decode()
    assert out.startswith('usage: conda-unpack')

    out = subprocess.check_output([conda_unpack, '--version'],
                                  stderr=subprocess.STDOUT).decode()
    assert out.startswith('conda-unpack')

    # Check no prefix generated for python executable
    python_pattern = re.compile(r'bin/python\d.\d')
    conda_unpack_mod = load_source('conda_unpack', conda_unpack_script)
    pythons = [r for r in conda_unpack_mod._prefix_records
               if python_pattern.match(r[0])]
    assert not pythons

    if on_win:
        command = (r"@call {path}\Scripts\activate.bat && "
                   "conda-unpack.exe && "
                   r"call {path}\Scripts\deactivate.bat && "
                   "echo Done").format(path=extract_path)
        unpack = tmpdir.join('unpack.bat')
        unpack.write(command)
        out = subprocess.check_output(['cmd.exe', '/c', str(unpack)],
                                      stderr=subprocess.STDOUT).decode()
        assert out == 'Done\r\n'

    else:
        # Check bash scripts all don't error
        command = (". {path}/bin/activate && "
                   "conda-unpack && "
                   ". {path}/bin/deactivate && "
                   "echo 'Done'").format(path=extract_path)
        out = subprocess.check_output(['/usr/bin/env', 'bash', '-c', command],
                                      stderr=subprocess.STDOUT).decode()
        assert out == 'Done\n'


@pytest.mark.parametrize('fix_dest', (True, False))
def test_pack_with_conda(tmpdir, fix_dest):
    env = CondaEnv.from_prefix(has_conda_path)
    out_path = os.path.join(str(tmpdir), 'has_conda.tar')
    extract_path = os.path.join(str(tmpdir), 'output')
    env.pack(out_path, dest_prefix=extract_path if fix_dest else None)

    os.mkdir(extract_path)

    assert os.path.exists(out_path)
    assert tarfile.is_tarfile(out_path)
    # Extract tarfile
    with tarfile.open(out_path) as fil:
        fil.extractall(extract_path)

    if on_win:
        fnames = ('conda.exe', 'activate.bat', 'deactivate.bat')
    else:
        fnames = ('conda', 'activate', 'deactivate')
    # Check conda/activate/deactivate all present
    for fname in fnames:
        fpath = os.path.join(extract_path, BIN_DIR, fname)
        assert os.path.exists(fpath)
        # Make sure we have replaced the activate/deactivate scripts
        # if the dest_prefix was not fixed; make sure we haven't
        # done so if it is.
        if 'activate' in fname:
            with open(fpath) as fp:
                data = fp.read()
                if fix_dest:
                    assert 'CONDA_PACK' not in data
                else:
                    assert 'CONDA_PACK' in data

    # Check the packaged conda works and recognizes its environment.
    # We need to unset CONDA_PREFIX to simulate unpacking into an environment
    # where conda is not already present.
    if on_win:
        commands = (r"@set CONDA_PREFIX=",
                    r"@call {path}\Scripts\activate".format(path=extract_path),
                    r"@conda info --json",
                    r"@deactivate")
        script_file = tmpdir.join('unpack.bat')
        cmd = ['cmd', '/c', str(script_file)]

    else:
        commands = ("unset CONDA_PREFIX",
                    ". {path}/bin/activate".format(path=extract_path),
                    "conda info --json",
                    ". deactivate >/dev/null 2>/dev/null")
        script_file = tmpdir.join('unpack.sh')
        cmd = ['/usr/bin/env', 'bash', str(script_file)]

    script_file.write('\n'.join(commands))
    out = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode()
    conda_info = json.loads(out)
    extract_path_n = normpath(extract_path)
    for var in ('conda_prefix', 'sys.prefix', 'default_prefix', 'root_prefix'):
        assert normpath(conda_info[var]) == extract_path_n
    assert extract_path_n in list(map(normpath, conda_info['envs']))

    # Check the conda-meta directory has been anonymized
    for path in glob(os.path.join(extract_path, 'conda-meta', '*.json')):
        with open(path) as fil:
            data = json.load(fil)

        for field in ["extracted_package_dir", "package_tarball_full_path"]:
            if field in data:
                assert data[field] == ""

        if "link" in data and "source" in data["link"]:
            assert data["link"]["source"] == ""


def test_pack_exceptions(py36_env):
    # Can't pass both prefix and name
    with pytest.raises(CondaPackException):
        pack(prefix=py36_path, name='py36')

    # Unknown filter type
    with pytest.raises(CondaPackException):
        pack(prefix=py36_path,
             filters=[("exclude", "*.py"),
                      ("foo", "*.pyc")])


@pytest.mark.slow
def test_zip64(tmpdir):
    # Create an environment that requires ZIP64 extensions, but doesn't use a
    # lot of disk/RAM
    source = os.path.join(str(tmpdir), 'source.txt')
    with open(source, 'wb') as f:
        f.write(b'0')

    files = [File(source, target='foo%d' % i) for i in range(1 << 16)]
    large_env = CondaEnv('large', files=files)

    out_path = os.path.join(str(tmpdir), 'large.zip')

    # Errors if ZIP64 disabled
    with pytest.raises(CondaPackException) as exc:
        large_env.pack(output=out_path, zip_64=False)
    assert 'ZIP64' in str(exc.value)
    assert not os.path.exists(out_path)

    # Works fine if ZIP64 not disabled
    large_env.pack(output=out_path)
    assert os.path.exists(out_path)


def test_force(tmpdir, py36_env):
    already_exists = os.path.join(str(tmpdir), 'py36.tar')
    with open(already_exists, 'wb'):
        pass

    # file already exists
    with pytest.raises(CondaPackException):
        py36_env.pack(output=already_exists)

    py36_env.pack(output=already_exists, force=True)
    assert tarfile.is_tarfile(already_exists)


def test_pack(tmpdir, py36_env):
    out_path = os.path.join(str(tmpdir), 'py36.tar')

    exclude1 = "*.py"
    exclude2 = "*.pyc"
    include = os.path.join(SP_36, 'conda_pack_test_lib1', '*')

    res = pack(prefix=py36_path,
               output=out_path,
               filters=[("exclude", exclude1),
                        ("exclude", exclude2),
                        ("include", include)])

    assert res == out_path
    assert os.path.exists(out_path)
    assert tarfile.is_tarfile(out_path)

    with tarfile.open(out_path) as fil:
        paths = fil.getnames()

    filtered = (py36_env
                .exclude(exclude1)
                .exclude(exclude2)
                .include(include))

    # Files line up with filtering, with extra conda-unpack command
    sol = set(os.path.normcase(f.target) for f in filtered.files)
    res = set(os.path.normcase(p) for p in paths)
    diff = res.difference(sol)

    if on_win:
        fnames = ('conda-unpack.exe', 'conda-unpack-script.py',
                  'activate.bat', 'deactivate.bat')
    else:
        fnames = ('conda-unpack', 'activate', 'deactivate')
    assert diff == set(os.path.join(BIN_DIR_L, f) for f in fnames)


def test_dest_prefix(tmpdir, py36_env):
    out_path = os.path.join(str(tmpdir), 'py36.tar')
    dest = r'C:\foo\bar\baz\biz' if on_win else '/foo/bar/baz/biz'
    res = pack(prefix=py36_path,
               dest_prefix=dest,
               output=out_path)

    assert res == out_path
    assert os.path.exists(out_path)
    assert tarfile.is_tarfile(out_path)

    with tarfile.open(out_path) as fil:
        paths = fil.getnames()

    # No conda-unpack generated
    assert 'conda-unpack' not in paths

    if on_win:
        test_files = ['Scripts/conda-pack-test-lib1',
                      'Scripts/pytest.exe']
    else:
        test_files = ['bin/conda-pack-test-lib1',
                      'bin/pytest',
                      'bin/clear']

    orig_bytes = py36_env.prefix.encode()
    new_bytes = dest.encode()

    # all paths, including shebangs, are rewritten using the prefix
    with tarfile.open(out_path) as fil:
        for test_file in test_files:
            orig_path = os.path.join(py36_env.prefix, test_file)
            with open(orig_path, 'rb') as fil2:
                orig_data = fil2.read()
            if orig_bytes in orig_data:
                data = fil.extractfile(test_file).read()
                assert orig_bytes not in data, test_file
                assert new_bytes in data, test_file


def test_activate(tmpdir):
    out_path = os.path.join(str(tmpdir), 'activate_scripts.tar')
    extract_path = str(tmpdir.join('env'))

    env = CondaEnv.from_prefix(activate_scripts_path)
    env.pack(out_path)

    with tarfile.open(out_path) as fil:
        fil.extractall(extract_path)

    # Check that activate environment variable is set
    if on_win:
        command = (r"@CALL {path}\Scripts\activate" "\r\n"
                   r"@ECHO CONDAPACK_ACTIVATED=%CONDAPACK_ACTIVATED%" "\r\n"
                   r"@CALL {path}\Scripts\deactivate" "\r\n"
                   r"@ECHO CONDAPACK_ACTIVATED=%CONDAPACK_ACTIVATED%" "\r\n"
                   r"@echo Done").format(path=extract_path)
        unpack = tmpdir.join('unpack.bat')
        unpack.write(command)

        out = subprocess.check_output(['cmd', '/c', str(unpack)],
                                      stderr=subprocess.STDOUT).decode()

        assert out == 'CONDAPACK_ACTIVATED=1\r\nCONDAPACK_ACTIVATED=\r\nDone\r\n'

    else:
        command = (". {path}/bin/activate && "
                   "test $CONDAPACK_ACTIVATED -eq 1 && "
                   ". {path}/bin/deactivate && "
                   "test ! $CONDAPACK_ACTIVATED && "
                   "echo 'Done'").format(path=extract_path)

        out = subprocess.check_output(['/usr/bin/env', 'bash', '-c', command],
                                      stderr=subprocess.STDOUT).decode()

        assert out == 'Done\n'
