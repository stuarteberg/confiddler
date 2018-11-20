from setuptools import setup
import versioneer

requirements = [
    'ruamel.yaml>=0.15.71',
    'jsonschema>=3.0.0a3',
]

setup(
    name='confiddler',
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    description="Utilities for defining, reading, and writing config files",
    author="Stuart Berg",
    author_email='bergs@janelia.hhmi.org',
    url='https://github.com/stuarteberg/confiddler',
    packages=['confiddler'],
    entry_points={
        'console_scripts': [
            'confiddler=confiddler.cli:cli'
        ]
    },
    install_requires=requirements,
    keywords='confiddler',
    classifiers=[
        'Programming Language :: Python :: 3.6',
    ]
)
