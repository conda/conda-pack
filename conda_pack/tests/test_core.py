from __future__ import absolute_import, print_function, division

import json
import os
import subprocess
import sys
import tarfile
from glob import glob

import pytest

from conda_pack import CondaEnv, CondaPackException, pack
from conda_pack.compat import on_win
from conda_pack.core import name_to_prefix, File, BIN_DIR

from .conftest import (py36_path, py36_editable_path, py36_broken_path,
                       py27_path, nopython_path, has_conda_path, rel_env_dir,
                       env_dir)


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


@pytest.mark.skipif(on_win, reason='Activate/deactivate are different on Win')
def test_load_environment_ignores(py36_env):
    lk = {f.target: f for f in py36_env}

    for path in ['bin/conda', 'conda-meta']:
        assert path not in lk

    # activate/deactivate exist, but aren't from conda
    assert not lk['bin/activate'].source.startswith(py36_path)
    assert not lk['bin/deactivate'].source.startswith(py36_path)


def test_file():
    f = File('/root/path/to/foo/bar', 'foo/bar')
    # smoketest repr
    repr(f)


@pytest.mark.skipif(on_win, reason='Different filenames and paths on Windows')
def test_loaded_file_properties(py36_env):
    lk = {f.target: f for f in py36_env}

    # Pip installed entrypoint
    fil = lk['bin/pytest']
    assert not fil.is_conda
    assert fil.file_mode == 'unknown'
    assert fil.prefix_placeholder is None

    # Conda installed noarch entrypoint
    fil = lk['bin/conda-pack-test-lib1']
    assert fil.is_conda
    assert fil.file_mode == 'text'
    assert fil.prefix_placeholder != py36_env.prefix

    # Conda installed entrypoint
    fil = lk['bin/conda-pack-test-lib2']
    assert fil.is_conda
    assert fil.file_mode == 'text'
    assert fil.prefix_placeholder != py36_env.prefix

    # Conda installed file
    fil = lk['lib/python3.6/site-packages/conda_pack_test_lib1/cli.py']
    assert fil.is_conda
    assert fil.file_mode is None
    assert fil.prefix_placeholder is None

@pytest.mark.skipif(not on_win, reason='Different filenames and paths on Windows')
def test_loaded_file_properties_win(py36_env):
    lk = {os.path.normcase(f.target): f for f in py36_env}

    # Pip installed entrypoint
    fil = lk[r'scripts\pytest.exe']
    assert not fil.is_conda
    assert fil.file_mode == 'unknown'
    assert fil.prefix_placeholder is None

    # Conda installed noarch entrypoint
    fil = lk[r'scripts\conda-pack-test-lib1']
    assert fil.is_conda
    assert fil.file_mode == 'text'
    assert fil.prefix_placeholder != py36_env.prefix

    # Conda installed entrypoint
    fil = lk[r'scripts\conda-pack-test-lib2.exe']
    assert fil.is_conda
    assert fil.file_mode == None
    assert fil.prefix_placeholder != py36_env.prefix

    # Conda installed file
    fil = lk[r'lib\site-packages\conda_pack_test_lib1\cli.py']
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

    site_packages = r"Lib\site-packages" if on_win else "lib/python3.6/site-packages"
    env3 = env2.exclude(os.path.join(site_packages, "conda_pack_test_lib1", "*"))
    env4 = env3.include(os.path.join(site_packages, "conda_pack_test_lib1", "cli.py"))
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
    conda_unpack = os.path.join(extract_path, BIN_DIR, 'conda-unpack.exe' if on_win else 'conda-pack')
    out = subprocess.check_output([conda_unpack, '--help'], shell=True,
                                  stderr=subprocess.STDOUT).decode()
    assert out.startswith('usage: conda-unpack')

    out = subprocess.check_output([conda_unpack, '--version'], shell=True,
                                  stderr=subprocess.STDOUT).decode()
    assert out.startswith('conda-unpack')

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


def test_pack_with_conda(tmpdir):
    env = CondaEnv.from_prefix(has_conda_path)
    out_path = os.path.join(str(tmpdir), 'has_conda.tar')
    env.pack(out_path)

    extract_path = os.path.join(str(tmpdir), 'output')
    os.mkdir(extract_path)

    assert os.path.exists(out_path)
    assert tarfile.is_tarfile(out_path)

    with tarfile.open(out_path) as fil:
        names = fil.getnames()

        # Check conda/activate/deactivate all present
        if on_win:
            assert 'Scripts/conda.exe' in names
        else:
            assert 'bin/conda' in names
            assert 'bin/activate' in names
            assert 'bin/deactivate' in names

        # Extract tarfile
        fil.extractall(extract_path)

    # Check the packaged conda works, and the output is a conda environment
    if not on_win:
        command = (". {path}/bin/activate && "
                   "conda list --json -p {path} &&"
                   ". {path}/bin/deactivate").format(path=extract_path)
        out = subprocess.check_output(['/usr/bin/env', 'bash', '-c', command],
                                      stderr=subprocess.STDOUT).decode()
        data = json.loads(out)
        assert 'conda' in {i['name'] for i in data}

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
    include = "lib/python3.6/site-packages/conda_pack_test_lib1/*"

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
        # conda-unpack.exe and conda-unpack-script.py
        assert len(diff) == 2
    else:
        assert len(diff) == 1
    extra = list(diff)[0]
    assert 'conda-unpack' in extra


def test_dest_prefix(tmpdir, py36_env):
    out_path = os.path.join(str(tmpdir), 'py36.tar')
    dest = '/foo/bar/baz/biz'
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

    dest_bytes = dest.encode()

    # shebangs are rewritten using env
    with tarfile.open(out_path) as fil:
        text_from_conda = fil.extractfile('/'.join([BIN_DIR, 'conda-pack-test-lib1'])).read()
        text_from_pip = fil.extractfile('scripts/pytest.exe' if on_win else 'bin/pytest').read()

    assert dest_bytes not in text_from_conda
    assert dest_bytes not in text_from_pip
    assert b'env python' in text_from_conda

    if not on_win:
        # pip entrypoint on Windows is complicated...
        assert b'env python' in text_from_pip

        with tarfile.open(out_path) as fil:
            binary_from_conda = fil.extractfile('bin/clear').read()

        # Other files are rewritten to use specified prefix This is only checked if
        # the original file did include the prefix, which is true at least on osx.
        orig_path = os.path.join(py36_env.prefix, 'bin/clear')
        with open(orig_path, 'rb') as fil:
            orig_bytes = fil.read()

        if py36_env.prefix.encode() in orig_bytes:
            assert py36_env.prefix.encode() not in binary_from_conda
            assert dest_bytes in binary_from_conda
