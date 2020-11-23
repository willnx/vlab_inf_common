# -*- coding: UTF-8 -*-
from setuptools import setup, find_packages


setup(name="vlab-inf-common",
      author="Nicholas Willhite, Kevin Broadware",
      author_email='willnx84@gmail.com',
      version='2020.11.23',
      packages=find_packages(),
      include_package_data=True,
      classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3.6',
      ],
      description="vLab common logic for working with virtual infrastructure",
      long_description=open('README.rst').read(),
      install_requires=['pyVmomi', 'vlab-api-common', 'pyOpenSSL'],
      )
