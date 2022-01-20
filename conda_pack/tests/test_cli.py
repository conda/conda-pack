from __future__ import absolute_import, print_function, division

import os
import signal
import tarfile
import time
from threading import Thread

import pytest

import conda_pack
from conda_pack.cli import main
from conda_pack.compat import on_win

from .conftest import py37_path, py310_path


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
    out_path = os.path.join(str(tmpdir), 'py37.tar')

    with pytest.raises(SystemExit) as exc:
        main(["-p", py37_path, "-o", out_path])

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
    out_path = os.path.join(str(tmpdir), 'py37.tar')

    with pytest.raises(SystemExit) as exc:
        main(["-p", py37_path, "-o", out_path, "-q"])

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


def test_cli_warnings(capsys, tmpdir):
    out_path = os.path.join(str(tmpdir), 'py310.tar')

    with pytest.raises(SystemExit) as exc:
        main(["-p", py310_path, "-o", out_path])

    assert exc.value.code == 0

    assert os.path.exists(out_path)
    assert tarfile.is_tarfile(out_path)

    out, err = capsys.readouterr()
    assert "Conda-managed packages were found" in err
    assert "UserWarning" not in err  # printed, not from python warning


@pytest.mark.skipif(on_win, reason='SIGINT terminates the tests on Windows')
def test_keyboard_interrupt(capsys, tmpdir):
    def interrupt():
        time.sleep(0.2)
        os.kill(os.getpid(), signal.SIGINT)

    interrupter = Thread(target=interrupt)

    out_path = os.path.join(str(tmpdir), 'py37.tar')
    try:
        with pytest.raises(SystemExit) as exc:
            interrupter.start()
            main(["-p", py37_path, "-o", out_path])
    except KeyboardInterrupt:
        assert False, "Should have been caught by the CLI"

    assert exc.value.code == 1
    out, err = capsys.readouterr()
    assert err == 'Interrupted\n'
    assert not os.path.exists(out_path)
