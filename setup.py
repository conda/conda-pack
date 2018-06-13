from setuptools import setup
import versioneer

setup(name='conda-pack',
      version=versioneer.get_version(),
      cmdclass=versioneer.get_cmdclass(),
      url='https://github.com/conda/conda-pack',
      maintainer='Jim Crist',
      maintainer_email='jiminy.crist@gmail.com',
      license='BSD',
      description='Package conda environments for redistribution',
      packages=['conda_pack'],
      package_data={'conda_pack': ['scripts/posix/*']},
      entry_points='''
        [console_scripts]
        conda-pack=conda_pack.cli:main
      ''',
      zip_safe=False)
