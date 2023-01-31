#!/usr/bin/env python

"""The setup script."""

from setuptools import find_packages, setup

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = ['ciso8601', 'PyYAML']

test_requirements = [
    'pytest>=3',
]

setup(
    author="Gonéri Le Bouder",
    author_email='goneri@lebouder.net',
    python_requires='>=3.6',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    description=(
        "Library to clean up Ansible tasks from any Personally Identifiable Information (PII)"
    ),
    install_requires=requirements,
    license="Apache Software License 2.0",
    long_description=readme + '\n\n' + history,
    include_package_data=True,
    keywords='anonymizor',
    name='anonymizor',
    packages=find_packages(include=['anonymizor', 'anonymizor.*']),
    test_suite='tests',
    tests_require=test_requirements,
    url='https://github.com/goneri/anonymizor',
    version='0.1.0',
    zip_safe=False,
)
