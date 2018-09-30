import libarchive
import os
import tempfile
from .formats_base import ArchiveBase
from .core import tmp_chdir


class _NewArchiveWrite(libarchive.write.ArchiveWrite):
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

    def close(self):
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
        self.archive = _NewArchiveWrite(self.filename, 'ustar', filter_name='zstd',
                                        options=self.mode)
        return self

    def __exit__(self, type, value, traceback):
        self.archive.close()
        del self.archive

    def libarchive_write(self, temp_path, target):
        with tmp_chdir(temp_path):
            self.archive.add_files(target)

    def _add_via_tempfile(self, target, bytes_or_sourcefile):
        temp_path = tempfile.mkdtemp()
        target_file = os.path.join(temp_path, target)
        try:
            os.makedirs(os.path.dirname(target_file))
        except OSError:
            pass
        if isinstance(bytes_or_sourcefile, (bytes, bytearray)):
            with open(target_file, 'wb') as temp_file:
                temp_file.write(bytes_or_sourcefile)
        else:
            from shutil import copyfile
            copyfile(bytes_or_sourcefile, target_file)
        self.libarchive_write(temp_path, target)

    def _add(self, source, target):
        if source.endswith(target):
            self.libarchive_write(source.replace(target, ""), target)
        else:
            self._add_via_tempfile(target, source)

    def _add_bytes(self, source, sourcebytes, target):
        self._add_via_tempfile(target, sourcebytes)
