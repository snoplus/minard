#!/usr/bin/env python
from setuptools import setup
from glob import glob

setup(name='minard',
      version='1.0',
      description='Web App Monitoring Tools',
      author='Anthony LaTorre',
      author_email='tlatorre@uchicago.edu',
      url='snopl.us',
      packages=['minard','snoplus_log'],
      include_package_data=True,
      zip_safe=False,
      scripts=glob('bin/*'),
      install_requires=['flask==0.10',
                        'gunicorn==19.9.0',
                        'numpy==1.4.1',
                        'redis==2.10.5',
                        'argparse==1.2.1',
                        'sphinx==1.8.6',
                        'requests==2.6.0',
                        'python-dateutil==2.5.3',
                        'sqlalchemy==1.0.12',
                        'psycopg2-binary==2.8.6',
                        'alabaster==0.7.7',
                        'couchdb==1.0.1',
                        'wtforms==2.1',
                        'email_validator==1.1.1',
                        'werkzeug==0.16.1']
      )
