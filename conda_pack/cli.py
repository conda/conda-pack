from __future__ import print_function, absolute_import

import sys
import traceback

import click

from . import pack, CondaPackException, __version__


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
@click.option("--packed-prefix",
              type=click.Path(),
              required=False,
              help=("Directory prefix in the archive to the conda "
                    "environment. Defaults to the environment name."))
@click.version_option(prog_name="conda-pack", version=__version__)
def cli(name, prefix, output, packed_prefix):
    """Package an existing conda environment into a zip file"""
    pack(name=name, prefix=prefix, output=output, packed_prefix=packed_prefix)


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
