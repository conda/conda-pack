import glob
import json
import os
import shutil

current_dir = os.path.dirname(os.path.abspath(__file__))

if __name__ == '__main__':
    print("Removing conda_pack_test_lib2 from package cache for py27 env")

    metas = glob.glob(os.path.join(current_dir, 'environments', 'py27',
                                   'conda-meta', 'conda_pack_test_lib2*.json'))

    if len(metas) != 1:
        raise ValueError("%d metadata files found for conda_pack_test_lib2, "
                         "expected only 1" % len(metas))

    with open(os.path.join(metas[0])) as fil:
        info = json.load(fil)
    pkg = info['link']['source']

    if os.path.exists(pkg):
        print("rm -r %r" % pkg)
        shutil.rmtree(pkg)
        print("Package removed")
    else:
        print("Package already removed")
