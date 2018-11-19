from setuptools import setup
import versioneer

requirements = [
    # package requirements go here
]

setup(
    name='figurehead',
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    description="Utilities for defining, reading, and writing config files",
    author="Stuart Berg",
    author_email='bergs@janelia.hhmi.org',
    url='https://github.com/stuarteberg/figurehead',
    packages=['figurehead'],
    entry_points={
        'console_scripts': [
            'figurehead=figurehead.cli:cli'
        ]
    },
    install_requires=requirements,
    keywords='figurehead',
    classifiers=[
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.6',
    ]
)
