import os
import shutil
import subprocess
import tarfile
import threading
import time
import zipfile
from multiprocessing import cpu_count
from os.path import isdir, isfile, islink, join, exists
from pathlib import Path
from subprocess import check_output, STDOUT

import pytest

from conda_pack.core import CondaPackException
from conda_pack.formats import archive, _parse_n_threads
from conda_pack.compat import on_win, PY2


@pytest.fixture(scope="module")
def root_and_paths(tmpdir_factory):
    root = str(tmpdir_factory.mktemp('example_dir'))

    def mkfil(*paths):
        with open(join(root, *paths), mode='wb') as fil:
            # Write 512 KiB to file
            fil.write(os.urandom(512 * 2 ** 10))

    def mkdir(path):
        os.mkdir(join(root, path))

    def symlink(path, target):
        target = join(root, target)
        path = join(root, path)
        if on_win:
            # Copy the files instead of symlinking
            if isdir(target):
                shutil.copytree(target, path)
            else:
                shutil.copyfile(target, path)
        else:
            target = os.path.relpath(target, os.path.dirname(path))
            os.symlink(target, path)

    # Build test directory structure
    mkdir("empty_dir")
    symlink("link_to_empty_dir", "empty_dir")

    mkdir("dir")
    mkfil("dir", "one")
    mkfil("dir", "two")
    symlink("link_to_dir", "dir")

    mkfil("file")
    symlink("link_to_file", "file")

    paths = ["empty_dir",
             "link_to_empty_dir",
             join("dir", "one"),
             join("dir", "two"),
             "file",
             "link_to_file",
             "link_to_dir"]

    if on_win:
        # Since we have no symlinks, these are actual
        # files that need to be added to the archive
        paths.extend([join("link_to_dir", "one"),
                      join("link_to_dir", "two")])

    # make sure the input matches the test
    check(root, links=not on_win)

    return root, paths


def check(out_dir, root=None, links=False):
    assert exists(join(out_dir, "empty_dir"))
    assert isdir(join(out_dir, "empty_dir"))
    assert isdir(join(out_dir, "link_to_empty_dir"))
    assert isdir(join(out_dir, "dir"))
    assert isfile(join(out_dir, "dir", "one"))
    assert isfile(join(out_dir, "dir", "two"))
    assert isdir(join(out_dir, "link_to_dir"))
    assert isfile(join(out_dir, "link_to_dir", "one"))
    assert isfile(join(out_dir, "link_to_dir", "two"))
    assert isfile(join(out_dir, "file"))
    assert isfile(join(out_dir, "link_to_file"))

    if root is not None:
        def check_equal_contents(*paths):
            with open(join(out_dir, *paths), 'rb') as path1:
                packaged = path1.read()

            with open(join(root, *paths), 'rb') as path2:
                source = path2.read()

            assert packaged == source

        check_equal_contents("dir", "one")
        check_equal_contents("dir", "two")
        check_equal_contents("file")

    if links:
        def checklink(path, sol):
            path = join(out_dir, "link_to_dir")
            sol = join(out_dir, sol)
            assert islink(path)
            return join(out_dir, os.readlink(path)) == sol

        checklink("link_to_dir", "dir")
        checklink("link_to_file", "file")
        checklink("link_to_empty_dir", "empty_dir")
    else:
        # Check that contents of directories are same
        files = set(os.listdir(join(out_dir, "link_to_dir")))
        # Remove the dynamically written file, if running in a test
        files.discard('from_bytes')
        assert files == {'one', 'two'}


def has_infozip_cli():
    try:
        out = check_output(['unzip', '-h'], stderr=STDOUT).decode()
    except Exception:
        return False
    return "Info-ZIP" in out


def has_tar_cli():
    try:
        check_output(['tar', '-h'], stderr=STDOUT)
        return True
    except Exception:
        return False


@pytest.mark.parametrize('format, zip_symlinks', [
    ('zip', True), ('zip', False),
    ('tar.gz', False), ('tar.bz2', False), ('tar', False),
    ('squashfs', False)
])
def test_format(tmpdir, format, zip_symlinks, root_and_paths):
    if format == 'zip':
        if zip_symlinks and (on_win or not has_infozip_cli()):
            pytest.skip("Cannot test zipfile symlink support on this platform")
        test_symlinks = zip_symlinks
    else:
        test_symlinks = not on_win

    root, paths = root_and_paths

    packed_env_path = join(str(tmpdir), 'test.' + format)
    spill_dir = join(str(tmpdir), 'test')
    os.mkdir(spill_dir)

    with open(packed_env_path, mode='wb') as fil:
        with archive(fil, '', format, zip_symlinks=zip_symlinks) as arc:
            for rel in paths:
                arc.add(join(root, rel), rel)
            arc.add_bytes(join(root, "file"),
                          b"foo bar",
                          join("dir", "from_bytes"))

    if format == 'zip':
        if test_symlinks:
            check_output(['unzip', packed_env_path, '-d', spill_dir])
        else:
            with zipfile.ZipFile(packed_env_path) as out:
                out.extractall(spill_dir)
    elif format == "squashfs":
        if on_win:
            # TODO make sure this runs on Mac as well
            pytest.skip("Cannot test SquashFS on Windows, Linux only")
        # 'mount' needs CAP_SYS_ADMIN
        cmd = ["mount", "-t", "squashfs", packed_env_path, spill_dir]
        # allow for local testing in root containers
        if "docker" not in Path("/proc/1/cgroup").read_text():
            cmd = ["sudo"] + cmd
        subprocess.check_output(cmd)
    else:
        with tarfile.open(packed_env_path) as out:
            out.extractall(spill_dir)

    check(spill_dir, links=test_symlinks, root=root)
    assert isfile(join(spill_dir, "dir", "from_bytes"))
    with open(join(spill_dir, "dir", "from_bytes"), 'rb') as fil:
        assert fil.read() == b"foo bar"


def test_n_threads():
    assert _parse_n_threads(-1) == cpu_count()
    assert _parse_n_threads(40) == 40

    for n in [-10, 0]:
        with pytest.raises(CondaPackException):
            _parse_n_threads(n)


@pytest.mark.parametrize('format', ['tar.gz', 'tar.bz2'])
def test_format_parallel(tmpdir, format, root_and_paths):
    # Python 2's bzip dpesn't support reading multipart files :(
    if format == 'tar.bz2' and PY2:
        if on_win or not has_tar_cli():
            pytest.skip("Unable to test parallel bz2 support on this platform")
        use_cli_to_extract = True
    else:
        use_cli_to_extract = False

    root, paths = root_and_paths

    out_path = join(str(tmpdir), 'test.' + format)
    out_dir = join(str(tmpdir), 'test')
    os.mkdir(out_dir)

    baseline = threading.active_count()
    with open(out_path, mode='wb') as fil:
        with archive(fil, '', format, n_threads=2) as arc:
            for rel in paths:
                arc.add(join(root, rel), rel)
    timeout = 5
    while threading.active_count() > baseline:
        time.sleep(0.1)
        timeout -= 0.1
        assert timeout > 0, "Threads failed to shutdown in sufficient time"

    if use_cli_to_extract:
        check_output(['tar', '-xf', out_path, '-C', out_dir])
    else:
        with tarfile.open(out_path) as out:
            out.extractall(out_dir)

    check(out_dir, links=(not on_win), root=root)
