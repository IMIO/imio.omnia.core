# -*- coding: utf-8 -*-
"""Installer for the imio.omnia.core package."""

from setuptools import find_packages
from setuptools import setup


long_description = '\n\n'.join([
    open('README.rst').read(),
    open('CONTRIBUTORS.rst').read(),
    open('CHANGES.rst').read(),
])


setup(
    name='imio.omnia.core',
    version='1.0a2.dev0',
    description="An add-on for Plone",
    long_description=long_description,
    # Get more from https://pypi.org/classifiers/
    classifiers=[
        "Environment :: Web Environment",
        "Framework :: Plone",
        "Framework :: Plone :: Addon",
        "Framework :: Plone :: 6.1",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
    ],
    keywords='Python Plone CMS',
    author='Antoine Duchêne',
    author_email='antoineduchene@icloud.com',
    url='https://github.com/collective/imio.omnia.core',
    project_urls={
        'PyPI': 'https://pypi.org/project/imio.omnia.core/',
        'Source': 'https://github.com/collective/imio.omnia.core',
        'Tracker': 'https://github.com/collective/imio.omnia.core/issues',
        # 'Documentation': 'https://imio.omnia.core.readthedocs.io/en/latest/',
    },
    license='GPL version 2',
    packages=find_packages('src', exclude=['ez_setup']),
    namespace_packages=['imio', 'imio.omnia'],
    package_dir={'': 'src'},
    include_package_data=True,
    zip_safe=False,
    python_requires=">=3.12",
    install_requires=[
        'setuptools',
        # -*- Extra requirements: -*-
        'z3c.jbot',
        'plone.api>=1.8.4',
        'plone.app.dexterity',
        'collective.z3cform.datagridfield',
        'httpx>=0.28.1',
    ],
    extras_require={
        'fingerpointing': [
            'collective.fingerpointing',
        ],
        'test': [
            'plone.app.testing',
            # Plone KGS does not use this version, because it would break
            # Remove if your package shall be part of coredev.
            # plone_coredev tests as of 2016-04-01.
            'plone.testing>=5.0.0',
            'plone.app.contenttypes',
            'plone.app.robotframework[debug]',
        ],
    },
    entry_points="""
    [z3c.autoinclude.plugin]
    target = plone
    [console_scripts]
    update_locale = imio.omnia.core.locales.update:update_locale
    """,
)
