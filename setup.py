"""Setup for entrypoint project."""

from setuptools import setup
from entrypoint import __version__ as version

requirements = map(lambda line: line.strip(),
                   open('requirements.txt', 'r').readlines())

setup(
    name='entrypoint',
    description='Entrypoint for containers providing extensible initalization routines, template-based configurability and simple init system for signal propagation and process handling',
    version=version,
    author='Teemu Kuusisto',
    license='MIT',
    url='https://github.com/hlub/entrypoint',
    platforms='linux',
    packages=[
    	'entrypoint'
    ],
    entry_points={
    	'console_scripts': [
    		'entrypoint = entrypoint.main:main'
    	]
    },
    install_requires=list(requirements)
)
