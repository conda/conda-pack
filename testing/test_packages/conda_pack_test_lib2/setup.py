from setuptools import setup

setup(name='conda_pack_test_lib2',
      version='0.0.1',
      description='Dummy package for testing conda-pack',
      packages=['conda_pack_test_lib2'],
      entry_points='''
        [console_scripts]
        conda-pack-test-lib2=conda_pack_test_lib2.cli:main
      ''',
      zip_safe=False)
