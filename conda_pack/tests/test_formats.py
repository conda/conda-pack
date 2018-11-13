import os
import shutil
import tarfile
import threading
import zipfile
from multiprocessing import cpu_count
from os.path import isdir, isfile, islink, join, exists
from subprocess import check_output, STDOUT

import pytest

from conda_pack.core import CondaPackException
from conda_pack.formats import archive, _parse_n_threads
from conda_pack.compat import on_win


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
        if not on_win:
            target = os.path.relpath(target, os.path.dirname(path))
            os.symlink(target, path)
        # Copy the files instead of symlinking
        elif isdir(target):
            shutil.copytree(target, path)
        else:
            shutil.copyfile(target, path)

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
        assert set(os.listdir(join(out_dir, "link_to_dir"))) == {'one', 'two'}


def has_infozip():
    try:
        out = check_output(['unzip', '-h'], stderr=STDOUT).decode()
    except Exception:
        return False
    return "Info-ZIP" in out


@pytest.mark.parametrize('format', ['zip', 'tar.gz', 'tar.bz2', 'tar'])
def test_format(tmpdir, format, root_and_paths):
    # Test symlinks whenever possible:
    # - not on windows
    # - not with zip files unless InfoZIP is installed
    symlinks = not on_win and (format != 'zip' or has_infozip())

    root, paths = root_and_paths

    out_path = join(str(tmpdir), 'test.' + format)
    out_dir = join(str(tmpdir), 'test')
    os.mkdir(out_dir)

    with open(out_path, mode='wb') as fil:
        with archive(fil, '', format, zip_symlinks=symlinks) as arc:
            for rel in paths:
                arc.add(join(root, rel), rel)
            arc.add_bytes(join(root, "file"),
                          b"foo bar",
                          join("dir", "from_bytes"))

    if format == 'zip':
        if symlinks:
            check_output(['unzip', out_path, '-d', out_dir])
        else:
            with zipfile.ZipFile(out_path) as out:
                out.extractall(out_dir)
    else:
        with tarfile.open(out_path) as out:
            out.extractall(out_dir)

    check(out_dir, links=symlinks, root=root)
    assert isfile(join(out_dir, "dir", "from_bytes"))
    with open(join(out_dir, "dir", "from_bytes"), 'rb') as fil:
        assert fil.read() == b"foo bar"


def test_n_threads():
    assert _parse_n_threads(-1) == cpu_count()
    assert _parse_n_threads(40) == 40

    for n in [-10, 0]:
        with pytest.raises(CondaPackException):
            _parse_n_threads(n)


@pytest.mark.parametrize('format', ['tar.gz', 'tar.bz2'])
def test_format_parallel(tmpdir, format, root_and_paths):
    root, paths = root_and_paths

    out_path = join(str(tmpdir), 'test.' + format)
    out_dir = join(str(tmpdir), 'test')
    os.mkdir(out_dir)

    active = threading.active_count()
    with open(out_path, mode='wb') as fil:
        with archive(fil, '', format, n_threads=2) as arc:
            for rel in paths:
                arc.add(join(root, rel), rel)
    current = threading.active_count()
    assert active == current

    with tarfile.open(out_path) as out:
        out.extractall(out_dir)

    check(out_dir, links=(not on_win), root=root)
