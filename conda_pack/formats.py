from __future__ import print_function, division, absolute_import

import errno
import os
import stat
import struct
import sys
import tarfile
import threading
import time
import zipfile
import zlib

from contextlib import closing
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


def archive(fileobj, arcroot, format, compress_level=4, zip_symlinks=False,
            zip_64=True, n_threads=1):

    n_threads = _parse_n_threads(n_threads)

    if format == 'zip':
        return ZipArchive(fileobj, arcroot, zip_symlinks=zip_symlinks,
                          zip_64=zip_64)

    # Tar archives
    if format in ('tar.gz', 'tgz', 'parcel'):
        if n_threads == 1:
            mode = 'w:gz'
            close_file = False
        else:
            mode = 'w'
            close_file = True
            fileobj = ParallelGzipFileWriter(fileobj, compresslevel=compress_level,
                                             n_threads=n_threads)
    elif format in ('tar.bz2', 'tbz2'):
        if n_threads == 1:
            mode = 'w:bz2'
            close_file = False
        else:
            mode = 'w'
            close_file = True
            fileobj = ParallelBZ2FileWriter(fileobj, compresslevel=compress_level,
                                            n_threads=n_threads)
    else:  # format == 'tar'
        mode = 'w'
        close_file = False
    return TarArchive(fileobj, arcroot, close_file=close_file,
                      mode=mode, compresslevel=compress_level)


class ParallelFileWriter(object):
    def __init__(self, fileobj, compresslevel=9, n_threads=1):
        self.fileobj = fileobj
        self.compresslevel = compresslevel
        self.n_threads = n_threads

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


class ArchiveBase(object):
    def add(self, source, target):
        target = os.path.join(self.arcroot, target)
        self._add(source, target)

    def add_bytes(self, source, sourcebytes, target):
        target = os.path.join(self.arcroot, target)
        self._add_bytes(source, sourcebytes, target)


class TarArchive(ArchiveBase):
    def __init__(self, fileobj, arcroot, close_file=False,
                 mode='w', compresslevel=4):
        self.fileobj = fileobj
        self.arcroot = arcroot
        self.close_file = close_file
        self.mode = mode
        self.compresslevel = compresslevel

    def __enter__(self):
        kwargs = {'compresslevel': self.compresslevel} if self.mode != 'w' else {}
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
    def __init__(self, fileobj, arcroot, zip_symlinks=False, zip_64=True):
        self.fileobj = fileobj
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
                                source = os.path.basename(source[:-len(target)-1])
                                source = '{}: {}'.format(source, target)
                            msg = _dangling_link_error.format(source)
                            raise CondaPackException(msg)
                        raise
        else:
            self.archive.write(source, target)

    def _add_bytes(self, source, sourcebytes, target):
        info = zipinfo_from_file(source, target)
        self.archive.writestr(info, sourcebytes)


if sys.version_info >= (3, 6):
    zipinfo_from_file = zipfile.ZipInfo.from_file
else:  # pragma: no cover
    # Backported from python 3.6
    def zipinfo_from_file(filename, arcname=None):
        st = os.stat(filename)
        isdir = stat.S_ISDIR(st.st_mode)
        mtime = time.localtime(st.st_mtime)
        date_time = mtime[0:6]
        # Create ZipInfo instance to store file information
        if arcname is None:
            arcname = filename
        arcname = os.path.normpath(os.path.splitdrive(arcname)[1])
        while arcname[0] in (os.sep, os.altsep):
            arcname = arcname[1:]
        if isdir:
            arcname += '/'
        zinfo = zipfile.ZipInfo(arcname, date_time)
        zinfo.external_attr = (st.st_mode & 0xFFFF) << 16  # Unix attributes
        if isdir:
            zinfo.file_size = 0
            zinfo.external_attr |= 0x10  # MS-DOS directory flag
        else:
            zinfo.file_size = st.st_size

        return zinfo
