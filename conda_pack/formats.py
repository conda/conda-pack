import errno
import gzip
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
from multiprocessing.pool import ThreadPool

from .compat import Queue, on_win
from .core import CondaPackException


def _parse_n_threads(n_threads=1):
    if n_threads == -1:
        from multiprocessing import cpu_count
        return cpu_count()
    if n_threads < 1:
        raise CondaPackException("n-threads must be >= 1, or -1 for all cores")
    return n_threads


def archive(
    fileobj,
    path,
    arcroot,
    format,
    compress_level=4,
    zip_symlinks=False,
    zip_64=True,
    n_threads=1,
    verbose=False,
    output=None,
    mtime=None,
):

    n_threads = _parse_n_threads(n_threads)

    if format == 'zip':
        return ZipArchive(fileobj, arcroot, compresslevel=compress_level,
                          zip_symlinks=zip_symlinks, zip_64=zip_64)

    # Tar archives
    if format in ('tar.gz', 'tgz', 'parcel'):
        if n_threads == 1:
            mode = "w"
            close_file = True
            fileobj = gzip.GzipFile(
                fileobj=fileobj, mode="w", compresslevel=compress_level, mtime=mtime
            )
        else:
            mode = 'w'
            close_file = True
            fileobj = ParallelGzipFileWriter(
                fileobj, compresslevel=compress_level, n_threads=n_threads, mtime=mtime
            )
    elif format in ("tar.bz2", "tbz2"):
        if n_threads == 1:
            mode = 'w:bz2'
            close_file = False
        else:
            mode = 'w'
            close_file = True
            fileobj = ParallelBZ2FileWriter(fileobj, compresslevel=compress_level,
                                            n_threads=n_threads)
    elif format in ('tar.xz', 'txz'):
        if n_threads == 1:
            mode = 'w:xz'
            close_file = False
        else:
            mode = 'w'
            close_file = True
            fileobj = ParallelXZFileWriter(fileobj, compresslevel=compress_level,
                                           n_threads=n_threads)
    elif format in ("tar.zst", "tzst"):
        # python's tarfile doesn't support zstd natively yet
        mode = "w"
        close_file = True
        fileobj = ParallelZstdFileWriter(fileobj)
    elif format == "squashfs":
        return SquashFSArchive(fileobj, path, arcroot, n_threads, verbose=verbose,
                               compress_level=compress_level)
    elif format == "no-archive":
        return NoArchive(output, arcroot)
    else:  # format == 'tar'
        mode = 'w'
        close_file = False
    return TarArchive(
        fileobj,
        arcroot,
        close_file=close_file,
        mode=mode,
        compresslevel=compress_level,
        mtime=mtime,
    )


class ParallelZstdFileWriter:
    def __init__(self, fileobj, compresslevel=9, n_threads=1, mtime=None):
        import zstandard

        self.cctx = zstandard.ZstdCompressor(level=compresslevel, threads=n_threads)
        self.compressor = self.cctx.stream_writer(fileobj)

    def write(self, data: bytes):
        self.compressor.write(data)

    def tell(self):
        return self.compressor.tell()

    def close(self):
        import zstandard

        self.compressor.flush(zstandard.FLUSH_FRAME)


class ParallelFileWriter:
    def __init__(self, fileobj, compresslevel=9, n_threads=1, mtime=None):
        self.fileobj = fileobj
        self.compresslevel = compresslevel
        self.n_threads = n_threads
        self.mtime = mtime

        # Initialize file state
        self.size = 0
        self._init_state()
        self._write_header()

        # Parallel initialization
        self.buffers = []
        self.buffer_length = 0

        self.pool = ThreadPool(n_threads)
        self.compress_queue = Queue(maxsize=n_threads)

        self._consumer_thread = threading.Thread(target=self._consumer)
        self._consumer_thread.daemon = True
        self._consumer_thread.start()

    def tell(self):
        return self.size

    def write(self, data):
        if not isinstance(data, bytes):
            data = memoryview(data)
        n = len(data)
        if n > 0:
            self._per_buffer_op(data)
            self.size += n
            self.buffer_length += n
            self.buffers.append(data)
            if self.buffer_length > self._block_size:
                self.compress_queue.put(self.buffers)
                self.buffers = []
                self.buffer_length = 0
        return n

    def _consumer(self):
        with closing(self.pool):
            for buffers in self.pool.imap(
                    self._compress, iter(self.compress_queue.get, None)):
                for buf in buffers:
                    if len(buf):
                        self.fileobj.write(buf)

    def _compress(self, in_bufs):
        out_bufs = []
        compressor = self._new_compressor()
        for data in in_bufs:
            out_bufs.append(compressor.compress(data))
        out_bufs.append(self._flush_compressor(compressor))
        return out_bufs

    def close(self):
        if self.fileobj is None:
            return

        # Flush any waiting buffers
        if self.buffers:
            self.compress_queue.put(self.buffers)

        # Wait for all work to finish
        self.compress_queue.put(None)
        self._consumer_thread.join()

        # Write the closing bytes
        self._write_footer()

        # Flush fileobj
        self.fileobj.flush()

        # Cache shutdown state
        self.compress_queue = None
        self.pool = None
        self.fileobj = None


class ParallelGzipFileWriter(ParallelFileWriter):
    # Since it's hard for us to keep a running dictionary (a serial operation)
    # with parallel compression of blocks, we use a blocksize > a few factors
    # bigger than the max dict size (32 KiB). In practice this is fine - we
    # only lose out by a small factor of unneeded redundancy, and real files
    # often lack enough redundant byte sequences to make this significant. Pigz
    # uses 128 KiB, but does more work to keep a running dict.
    _block_size = 256 * 2**10

    def _init_state(self):
        self.crc = zlib.crc32(b"") & 0xffffffff

    def _new_compressor(self):
        return zlib.compressobj(self.compresslevel, zlib.DEFLATED,
                                -zlib.MAX_WBITS, zlib.DEF_MEM_LEVEL, 0)

    def _per_buffer_op(self, buffer):
        self.crc = zlib.crc32(buffer, self.crc) & 0xffffffff

    def _write32u(self, value):
        self.fileobj.write(struct.pack("<L", value))

    def _write_header(self):
        self.fileobj.write(b'\037\213\010')
        self.fileobj.write(b'\x00')
        if self.mtime is not None:
            self._write32u(int(self.mtime))
        else:
            self._write32u(int(time.time()))
        self.fileobj.write(b'\002\377')

    def _write_footer(self):
        self.fileobj.write(self._new_compressor().flush(zlib.Z_FINISH))
        self._write32u(self.crc)
        self._write32u(self.size & 0xffffffff)

    def _flush_compressor(self, compressor):
        return compressor.flush(zlib.Z_FULL_FLUSH)


class ParallelBZ2FileWriter(ParallelFileWriter):
    def _init_state(self):
        # bzip2 compresslevel dictates its blocksize of 100 - 900 kb
        self._block_size = self.compresslevel * 100 * 2**10

    def _new_compressor(self):
        import bz2
        return bz2.BZ2Compressor(self.compresslevel)

    def _per_buffer_op(self, buffer):
        pass

    def _write_header(self):
        pass

    def _write_footer(self):
        pass

    def _flush_compressor(self, compressor):
        return compressor.flush()


class ParallelXZFileWriter(ParallelFileWriter):
    def _init_state(self):
        # from `man lzma`: uses dict sizes between 64 kb and 32 MB for the level presets.
        # 2-4 times the size (minimum 1 MB) is best for the block size.
        self._block_size = 4 * max(1, (2**(self.compresslevel - 4))) * 2**10 * 2**10

    def _new_compressor(self):
        import lzma
        return lzma.LZMACompressor(preset=self.compresslevel)

    def _per_buffer_op(self, buffer):
        pass

    def _write_header(self):
        pass

    def _write_footer(self):
        pass

    def _flush_compressor(self, compressor):
        return compressor.flush()


class ArchiveBase:
    def add(self, source, target):
        target = os.path.join(self.arcroot, target)
        self._add(source, target)

    def add_bytes(self, source, sourcebytes, target):
        target = os.path.join(self.arcroot, target)
        self._add_bytes(source, sourcebytes, target)


class TarArchive(ArchiveBase):
    def __init__(
        self, fileobj, arcroot, close_file=False, mode="w", compresslevel=4, mtime=None
    ):
        self.fileobj = fileobj
        self.arcroot = arcroot
        self.close_file = close_file
        self.mode = mode
        self.compresslevel = compresslevel
        self.mtime = mtime

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
        def filter_mtime(tarinfo):
            tarinfo.mtime = self.mtime
            return tarinfo

        if target == "bin/conda-unpack":
            self.archive.add(source, target, recursive=False, filter=filter_mtime)
        else:
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
    def __init__(self, fileobj, arcroot, compresslevel=4, zip_symlinks=False, zip_64=True):
        self.fileobj = fileobj
        self.arcroot = arcroot
        self.compresslevel = compresslevel
        self.zip_symlinks = zip_symlinks
        self.zip_64 = zip_64

    def __enter__(self):
        self.archive = zipfile.ZipFile(self.fileobj, "w",
                                       allowZip64=self.zip_64,
                                       compresslevel=self.compresslevel,
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
        self._temp_dir = os.path.normpath(tempfile.mkdtemp())
        self._staging_dir = os.path.join(self._temp_dir, "squashfs-root")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        shutil.rmtree(self._temp_dir)

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
        source_stat = os.lstat(source)
        target_stat = os.lstat(os.path.dirname(target_abspath))
        same_device = source_stat.st_dev == target_stat.st_dev
        same_user = source_stat.st_uid == target_stat.st_uid

        if same_device and same_user:
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


# Copies files to the output directory
class NoArchive(ArchiveBase):
    def __init__(self, output, arcroot):
        self.output = output
        self.arcroot = arcroot
        self.copy_func = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return self

    def _absolute_path(self, path):
        return os.path.normpath(os.path.join(self.output, path))

    def _ensure_parent(self, path):
        dir_path = os.path.dirname(path)
        os.makedirs(dir_path, exist_ok=True)

    def _add(self, source, target):
        target_abspath = self._absolute_path(target)
        self._ensure_parent(target_abspath)

        # hardlink instead of copy is faster, but it doesn't work across devices
        if self.copy_func is None:
            if os.lstat(source).st_dev == os.lstat(os.path.dirname(target_abspath)).st_dev:
                self.copy_func = partial(os.link, follow_symlinks=False)
            else:
                self.copy_func = partial(shutil.copy2, follow_symlinks=False)

        if os.path.isfile(source) or os.path.islink(source):
            self.copy_func(source, target_abspath)
        else:
            os.mkdir(target_abspath)

    def _add_bytes(self, source, sourcebytes, target):
        target_abspath = self._absolute_path(target)
        self._ensure_parent(target_abspath)
        with open(target_abspath, "wb") as f:
            shutil.copystat(source, target_abspath)
            f.write(sourcebytes)
