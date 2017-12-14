from __future__ import print_function, absolute_import

import argparse
import sys
import traceback

from . import __version__
from .core import pack, CondaPackException, context


def main():
    description = "Package an existing conda environment into an archive file."
    parser = argparse.ArgumentParser(prog="conda-pack",
                                     description=description,
                                     allow_abbrev=False,
                                     add_help=False)
    parser.add_argument("--name", "-n",
                        metavar="ENV",
                        help=("Name of existing environment. Default is "
                              "current environment."))
    parser.add_argument("--prefix", "-p",
                        metavar="PATH",
                        help="Full path to environment prefix.")
    parser.add_argument("--output", "-o",
                        metavar="PATH",
                        help="Output zip file. Defaults to the environment name.")
    parser.add_argument("--arcroot",
                        metavar="PATH",
                        help=("The relative in the archive to the conda "
                              "environment. Defaults to the environment name."))
    parser.add_argument("--format",
                        choices=['infer', 'zip', 'tar.gz', 'tgz', 'tar.bz2',
                                 'tbz2', 'tar'],
                        default='infer',
                        help=("The archival format to use. By default this is "
                              "inferred by the output file extension, falling "
                              "back to `zip` if a non-standard extension."))
    parser.add_argument("--zip-symlinks",
                        action="store_true",
                        help=("Symbolic links aren't supported by the Zip "
                              "standard, but are supported by *many* common "
                              "Zip implementations. If set, store symbolic "
                              "links in the archive, instead of the file "
                              "referred to by the link. This can avoid storing "
                              "multiple copies of the same files. *Note that "
                              "the resulting archive may silently fail on "
                              "decompression if the ``unzip`` implementation "
                              "doesn't support symlinks*. Ignored if format "
                              "isn't ``zip``."))
    parser.add_argument("--quiet", "-q",
                        action="store_true",
                        help="Do not report progress")
    parser.add_argument("--help", "-h", action='help',
                        help="Show this help message then exit")
    parser.add_argument("--version", action='version',
                        version='%(prog)s ' + __version__,
                        help="Show version then exit")

    args = parser.parse_args()

    try:
        with context.set_cli():
            pack(name=args.name, prefix=args.prefix, output=args.output,
                 format=args.format, zip_symlinks=args.zip_symlinks,
                 arcroot=args.arcroot, verbose=not args.quiet)
    except CondaPackException as e:
        print("CondaPackError: %s" % e, file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(traceback.format_exc(), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
