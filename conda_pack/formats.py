import os
import stat
import zipfile
import tarfile
from io import BytesIO

_tar_mode = {'tar.gz': 'w:gz',
             'tgz': 'w:gz',
             'tar.bz2': 'w:bz2',
             'tbz2': 'w:bz2',
             'tar': 'w'}


def archive(fileobj, arcroot, format, zip_symlinks=False):
    if format == 'zip':
        return ZipArchive(fileobj, arcroot, zip_symlinks=zip_symlinks)
    else:
        return TarArchive(fileobj, arcroot, _tar_mode[format])


class ArchiveBase(object):
    def __exit__(self, *args):
        self.archive.close()

    def add(self, source, target):
        target = os.path.join(self.arcroot, target)
        self._add(source, target)
        self.records.append((source, target))

    def add_bytes(self, source, sourcebytes, target):
        target = os.path.join(self.arcroot, target)
        self._add_bytes(source, sourcebytes, target)
        self.records.append((source, target))


class TarArchive(ArchiveBase):
    def __init__(self, fileobj, arcroot, mode):
        self.fileobj = fileobj
        self.arcroot = arcroot
        self.mode = mode

    def __enter__(self):
        self.archive = tarfile.open(fileobj=self.fileobj, mode=self.mode,
                                    dereference=False)
        self.records = []
        return self

    def _add(self, source, target):
        self.archive.add(source, target, recursive=False)

    def _add_bytes(self, source, sourcebytes, target):
        info = self.archive.gettarinfo(source, target)
        info.size = len(sourcebytes)
        self.archive.addfile(info, BytesIO(sourcebytes))


class ZipArchive(ArchiveBase):
    def __init__(self, fileobj, arcroot, zip_symlinks=False):
        self.fileobj = fileobj
        self.arcroot = arcroot
        self.zip_symlinks = zip_symlinks

    def __enter__(self):
        self.archive = zipfile.ZipFile(self.fileobj, "w", allowZip64=True,
                                       compression=zipfile.ZIP_DEFLATED)
        self.records = []
        return self

    def _add(self, source, target):
        try:
            st = os.lstat(source)
            is_link = stat.S_ISLNK(st.st_mode)
            is_dir = stat.S_ISDIR(st.st_mode)
        except (OSError, AttributeError):
            is_link = False

        if is_link:
            if self.zip_symlinks:
                info = zipfile.ZipInfo(target)
                info.create_system = 3
                info.external_attr = (st.st_mode & 0xFFFF) << 16
                if is_dir:
                    info.external_attr |= 0x10  # MS-DOS directory flag
                self.archive.writestr(info, os.readlink(source))
            else:
                if is_dir:
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
        info = zipfile.ZipInfo.from_file(source, target)
        self.archive.writestr(info, sourcebytes)
