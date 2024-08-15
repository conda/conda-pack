from setuptools import setup

import versioneer

setup(
    name="conda-pack",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    url="https://conda.github.io/conda-pack/",
    project_urls={"Source Code": "https://github.com/conda/conda-pack"},
    maintainer="Jim Crist",
    maintainer_email="jiminy.crist@gmail.com",
    keywords="conda packaging",
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: System :: Archiving :: Packaging",
        "Topic :: System :: Software Distribution",
        "Topic :: Software Development :: Build Tools",
    ],
    license="BSD",
    description="Package conda environments for redistribution",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    packages=["conda_pack"],
    package_data={"conda_pack": ["scripts/windows/*", "scripts/posix/*"]},
    entry_points="""
        [console_scripts]
        conda-pack=conda_pack.cli:main
      """,
    install_requires=["setuptools"],
    python_requires=">=3.8",
    zip_safe=False,
)
