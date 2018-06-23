from __future__ import absolute_import, print_function, division

import os
import signal
import tarfile
import time
from subprocess import Popen, PIPE

import pytest

import conda_pack
from conda_pack.cli import main

from .conftest import py36_path, py27_path


def test_help(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["-h"])

    assert exc.value.code == 0

    out, err = capsys.readouterr()
    assert not err
    assert 'usage: conda-pack' in out


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])

    assert exc.value.code == 0

    out, err = capsys.readouterr()
    assert not err
    assert conda_pack.__version__ in out


def test_parse_include_exclude():
    out = {}

    def capture(**kwargs):
        out.update(kwargs)

    with pytest.raises(SystemExit) as exc:
        main(["--exclude", "foo/*",
              "--include", "*.py",
              "--include", "*.pyx",
              "--exclude", "foo/bar/*.pyx"],
             pack=capture)

    assert exc.value.code == 0

    assert out['filters'] == [("exclude", "foo/*"),
                              ("include", "*.py"),
                              ("include", "*.pyx"),
                              ("exclude", "foo/bar/*.pyx")]


def test_cli_roundtrip(capsys, tmpdir):
    out_path = os.path.join(str(tmpdir), 'py36.tar')

    with pytest.raises(SystemExit) as exc:
        main(["-p", py36_path, "-o", out_path])

    assert exc.value.code == 0

    assert os.path.exists(out_path)
    assert tarfile.is_tarfile(out_path)

    out, err = capsys.readouterr()
    assert not err

    bar, percent, time = [i.strip() for i in out.split('\r')[-1].split('|')]
    assert bar == '[' + '#' * 40 + ']'
    assert percent == '100% Completed'
    assert time


def test_quiet(capsys, tmpdir):
    out_path = os.path.join(str(tmpdir), 'py36.tar')

    with pytest.raises(SystemExit) as exc:
        main(["-p", py36_path, "-o", out_path, "-q"])

    assert exc.value.code == 0

    assert os.path.exists(out_path)
    assert tarfile.is_tarfile(out_path)

    out, err = capsys.readouterr()
    assert not err
    assert not out


def test_cli_exceptions(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["-p", "not_a_real_path"])

    assert exc.value.code == 1

    out, err = capsys.readouterr()
    assert "CondaPackError: Environment path" in err

    with pytest.raises(SystemExit) as exc:
        main(["-foo", "-bar"])

    assert exc.value.code != 0

    out, err = capsys.readouterr()
    assert not out
    assert "usage: conda-pack" in err


def test_cli_warnings(capsys, broken_package_cache, tmpdir):
    out_path = os.path.join(str(tmpdir), 'py27.tar')

    with pytest.raises(SystemExit) as exc:
        main(["-p", py27_path, "-o", out_path])

    assert exc.value.code == 0

    assert os.path.exists(out_path)
    assert tarfile.is_tarfile(out_path)

    out, err = capsys.readouterr()
    assert "Conda-managed packages were found" in err
    assert "UserWarning" not in err  # printed, not from python warning


def test_keyboard_interrupt(tmpdir):
    out_path = os.path.join(str(tmpdir), 'py36.tar')

    proc = Popen('conda-pack -p %s -o %s' % (py36_path, out_path),
                 stdout=PIPE, stderr=PIPE, shell=True)

    time.sleep(0.5)
    proc.send_signal(signal.SIGINT)

    outcode = proc.wait()

    out = proc.stdout.read().decode()
    err = proc.stderr.read().decode()

    print(out)
    print(err)
    assert outcode == 1
    assert err == 'Interrupted\n'
    assert not os.path.exists(out_path)
