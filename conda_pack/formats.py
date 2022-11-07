import errno
import os
import shutil
import stat
import struct
import subprocess
import tarfile
import tempfile
import threading
import time
import zipfile
import zlib
from contextlib import closing
from functools import partial
from io import BytesIO
from .formats_base import ArchiveBase

_tar_mode = {'tar.gz': 'w:gz',
             'tgz': 'w:gz',
             'tar.bz2': 'w:bz2',
             'tbz2': 'w:bz2',
             'tar': 'w',
             'tar.zst': 'zstd:compression-level=22'}


def archive(fileobj, filename, arcroot, format, compress_level=4, zip_symlinks=False,
            zip_64=True):
    if format == 'zip':
        return ZipArchive(fileobj, filename, arcroot, zip_symlinks=zip_symlinks,
                          zip_64=zip_64)
    elif format == 'tar.zst':
        from .formats_libarchive import TarZstArchive
        return TarZstArchive(fileobj, filename, arcroot, _tar_mode[format],
                             compress_level=compress_level)
    else:
        return TarArchive(fileobj, filename, arcroot, _tar_mode[format],
                          compress_level=compress_level)


class TarArchive(ArchiveBase):
    def __init__(self, fileobj, filename, arcroot, mode, compress_level):
        self.fileobj = fileobj
        self.filename = filename
        self.arcroot = arcroot
        self.close_file = close_file
        self.mode = mode
        self.compresslevel = compresslevel

    def __enter__(self):
        kwargs = {'compresslevel': self.compresslevel} if self.mode not in {'w', 'w:xz'} else {}
        # Hard links seem to throw off the tar file format on windows.
        # Revisit when libarchive is used.
        self.archive = tarfile.open(fileobj=self.fileobj,
                                    dereference=on_win,
                                    mode=self.mode,
                                    **kwargs)
        return self

    def __exit__(self, *args):
        self.archive.close()
        if self.close_file:
            self.fileobj.close()

    def _add(self, source, target):
        self.archive.add(source, target, recursive=False)

    def _add_bytes(self, source, sourcebytes, target):
        info = self.archive.gettarinfo(source, target)
        info.size = len(sourcebytes)
        self.archive.addfile(info, BytesIO(sourcebytes))


_dangling_link_error = """
The following conda package file is a symbolic link that does not match an
existing file within the same package:

    {0}

It is likely this link points to a file brought into the environment by
a dependency. Unfortunately, conda-pack does not support this practice
for zip files unless the --zip-symlinks option is engaged. Please see
"conda-pack --help" for more information about this option, or use a
tar-based archive format instead."""


class ZipArchive(ArchiveBase):
    def __init__(self, fileobj, filename, arcroot, zip_symlinks=False, zip_64=True):
        self.fileobj = fileobj
        self.filename = filename
        self.arcroot = arcroot
        self.zip_symlinks = zip_symlinks
        self.zip_64 = zip_64

    def __enter__(self):
        self.archive = zipfile.ZipFile(self.fileobj, "w",
                                       allowZip64=self.zip_64,
                                       compression=zipfile.ZIP_DEFLATED)
        return self

    def __exit__(self, type, value, traceback):
        self.archive.close()
        if isinstance(value, zipfile.LargeZipFile):
            raise CondaPackException(
                "Large Zip File: ZIP64 extensions required "
                "but were disabled")

    def _add(self, source, target):
        try:
            st = os.lstat(source)
            is_link = stat.S_ISLNK(st.st_mode)
        except (OSError, AttributeError):
            is_link = False

        if is_link:
            if self.zip_symlinks:
                info = zipfile.ZipInfo(target)
                info.create_system = 3
                info.external_attr = (st.st_mode & 0xFFFF) << 16
                if os.path.isdir(source):
                    info.external_attr |= 0x10  # MS-DOS directory flag
                self.archive.writestr(info, os.readlink(source))
            else:
                if os.path.isdir(source):
                    for root, dirs, files in os.walk(source, followlinks=True):
                        root2 = os.path.join(target, os.path.relpath(root, source))
                        for fil in files:
                            self.archive.write(os.path.join(root, fil),
                                               os.path.join(root2, fil))
                        if not dirs and not files:
                            # root is an empty directory, write it now
                            self.archive.write(root, root2)
                else:
                    try:
                        self.archive.write(source, target)
                    except OSError as e:
                        if e.errno == errno.ENOENT:
                            if source[-len(target):] == target:
                                # For managed packages, this will give us the package name
                                # followed by the relative path within the environment, a
                                # more readable result.
                                source = os.path.basename(source[: -len(target) - 1])
                                source = f"{source}: {target}"
                            msg = _dangling_link_error.format(source)
                            raise CondaPackException(msg)
                        raise
        else:
            self.archive.write(source, target)

    def _add_bytes(self, source, sourcebytes, target):
        info = zipinfo_from_file(source, target)
        self.archive.writestr(info, sourcebytes)


zipinfo_from_file = zipfile.ZipInfo.from_file


class SquashFSArchive(ArchiveBase):
    def __init__(self, fileobj, target_path, arcroot, n_threads, verbose=False,
                 compress_level=4):
        if shutil.which("mksquashfs") is None:
            raise SystemError("Command 'mksquashfs' not found. Please install it, "
                              "e.g. 'conda install squashfs-tools'.")
        # we don't need fileobj, just the name of the file
        self.target_path = target_path
        self.arcroot = arcroot
        self.n_threads = n_threads
        self.verbose = verbose
        self.compress_level = compress_level

    def __enter__(self):
        # create a staging directory where we will collect
        # hardlinks to files and make tmpfiles for bytes
        self._staging_dir = os.path.normpath(tempfile.mkdtemp())
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        shutil.rmtree(self._staging_dir)

    def mksquashfs_from_staging(self):
        """
        After building the staging directory, squash it into file
        """
        cmd = [
            "mksquashfs",
            self._staging_dir,
            self.target_path,
            "-noappend",
            "-processors",
            str(self.n_threads),
            "-quiet",  # will still display native progressbar
        ]

        if self.compress_level == 0:
            # No compression
            comp_algo_str = "None"
            cmd += ["-noI", "-noD", "-noF", "-noX"]
        elif self.compress_level == 9:
            comp_algo_str = "xz"
            cmd += ["-comp", comp_algo_str]
        else:
            comp_level = int(self.compress_level / 8 * 20)
            comp_algo_str = f"zstd (level {comp_level})"
            # 256KB block size instead of the default 128KB for slightly smaller archive sizes
            cmd += ["-comp", "zstd", "-Xcompression-level", str(comp_level), "-b", str(256*1024)]

        if self.verbose:
            s = "Running mksquashfs with {} compression (processors: {}).".format(
                comp_algo_str, self.n_threads)
            if self.compress_level != 9:
                s += "\nWill require kernel>=4.14 or squashfuse>=0.1.101 (compiled with zstd) " \
                     "for mounting.\nTo support older systems, compress with " \
                     "`xz` (--compress-level 9) instead."
            print(s)
        else:
            cmd.append("-no-progress")
        subprocess.check_call(cmd)

    def _absolute_path(self, path):
        return os.path.normpath(os.path.join(self._staging_dir, path))

    def _ensure_parent(self, path):
        dir_path = os.path.dirname(path)
        os.makedirs(dir_path, exist_ok=True)

    def _add(self, source, target):
        target_abspath = self._absolute_path(target)
        self._ensure_parent(target_abspath)

        # hardlink instead of copy is faster, but it doesn't work across devices
        same_device = os.lstat(source).st_dev == os.lstat(os.path.dirname(target_abspath)).st_dev
        if same_device:
            copy_func = partial(os.link, follow_symlinks=False)
        else:
            copy_func = partial(shutil.copy2, follow_symlinks=False)

        # we overwrite if the same `target` is added twice
        # to be consistent with the tar-archive implementation
        if os.path.lexists(target_abspath):
            os.remove(target_abspath)

        if os.path.isdir(source) and not os.path.islink(source):
            # directories we add through copying the tree
            shutil.copytree(source,
                            target_abspath,
                            symlinks=True,
                            copy_function=copy_func)
        else:
            # files & links to directories we copy directly
            copy_func(source, target_abspath)

    def _add_bytes(self, source, sourcebytes, target):
        target_abspath = self._absolute_path(target)
        self._ensure_parent(target_abspath)
        with open(target_abspath, "wb") as f:
            shutil.copystat(source, target_abspath)
            f.write(sourcebytes)
