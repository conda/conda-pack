from __future__ import print_function, absolute_import

import json
import os
import sys
import traceback
import zipfile
from subprocess import check_output

import click


_VERSION = '0.0.1'
_ENCODING = sys.getdefaultencoding()


class CondaPackException(Exception):
    """Internal exception to report to user"""
    pass


def zip_dir(directory, fname):
    # The top-level folder in the zipfile
    env_name = os.path.splitext(os.path.split(fname)[-1])[0]
    zFile = zipfile.ZipFile(fname, "w", allowZip64=True,
                            compression=zipfile.ZIP_DEFLATED)
    try:
        for root, dirs, files in os.walk(directory, followlinks=True):
            to_root = os.path.join(env_name, os.path.relpath(root, directory))
            for f in files:
                from_path = os.path.join(root, f)
                to_path = os.path.join(to_root, f)
                zFile.write(from_path, to_path)
    finally:
        zFile.close()


@click.command()
@click.option("--name",
              "-n",
              required=False,
              help=("Name of existing environment. Default is current "
                    "environment."))
@click.option("--prefix",
              "-p",
              type=click.Path(),
              required=False,
              help="Full path to environment prefix.")
@click.option("--output",
              "-o",
              "output",
              type=click.Path(),
              required=False,
              help="Output zip file. Defaults to the environment name.")
@click.version_option(prog_name="conda-pack", version=_VERSION)
def cli(name, prefix, output):
    """
    Package an existing conda environment into a zip file

    Usage:
        conda-pack -n myenv
        conda-pack -p /home/ubuntu/myenv
        conda-pack -n myenv -o myenv.zip
    """
    if name and prefix:
        raise CondaPackException("Cannot specify both --name and --prefix.")
    elif prefix:
        env_dir = prefix
        if not os.path.exists(env_dir):
            raise CondaPackException("Environment path %r doesn't "
                                     "exist" % env_dir)
    else:
        info = check_output("conda info --json", shell=True).decode(_ENCODING)
        info2 = json.loads(info)

        if name:
            env_lk = {os.path.basename(e): e for e in info2['envs']}
            try:
                env_dir = env_lk[name]
            except KeyError:
                raise CondaPackException("Environment name %r doesn't "
                                         "exist" % name)
        else:
            env_dir = info2['default_prefix']

    if not output:
        env_name = os.path.basename(env_dir)
        output = os.extsep.join([env_name, 'zip'])

    if os.path.exists(output):
        raise CondaPackException("File %r already exists" % output)

    zip_dir(env_dir, output)


_py3_err_msg = """
Your terminal does not properly support unicode text required by command line
utilities running Python 3. This is commonly solved by specifying encoding
environment variables, though exact solutions may depend on your system:
    $ export LC_ALL=C.UTF-8
    $ export LANG=C.UTF-8
For more information see: http://click.pocoo.org/5/python3/
""".strip()


def main():
    # Pre-check for python3 unicode settings
    try:
        from click import _unicodefun
        _unicodefun._verify_python3_env()
    except (TypeError, RuntimeError) as e:
        click.echo(_py3_err_msg, err=True)

    # run main
    try:
        cli()
    except CondaPackException as e:
        click.echo("CondaPackError: %s" % e, err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(traceback.format_exc(), err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
