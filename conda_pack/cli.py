from __future__ import print_function, absolute_import

import argparse
import sys
import traceback

from . import __version__
from .core import pack, CondaPackException, context


class MultiAppendAction(argparse.Action):
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None:
            raise ValueError("nargs not allowed")
        super(MultiAppendAction, self).__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        if getattr(namespace, self.dest) is None:
            setattr(namespace, self.dest, [])
        getattr(namespace, self.dest).append((option_string.strip('-'), values))


def main():
    description = "Package an existing conda environment into an archive file."
    kwargs = dict(prog="conda-pack",
                  description=description,
                  add_help=False)
    if sys.version_info >= (3, 5):
        kwargs['allow_abbrev'] = False
    parser = argparse.ArgumentParser(**kwargs)
    parser.add_argument("--name", "-n",
                        metavar="ENV",
                        help=("Name of existing environment. Default is "
                              "current environment."))
    parser.add_argument("--prefix", "-p",
                        metavar="PATH",
                        help="Full path to environment prefix.")
    parser.add_argument("--output", "-o",
                        metavar="PATH",
                        help=("The path of the output file. Defaults to the "
                              "environment name with a ``.tar.gz`` suffix "
                              "(e.g.  ``my_env.tar.gz``)."))
    parser.add_argument("--arcroot",
                        metavar="PATH", default='',
                        help=("The relative path in the archive to the conda "
                              "environment. Defaults to ''."))
    parser.add_argument("--format",
                        choices=['infer', 'zip', 'tar.gz', 'tgz', 'tar.bz2',
                                 'tbz2', 'tar'],
                        default='infer',
                        help=("The archival format to use. By default this is "
                              "inferred by the output file extension."))
    parser.add_argument("--compress-level",
                        type=int,
                        default=4,
                        help=("The compression level to use, from 0 to 9. "
                              "Higher numbers decrease output file size at "
                              "the expense of compression time. Ignored for "
                              "``format='zip'``. Default is 4."))
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
    parser.add_argument("--exclude",
                        action=MultiAppendAction,
                        metavar="PATTERN",
                        dest="filters",
                        help="Exclude files matching this pattern")
    parser.add_argument("--include",
                        action=MultiAppendAction,
                        metavar="PATTERN",
                        dest="filters",
                        help="Re-add excluded files matching this pattern")
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
                 format=args.format, compress_level=args.compress_level,
                 zip_symlinks=args.zip_symlinks, arcroot=args.arcroot,
                 verbose=not args.quiet, filters=args.filters)
    except CondaPackException as e:
        print("CondaPackError: %s" % e, file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(traceback.format_exc(), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
