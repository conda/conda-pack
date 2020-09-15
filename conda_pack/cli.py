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


def build_parser():
    description = "Package an existing conda environment into an archive file."
    kwargs = dict(prog="conda-pack",
                  description=description,
                  add_help=False)
    if sys.version_info >= (3, 5):
        kwargs['allow_abbrev'] = False
    parser = argparse.ArgumentParser(**kwargs)
    parser.add_argument("--name", "-n",
                        metavar="ENV",
                        help="The name of the environment to pack. "
                        "If neither --name nor --prefix are supplied, "
                        "the current activated environment is packed.")
    parser.add_argument("--prefix", "-p",
                        metavar="PATH",
                        help="The path to the environment to pack. "
                        "Only one of --name/--prefix should be supplied.")
    parser.add_argument("--output", "-o",
                        metavar="PATH",
                        help=("The path of the output file. Defaults to the "
                              "environment name with a ``.tar.gz`` suffix "
                              "(e.g.  ``my_env.tar.gz``)."))
    parser.add_argument("--arcroot",
                        metavar="PATH", default='',
                        help=("The relative path in the archive to the conda "
                              "environment. Defaults to ''."))
    parser.add_argument("--dest-prefix", "-d",
                        metavar="PATH",
                        help=("If present, prefixes will be rewritten to this "
                              "path before packaging. In this case the "
                              "`conda-unpack` script will not be generated. "
                              "This option should not be used with parcels, which "
                              "instead generate their destination prefix from the "
                              "--parcel-root, --parcel-name, and "
                              "--parcel-version options."))
    parser.add_argument("--parcel-root", default=None,
                        help="(Parcels only) The location where all parcels are unpacked "
                        "on the target Hadoop cluster (default: '/opt/cloudera/parcels').")
    parser.add_argument("--parcel-name", default=None,
                        help="(Parcels only) The name of the parcel, without a version "
                        "suffix. The default value is the local environment name. The parcel "
                        "name may not have any hyphens.")
    parser.add_argument("--parcel-version", default=None,
                        help="(Parcels only) The version number for the parcel. The default "
                        "value is the current date, using the format YYYY.MM.DD.")
    parser.add_argument("--parcel-distro", default=None,
                        help="(Parcels only) The distribution type for the parcel. The "
                        "default value is 'el7'. This value cannot have any hyphens.")
    parser.add_argument("--format",
                        choices=['infer', 'zip', 'tar.gz', 'tgz', 'tar.bz2',
                                 'tbz2', 'tar', 'parcel'],
                        default='infer',
                        help=("The archival format to use. By default this is "
                              "inferred by the output file extension."))
    parser.add_argument("--compress-level",
                        metavar="LEVEL",
                        type=int,
                        default=4,
                        help=("The compression level to use, from 0 to 9. "
                              "Higher numbers decrease output file size at "
                              "the expense of compression time. Ignored for "
                              "``format='zip'``. Default is 4."))
    parser.add_argument("--n-threads", "-j",
                        metavar="N",
                        type=int,
                        default=1,
                        help=("The number of threads to use. Set to -1 to use "
                              "the number of cpus on this machine. If a file "
                              "format doesn't support threaded packaging, this "
                              "option will be ignored. Default is 1."))
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
    parser.add_argument("--no-zip-64",
                        action="store_true",
                        help="Disable ZIP64 extensions.")
    parser.add_argument("--ignore-editable-packages",
                        action="store_true",
                        help="Skips checks for editable packages.")
    parser.add_argument("--ignore-missing-files",
                        action="store_true",
                        help="Skip checks for missing package files.")
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
    parser.add_argument("--force", "-f",
                        action="store_true",
                        help="Overwrite any existing archive at the output path.")
    parser.add_argument("--quiet", "-q",
                        action="store_true",
                        help="Do not report progress")
    parser.add_argument("--help", "-h", action='help',
                        help="Show this help message then exit")
    parser.add_argument("--version",
                        action='store_true',
                        help="Show version then exit")
    return parser


# Parser at top level to allow sphinxcontrib.autoprogram to work
PARSER = build_parser()


def fail(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)


def main(args=None, pack=pack):
    args = PARSER.parse_args(args=args)

    # Manually handle version printing to output to stdout in python < 3.4
    if args.version:
        print('conda-pack %s' % __version__)
        sys.exit(0)

    try:
        with context.set_cli():
            pack(name=args.name,
                 prefix=args.prefix,
                 output=args.output,
                 format=args.format,
                 force=args.force,
                 compress_level=args.compress_level,
                 n_threads=args.n_threads,
                 zip_symlinks=args.zip_symlinks,
                 zip_64=not args.no_zip_64,
                 arcroot=args.arcroot,
                 dest_prefix=args.dest_prefix,
                 parcel_root=args.parcel_root,
                 parcel_name=args.parcel_name,
                 parcel_version=args.parcel_version,
                 parcel_distro=args.parcel_distro,
                 verbose=not args.quiet,
                 filters=args.filters,
                 ignore_editable_packages=args.ignore_editable_packages,
                 ignore_missing_files=args.ignore_missing_files)
    except CondaPackException as e:
        fail("CondaPackError: %s" % e)
    except KeyboardInterrupt:
        fail("Interrupted")
    except Exception:
        fail(traceback.format_exc())
    sys.exit(0)


if __name__ == '__main__':
    main()
