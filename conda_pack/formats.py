import os
import stat
import zipfile
import tarfile

_tar_mode = {'tar.gz': 'w:gz',
             'tgz': 'w:gz',
             'tar.bz2': 'w:bz2',
             'tbz2': 'w:bz2',
             'tar': 'w'}


def archive(path, format, zip_symlinks=False):
    if format == 'zip':
        return ZipArchive(path, zip_symlinks=zip_symlinks)
    else:
        return TarArchive(path, _tar_mode[format])


class TarArchive(object):
    def __init__(self, path, mode):
        self.path = path
        self.mode = mode

    def __enter__(self):
        self.archive = tarfile.open(name=self.path, mode=self.mode,
                                    dereference=False)
        return self

    def __exit__(self, *args):
        self.archive.close()

    def add(self, source, target):
        self.archive.add(source, target, recursive=False)


class ZipArchive(object):
    def __init__(self, path, zip_symlinks=False):
        self.path = path
        self.zip_symlinks = zip_symlinks

    def __enter__(self):
        self.archive = zipfile.ZipFile(self.path, "w", allowZip64=True,
                                       compression=zipfile.ZIP_DEFLATED)
        return self

    def __exit__(self, *args):
        self.archive.close()

    def add(self, source, target):
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
