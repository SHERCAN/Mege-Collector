#!/usr/bin/python

from setuptools import setup
from setuptools import find_packages


def get_version():
    with open("megedc/__init__.py") as f:
        for line in f:
            if line.startswith("__version__"):
                return eval(line.split("=")[-1])


def get_requires():
    requirements_list = []
    with open("requirements.txt") as f:
        for line in f:
            requirements_list.append(line)
    return requirements_list


with open("README.md", "r") as readme_file:
    readme = readme_file.read()

setup(
    name="megedc",
    version=get_version(),
    description="MeGe Data Collector",
    long_description=readme,
    author="Enerion Group",
    packages=find_packages(),
    install_requires=get_requires(),
    include_package_data=True,
)
