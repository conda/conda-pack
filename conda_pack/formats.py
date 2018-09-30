import libarchive
import os
import stat
import sys
import tarfile
import tempfile
import time
import zipfile
from contextlib import contextmanager
from io import BytesIO

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
        return TarZstArchive(fileobj, filename, arcroot, _tar_mode[format],
                          compress_level=compress_level)
    else:
        return TarArchive(fileobj, filename, arcroot, _tar_mode[format],
                          compress_level=compress_level)

class ArchiveBase(object):
    def __exit__(self, *args):
        if hasattr(self.archive, "close"):
            self.archive.close()

    def add(self, source, target):
        target = os.path.join(self.arcroot, target)
        self._add(source, target)

    def add_bytes(self, source, sourcebytes, target):
        target = os.path.join(self.arcroot, target)
        self._add_bytes(source, sourcebytes, target)


class TarArchive(ArchiveBase):
    def __init__(self, fileobj, filename, arcroot, mode, compress_level):
        self.fileobj = fileobj
        self.filename = filename
        self.arcroot = arcroot
        self.mode = mode
        self.compress_level = compress_level

    def __enter__(self):
        if self.mode != 'w':
            kwargs = {'compresslevel': self.compress_level}
        else:
            kwargs = {}

        self.archive = tarfile.open(fileobj=self.fileobj, mode=self.mode,
                                    dereference=False, **kwargs)
        return self

    def _add(self, source, target):
        self.archive.add(source, target, recursive=False)

    def _add_bytes(self, source, sourcebytes, target):
        info = self.archive.gettarinfo(source, target)
        info.size = len(sourcebytes)
        self.archive.addfile(info, BytesIO(sourcebytes))

@contextmanager
def tmp_chdir(dest):
    curdir = os.getcwd()
    try:
        os.chdir(dest)
        yield
    finally:
        os.chdir(curdir)


class NewArchiveWrite(libarchive.ArchiveWrite):
    def __init__(self, filename, format_name, filter_name=None, options=''):
        from libarchive import ffi
        self.filename = filename
        self.archive_p = ffi.write_new()
        libarchive.ArchiveWrite.__init__(self, self.archive_p)
        getattr(ffi, 'write_set_format_' + format_name)(self.archive_p)
        if filter_name:
            getattr(ffi, 'write_add_filter_' + filter_name)(self.archive_p)
        if options:
            if not isinstance(options, bytes):
                options = options.encode('utf-8')
            ffi.write_set_options(self.archive_p, options)
        ffi.write_open_filename_w(self.archive_p, self.filename)

    def __del__(self):
        from libarchive import ffi
        ffi.write_close(self.archive_p)
        ffi.write_free(self.archive_p)


class TarZstArchive(ArchiveBase):
    def __init__(self, fileobj, filename, arcroot, mode, compress_level):
        self.fileobj = fileobj
        self.filename = filename
        self.arcroot = arcroot
        self.mode = mode
        self.compress_level = compress_level

    def __enter__(self):
        if self.mode != 'w':
            kwargs = {'compresslevel': self.compress_level}
        else:
            kwargs = {}

        # Context manager shennanigans.
        self.archive = None
        self.archive = NewArchiveWrite(self.filename, 'ustar', filter_name='zstd', options=self.mode)

        return self

    def __exit__(self, type, value, traceback):
        del self.archive

    def libarchive_write(self, temp_path, target, archive_filename, container, filter_name, options):
        with tmp_chdir(temp_path):
            self.archive.add_files(target)


    def _add_via_tempfile(self, target, bytes_or_sourcefile):
        temp_path = tempfile.mkdtemp()
        target_file = os.path.join(temp_path, target)
        os.makedirs(os.path.dirname(target_file))
        if isinstance(bytes_or_sourcefile, (bytes, bytearray)):
            with open(target_file, 'wb') as temp_file:
                temp_file.write(bytes_or_sourcefile)
        else:
            from shutil import copyfile
            copyfile(bytes_or_sourcefile, target_file)
        self.libarchive_write(temp_path, target, self.filename, 'ustar', filter_name='zstd', options=self.mode)


    def _add(self, source, target):
        if source.endswith(target):
            self.libarchive_write(source.replace(target, ""), target, self.filename, 'ustar', filter_name='zstd',
                                  options=self.mode)
        else:
            self._add_via_tempfile(target, source)

    def _add_bytes(self, source, sourcebytes, target):
        self._add_via_tempfile(target, sourcebytes)

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
                    self.archive.write(source, target)
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
