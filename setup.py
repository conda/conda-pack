from setuptools import setup

setup(name='conda-pack',
      version='0.0.1',
      url='https://github.com/jcrist/conda-pack',
      maintainer='Jim Crist',
      maintainer_email='jiminy.crist@gmail.com',
      license='BSD',
      description='Package conda environments for redistribution',
      install_requires=['click'],
      packages=['conda_pack'],
      entry_points='''
        [console_scripts]
        conda-pack=conda_pack.cli:main
      ''',
      zip_safe=False)
