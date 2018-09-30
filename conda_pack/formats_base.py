import os


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
