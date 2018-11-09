import os
import shutil
import tarfile
import zipfile
from io import BytesIO
from os.path import isdir, isfile, islink, join, exists
from subprocess import check_output, STDOUT

import pytest

from conda_pack.formats import archive
from conda_pack.compat import on_win


@pytest.fixture(scope="module")
def root_and_paths(tmpdir_factory):
    root = str(tmpdir_factory.mktemp('example_dir'))

    def mkfil(*paths):
        with open(join(root, *paths), mode='w'):
            pass

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
    check(root, not on_win)

    return root, paths


def check(out_dir, links=False):
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


@pytest.mark.parametrize('format', ['zip', 'tar.gz', 'tar.bz2', 'tar.zst', 'tar'])
def test_format(tmpdir, format, root_and_paths):
    if format == 'tar.zst':
        zstandard = pytest.importorskip('zstandard')

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
    elif format == 'tar.zst':
        dctx = zstandard.ZstdDecompressor()
        with open(out_path, 'rb') as fil:
            data = BytesIO()
            with dctx.stream_reader(fil) as reader:
                while True:
                    chunk = reader.read(16384)
                    if not chunk:
                        break
                    data.write(chunk)
        data.seek(0)
        with tarfile.open(fileobj=data) as out:
            out.extractall(out_dir)
    else:
        with tarfile.open(out_path) as out:
            out.extractall(out_dir)

    check(out_dir, links=symlinks)
    assert isfile(join(out_dir, "dir", "from_bytes"))
    with open(join(out_dir, "dir", "from_bytes"), 'rb') as fil:
        assert fil.read() == b"foo bar"
