# -*- coding: UTF-8 -*-
from setuptools import setup, find_packages


setup(name="vlab-inf-common",
      author="Nicholas Willhite, Kevin Broadware",
      author_email='willnx84@gmail.com',
      version='2018.05.30',
      packages=find_packages(),
      include_package_data=True,
      long_description=open('README.rst').read(),
      description="vLab common logic for working with virtual infrastructure",
      install_requires=['pyVmomi'],
      )
