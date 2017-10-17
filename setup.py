from setuptools import setup

setup(name='conda-pack',
      version='0.0.1',
      license='BSD',
      packages=['conda_pack'],
      entry_points='''
        [console_scripts]
        conda-pack=conda_pack.cli:main
      ''',
      zip_safe=False)
