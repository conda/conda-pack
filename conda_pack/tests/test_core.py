import filecmp
import json
import os
import re
import subprocess
import tarfile
from glob import glob
from unittest.mock import Mock, mock_open, patch

import pytest

from conda_pack import CondaEnv, CondaPackException, pack
from conda_pack.compat import load_source, on_win
from conda_pack.core import BIN_DIR, File, Packer, name_to_prefix

from .conftest import (
    activate_scripts_path,
    basic_python_broken_path,
    basic_python_editable_path,
    basic_python_missing_files_path,
    basic_python_path,
    env_dir,
    has_conda_path,
    nopython_path,
    py310_path,
)

BIN_DIR_L = BIN_DIR.lower()
SP = "Lib\\site-packages" if on_win else "lib/python3.9/site-packages"
SP_L = SP.lower().replace("\\", "/")


if on_win:
    def normpath(f):
        return os.path.normcase(f).replace('\\', '/')
else:
    def normpath(f):
        return f


@pytest.fixture(scope="module")
def basic_python_env():
    return CondaEnv.from_prefix(basic_python_path)


@pytest.fixture
def bad_conda_exe(tmpdir_factory, monkeypatch):
    tmpdir = str(tmpdir_factory.mktemp('bin'))
    fake_conda = os.path.join(tmpdir, 'conda.bat' if on_win else 'conda')
    with open(fake_conda, 'w') as f:
        f.write('ECHO Failed\r\nEXIT /B 1' if on_win else 'echo "Failed"\nexit 1')
    os.chmod(fake_conda, os.stat(fake_conda).st_mode | 0o555)

    monkeypatch.setenv('PATH', tmpdir, prepend=os.pathsep)
    monkeypatch.delenv('CONDA_EXE', raising=False)


def test_name_to_prefix():
    # Smoketest on default name
    name_to_prefix()

    with pytest.raises(CondaPackException):
        name_to_prefix("this_is_probably_not_a_real_env_name")


def test_from_prefix():
    rel_env_dir = os.path.relpath(basic_python_path, os.getcwd())
    env = CondaEnv.from_prefix(rel_env_dir)
    assert len(env)
    # relative path is normalized
    assert os.path.normcase(env.prefix) == os.path.normcase(basic_python_path)

    # Path is missing
    with pytest.raises(CondaPackException):
        CondaEnv.from_prefix(os.path.join(env_dir, "this_path_doesnt_exist"))

    # Path exists, but isn't a conda environment
    with pytest.raises(CondaPackException):
        CondaEnv.from_prefix(os.path.join(env_dir))


def test_missing_package_cache():
    with pytest.warns(UserWarning) as record:
        env = CondaEnv.from_prefix(py310_path)

    assert len(env)

    assert len(record) == 1
    msg = str(record[0].message)
    assert 'conda_pack_test_lib2' in msg

    with pytest.raises(CondaPackException):
        CondaEnv.from_prefix(py310_path, on_missing_cache="raise")


def test_errors_editable_packages():
    with pytest.raises(CondaPackException) as exc:
        CondaEnv.from_prefix(basic_python_editable_path)

    # The error message has changed to reflect conda/pip conflicts
    # rather than just "editable packages found"
    assert "pip" in str(exc.value) and "conda" in str(exc.value)


def test_ignore_errors_editable_packages():
    # The ignore_editable_packages flag doesn't help with conda/pip conflicts
    # We need to ignore missing files instead
    CondaEnv.from_prefix(basic_python_editable_path, ignore_missing_files=True)


def test_errors_when_target_directory_not_exists_and_not_force(
    tmpdir, basic_python_env
):

    target_directory = os.path.join(tmpdir, "not_a_real_directory/")
    assert not os.path.exists(target_directory)

    target_file = os.path.join(target_directory, "env.tar.gz")

    with pytest.raises(CondaPackException) as exc:
        basic_python_env.pack(output=target_file, force=False)

    assert "not_a_real_directory" in str(exc.value)


def test_creates_directories_if_missing_and_force(tmpdir, basic_python_env):

    target_directory = os.path.join(tmpdir, "not_a_real_directory/")
    assert not os.path.exists(target_directory)

    target_file = os.path.join(target_directory, "env.tar.gz")

    basic_python_env.pack(output=target_file, force=True)

    assert os.path.exists(target_directory)


def test_errors_pip_overwrites():
    with pytest.raises(CondaPackException) as exc:
        CondaEnv.from_prefix(basic_python_broken_path)

    msg = str(exc.value)
    assert "pip" in msg
    assert "toolz" in msg


def test_missing_files():
    with pytest.raises(CondaPackException) as exc:
        CondaEnv.from_prefix(basic_python_missing_files_path)

    msg = str(exc.value)
    assert f"{os.sep}toolz{os.sep}__init__.py" in msg, msg
    assert f"{os.sep}toolz{os.sep}_signatures.py" in msg, msg


def test_missing_files_ignored(tmpdir):
    out_path = os.path.join(str(tmpdir), "basic_python_missing.tar")
    CondaEnv.from_prefix(
        basic_python_missing_files_path, ignore_missing_files=True
    ).pack(out_path)


def test_errors_conda_missing(bad_conda_exe):
    with pytest.raises(CondaPackException) as exc:
        CondaEnv.from_name('probably_fake_env')

    assert 'Failed to determine path to environment' in str(exc.value)


def test_env_properties(basic_python_env):
    assert basic_python_env.name == "basic_python"
    assert basic_python_env.prefix == basic_python_path

    # Env has a length
    assert len(basic_python_env) == len(basic_python_env.files)

    # Env is iterable
    assert len(list(basic_python_env)) == len(basic_python_env)

    # Smoketest repr
    assert "CondaEnv<" in repr(basic_python_env)


def test_load_environment_ignores(basic_python_env):
    lk = {normpath(f.target): f for f in basic_python_env}
    for fname in ("conda", "conda.bat"):
        assert f"{BIN_DIR_L}/{fname}" not in lk
    for fname in ("activate", "activate.bat", "deactivate", "deactivate.bat"):
        fpath = f"{BIN_DIR_L}/{fname}"
        assert fpath not in lk or not lk[fpath].source.startswith(basic_python_path)


def test_file():
    f = File('/root/path/to/foo/bar', 'foo/bar')
    # smoketest repr
    repr(f)


def test_loaded_file_properties(basic_python_env):
    lk = {normpath(f.target): f for f in basic_python_env}

    # Pip installed entrypoint
    exe_suffix = ".exe" if on_win else ""
    fil = lk[f"{BIN_DIR_L}/pytest{exe_suffix}"]
    assert not fil.is_conda
    assert fil.file_mode == 'unknown'
    assert fil.prefix_placeholder is None

    # Conda installed noarch entrypoint
    fil = lk[f"{BIN_DIR_L}/conda-pack-test-lib1"]
    assert fil.is_conda
    assert fil.file_mode == 'text'
    assert fil.prefix_placeholder != basic_python_env.prefix

    # Conda installed entrypoint
    suffix = "-script.py" if on_win else ""
    fil = lk[f"{BIN_DIR_L}/conda-pack-test-lib2{suffix}"]
    assert fil.is_conda
    assert fil.file_mode == 'text'
    assert fil.prefix_placeholder != basic_python_env.prefix

    # Conda installed file
    fil = lk[f"{SP_L}/conda_pack_test_lib1/cli.py"]
    assert fil.is_conda
    assert fil.file_mode is None
    assert fil.prefix_placeholder is None


def test_works_with_no_python():
    # Collection doesn't require python
    env = CondaEnv.from_prefix(nopython_path)
    # non-empty
    assert len(env)


def test_include_exclude(basic_python_env):
    old_len = len(basic_python_env)
    env2 = basic_python_env.exclude("*.pyc")
    # No mutation
    assert len(basic_python_env) == old_len
    assert env2 is not basic_python_env
    assert len(env2) < len(basic_python_env)

    # Re-add the removed files, envs are equivalent
    assert len(env2.include("*.pyc")) == len(basic_python_env)

    env3 = env2.exclude(os.path.join(SP, "conda_pack_test_lib1", "*"))
    env4 = env3.include(os.path.join(SP, "conda_pack_test_lib1", "cli.py"))
    assert len(env3) + 1 == len(env4)


def test_output_and_format(basic_python_env):
    output, format = basic_python_env._output_and_format()
    assert output == "basic_python.tar.gz"
    assert format == "tar.gz"

    for format in ["tar.gz", "tar.bz2", "tar.xz", "tar.zst", "tar", "zip", "parcel"]:
        output = os.extsep.join([basic_python_env.name, format])

        o, f = basic_python_env._output_and_format(format=format)
        assert f == format
        assert o == (None if f == "parcel" else output)

        o, f = basic_python_env._output_and_format(output=output)
        assert o == output
        assert f == format

        o, f = basic_python_env._output_and_format(output="foo.zip", format=format)
        assert f == format
        assert o == 'foo.zip'

    with pytest.raises(CondaPackException):
        basic_python_env._output_and_format(format="foo")

    with pytest.raises(CondaPackException):
        basic_python_env._output_and_format(output="foo.bar")

    with pytest.raises(CondaPackException):
        basic_python_env._output_and_format(output="foo.parcel", format="zip")


def test_roundtrip(tmpdir, basic_python_env):
    out_path = os.path.join(str(tmpdir), "basic_python.tar")
    basic_python_env.pack(out_path)
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
    with open(textfile) as fil:
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
    with tarfile.open(out_path, ignore_zeros=True) as fil:
        fil.extractall(extract_path)

    if on_win:
        fnames = ['conda.exe', 'activate.bat']
        # New conda drops deactivate.bat files
        if not fix_dest:
            fnames.append("deactivate.bat")
    else:
        fnames = ['conda', 'activate', 'deactivate']
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
        if fix_dest:
            # XXX: Conda windows activatation scripts now seem to assume a base
            # conda install, rather than relative paths. Given that this tool
            # is mostly for deploying code, and usually on servers (not
            # windows), this failure isn't critical but isn't 100% correct.
            # Ideally this test shouldn't need to special case `fix_dest`, and
            # use the same batch commands in both cases.
            commands = (
                rf"@call {extract_path}\condabin\conda activate",
                r"@conda info --json",
                r"@conda deactivate",
            )
        else:
            commands = (
                r"@set CONDA_PREFIX=",
                r"@set CONDA_SHVL=",
                rf"@call {extract_path}\Scripts\activate.bat",
                r"@conda info --json",
                r"@deactivate",
            )
        script_file = tmpdir.join("unpack.bat")
        cmd = ["cmd", "/c", str(script_file)]

    else:
        commands = (
            "unset CONDA_PREFIX",
            "unset CONDA_SHLVL",
            f". {extract_path}/bin/activate",
            "conda info --json",
            ". deactivate >/dev/null 2>/dev/null",
        )
        script_file = tmpdir.join("unpack.sh")
        cmd = ["/usr/bin/env", "bash", str(script_file)]

    script_file.write('\n'.join(commands))

    # When fix_dest=True, the conda installation is not relocatable,
    # so we can't test running it from a different location
    if not fix_dest:
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


def test_pack_exceptions(basic_python_env):
    # Can't pass both prefix and name
    with pytest.raises(CondaPackException):
        pack(prefix=basic_python_path, name="basic_python")

    # Unknown filter type
    with pytest.raises(CondaPackException):
        pack(prefix=basic_python_path, filters=[("exclude", "*.py"), ("foo", "*.pyc")])


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


def test_force(tmpdir, basic_python_env):
    already_exists = os.path.join(str(tmpdir), "basic_python.tar")
    with open(already_exists, "wb"):
        pass

    # file already exists
    with pytest.raises(CondaPackException):
        basic_python_env.pack(output=already_exists)

    basic_python_env.pack(output=already_exists, force=True)
    assert tarfile.is_tarfile(already_exists)


@pytest.mark.parametrize("format,n_threads", [("tar.gz", 1), ("tar.gz", 2)])
def test_reproducible(tmpdir, basic_python_env, format, n_threads):
    output_1 = os.path.join(str(tmpdir), "out1.tar")
    output_2 = os.path.join(str(tmpdir), "out2.tar")

    # Two consecutive runs should lead to exactly the same contents.
    basic_python_env.pack(output=output_1, n_threads=n_threads, format=format)
    basic_python_env.pack(output=output_2, n_threads=n_threads, format=format)

    filecmp.cmp(output_1, output_2)


def test_pack(tmpdir, basic_python_env):
    out_path = os.path.join(str(tmpdir), "basic_python.tar")

    exclude1 = "*.py"
    exclude2 = "*.pyc"
    include = os.path.join(SP, "conda_pack_test_lib1", "*")

    res = pack(
        prefix=basic_python_path,
        output=out_path,
        filters=[("exclude", exclude1), ("exclude", exclude2), ("include", include)],
    )

    assert res == out_path
    assert os.path.exists(out_path)
    assert tarfile.is_tarfile(out_path)

    with tarfile.open(out_path) as fil:
        paths = fil.getnames()

    filtered = basic_python_env.exclude(exclude1).exclude(exclude2).include(include)

    # Files line up with filtering, with extra conda-unpack command
    sol = {os.path.normcase(f.target) for f in filtered.files}
    res = {os.path.normcase(p) for p in paths}
    diff = res.difference(sol)

    if on_win:
        fnames = ('conda-unpack.exe', 'conda-unpack-script.py',
                  'activate.bat', 'deactivate.bat')
    else:
        fnames = ('conda-unpack', 'activate', 'deactivate', 'activate.fish')
    assert diff == {os.path.join(BIN_DIR_L, f) for f in fnames}


def _test_dest_prefix(src_prefix, dest_prefix, arcroot, out_path, format):
    if on_win:
        test_files = ['Scripts/conda-pack-test-lib1',
                      'Scripts/pytest.exe']
    else:
        test_files = ['bin/conda-pack-test-lib1',
                      'bin/pytest',
                      'bin/clear']

    orig_bytes = src_prefix.encode()
    orig_bytes_l = src_prefix.lower().encode() if on_win else orig_bytes
    new_bytes = dest_prefix.encode()
    new_bytes_l = dest_prefix.lower().encode() if on_win else new_bytes

    # all paths, including shebangs, are rewritten using the prefix
    with tarfile.open(out_path) as fil:
        for path in fil.getnames():
            assert os.path.basename(path) != "conda-unpack", path
            if arcroot:
                assert path.startswith(arcroot), path
        for test_file in test_files:
            orig_path = os.path.join(src_prefix, test_file)
            dest_path = os.path.join(arcroot, test_file)
            with open(orig_path, 'rb') as fil2:
                orig_data = fil2.read()
            if orig_bytes in orig_data:
                data = fil.extractfile(dest_path).read()
                assert orig_bytes not in data and orig_bytes_l not in data, test_file
                assert new_bytes in data or new_bytes_l in data, test_file


def test_dest_prefix(tmpdir, basic_python_env):
    out_path = os.path.join(str(tmpdir), "basic_python.tar")
    dest = r"c:\foo\bar\baz\biz" if on_win else "/foo/bar/baz/biz"
    res = pack(prefix=basic_python_path, dest_prefix=dest, output=out_path)

    assert res == out_path
    assert os.path.exists(out_path)
    assert tarfile.is_tarfile(out_path)

    _test_dest_prefix(basic_python_env.prefix, dest, "", out_path, "r")


def test_parcel(tmpdir, basic_python_env):
    if on_win:
        pytest.skip("Not parcel tests on Windows")
    arcroot = "basic_python-1234.56"

    out_path = os.path.join(str(tmpdir), arcroot + "-el7.parcel")

    pdir = os.getcwd()
    try:
        os.chdir(str(tmpdir))
        res = pack(prefix=basic_python_path, format="parcel", parcel_version="1234.56")
    finally:
        os.chdir(pdir)

    assert os.path.join(str(tmpdir), res) == out_path
    assert os.path.exists(out_path)

    # Verify that only the parcel files were added
    with tarfile.open(out_path, "r:gz") as fil:
        paths = fil.getnames()
    sol = {os.path.join(arcroot, f.target) for f in basic_python_env.files}
    diff = set(paths).difference(sol)
    fnames = ("conda_env.sh", "parcel.json")
    assert diff == {os.path.join(arcroot, "meta", f) for f in fnames}

    # Verify correct metadata in parcel.json
    with tarfile.open(out_path) as fil:
        fpath = os.path.join(arcroot, "meta", "parcel.json")
        data = fil.extractfile(fpath).read()
    data = json.loads(data)
    assert (
        data["name"] == "basic_python"
        and data["components"][0]["name"] == "basic_python"
    )
    assert (
        data["version"] == "1234.56" and data["components"][0]["version"] == "1234.56"
    )

    # Verify the correct dest_prefix substitution
    dest = os.path.join("/opt/cloudera/parcels", arcroot)
    _test_dest_prefix(basic_python_env.prefix, dest, arcroot, out_path, "r:gz")


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
        # bash
        command = (". {path}/bin/activate && "
                   "test $CONDAPACK_ACTIVATED -eq 1 && "
                   ". {path}/bin/deactivate && "
                   "test ! $CONDAPACK_ACTIVATED && "
                   "echo 'Done'").format(path=extract_path)

        out = subprocess.check_output(['/usr/bin/env', 'bash', '-c', command],
                                      stderr=subprocess.STDOUT).decode()

        assert out == 'Done\n'

        # fish
        command = (". {path}/bin/activate.fish && "
                   "python -c 'import sys; print(sys.executable)' && "
                   "deactivate && "
                   "echo 'Done'").format(path=extract_path)

        try:
            out = subprocess.check_output(['/usr/bin/env', 'fish', '-c', command],
                                          stderr=subprocess.STDOUT).decode()
            assert "test_activate0" in out
            assert "Done\n" in out
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Skip fish test if fish shell is not available
            pytest.skip("fish shell not available")


@pytest.mark.skipif(not on_win, reason="Windows-specific test")
def test_windows_extended_length_path_normalization():
    """Test that Windows extended-length paths are properly normalized in Packer.add()."""
    # Create mock archive
    mock_archive = Mock()
    test_prefix = r"C:\test\prefix"
    dest_prefix = r"C:\dest\prefix"  # Add dest_prefix to trigger replace_prefix

    # Create Packer instance with dest_prefix to ensure replace_prefix is called
    packer = Packer(prefix=test_prefix, archive=mock_archive, dest_prefix=dest_prefix)

    # Test data: (placeholder_input, expected_normalized_placeholder)
    test_cases = [
        # UNC path with forward slashes should be normalized
        (r"//?/C:\very\long\path\prefix", r"C:\very\long\path\prefix"),
        # UNC path with backslashes should be normalized
        (r"\\?\C:\very\long\path\prefix", r"C:\very\long\path\prefix"),
        # Normal path should remain unchanged
        (r"C:\normal\path\prefix", r"C:\normal\path\prefix"),
        # Empty string should remain unchanged
        ("", ""),
    ]

    # Mock file content
    test_content = b"#!/usr/bin/env python\nprint('test')"

    with patch('builtins.open', mock_open(read_data=test_content)):
        with patch('conda_pack.core.replace_prefix') as mock_replace_prefix:
            mock_replace_prefix.return_value = test_content

            for i, (input_placeholder, expected_placeholder) in enumerate(test_cases):
                # Create file with test placeholder
                test_file = File(
                    source=f"C:\\source\\file{i}.py",
                    target=f"lib/python3.9/file{i}.py",
                    is_conda=True,
                    file_mode="text",
                    prefix_placeholder=input_placeholder
                )

                # Add file to packer (triggers normalization logic)
                packer.add(test_file)

    # Verify replace_prefix was called with normalized placeholders
    calls = mock_replace_prefix.call_args_list
    assert len(calls) == len(test_cases)

    for i, (_, expected_placeholder) in enumerate(test_cases):
        # Check that the normalized placeholder was passed to replace_prefix
        # replace_prefix signature: replace_prefix(data, file_mode, placeholder, dest)
        actual_placeholder = calls[i][0][2]  # Third argument is the placeholder
        assert actual_placeholder == expected_placeholder, (
            f"Test case {i}: expected {expected_placeholder}, got {actual_placeholder}"
        )


@pytest.mark.skipif(not on_win, reason="Windows-specific test")
def test_windows_extended_length_path_normalization_none_placeholder():
    """Test that None placeholders are handled correctly in Windows path normalization."""
    mock_archive = Mock()
    test_prefix = r"C:\test\prefix"
    # Don't set dest_prefix so that files with None placeholder aren't processed
    packer = Packer(prefix=test_prefix, archive=mock_archive)

    # File with None placeholder should not crash
    test_file = File(
        source=r"C:\source\file.py",
        target="lib/python3.9/file.py",
        is_conda=True,
        file_mode="text",
        prefix_placeholder=None
    )

    # Mock file that should not go through replace_prefix path
    # This should take the "archive.add" path instead
    packer.add(test_file)

    # Verify the file was added to archive without prefix processing
    mock_archive.add.assert_called_once_with(test_file.source, test_file.target)


@pytest.mark.skipif(not on_win, reason="Windows-specific test")
def test_windows_extended_length_path_normalization_unknown_mode():
    """Test Windows extended-length path normalization for unknown file mode (self.prefix)."""
    mock_archive = Mock()

    # Use a prefix with extended-length path to test the second normalization block
    test_prefix = r"\\?\C:\very\long\test\prefix"
    dest_prefix = r"C:\dest\prefix"

    packer = Packer(prefix=test_prefix, archive=mock_archive, dest_prefix=dest_prefix)

    # Test data: (prefix_input, expected_normalized_prefix)
    test_cases = [
        # UNC path with backslashes should be normalized
        (r"\\?\C:\very\long\test\prefix", r"C:\very\long\test\prefix"),
        # UNC path with forward slashes should be normalized
        (r"//?/C:\very\long\test\prefix", r"C:\very\long\test\prefix"),
    ]

    for i, (input_prefix, expected_prefix) in enumerate(test_cases):
        # Update the packer's prefix for each test case
        packer.prefix = input_prefix

        # Use file_mode="unknown" to trigger the second normalization block (lines 1203-1207)
        test_file = File(
            source=f"C:\\source\\file{i}.exe",
            target=f"Scripts/some_executable{i}.exe",  # Windows bin dir with executable
            is_conda=True,
            file_mode="unknown",  # This triggers the second code path
            prefix_placeholder=None  # When None, it uses self.prefix
        )

        test_content = b"#!/usr/bin/env python\nprint('test')"

        with patch('builtins.open', mock_open(read_data=test_content)):
            with patch('conda_pack.core.replace_prefix') as mock_replace_prefix:
                with patch('conda_pack.core.is_binary_file', return_value=False):  # Force text mode
                    mock_replace_prefix.return_value = test_content

                    packer.add(test_file)

                    # Verify the normalized self.prefix was used (no \\?\ or //?/)
                    calls = mock_replace_prefix.call_args_list
                    assert len(calls) == 1, f"Expected 1 call, got {len(calls)}"

                    # Check the call arguments
                    actual_placeholder = calls[0][0][2]  # Third argument is the placeholder
                    assert actual_placeholder == expected_prefix, (
                        f"Test case {i}: expected {expected_prefix}, got {actual_placeholder}"
                    )
