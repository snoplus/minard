Minard - SNO+ Monitoring from the Future
========================================

Quickstart
----------

To run a local copy of minard, first create a virtual environment and activate
it.

    $ virtualenv venv
    $ . venv/bin/activate

Now, clone the minard repository, and install the prerequisites:

    $ git clone https://github.com/snoplus/minard
    $ cd minard
    $ pip install -r requirements.txt

Create a configuration file called settings.conf with the following values:

    DB_HOST='dbug'
    DB_PASS=[password]
    DB_USER='snoplus'
    DB_NAME='detector'
    DB_PORT=5432

    DB_HOST_NEARLINE='dbus'
    DB_NAME_NEARLINE='nearline'
    DB_PORT_NEARLINE=5433

If you are testing the detector state check page you will also need to add:

    DAQ_LOG_DIR=[path to log files]
    BUILDER_LOG_DIR=[path to builder files]

If you are testing the shifter information page you will also need to add:

    DB_OPERATOR = 'operator'
    DB_OPERATOR_PASS =[password]

And if you are testing anything that requires CouchDB access you will need to
add:

    COUCHDB_HOSTNAME=[hostname]
    COUCHDB_PASSWORD=[password]

If you are testing the run-selection pages, you will also need to add:

    DROP_DOWN_MENU_CRITS=['scintillator', 'scintillator_silver', 'scintillator_bronze', 'directionality_analysis']
    RS_EXPERT_PASS=[password]

(DROP_DOWN_MENU_CRITS can be any list of criteria, this is a standard example)

Now, export the environment variable MINARD_SETTINGS to point to the
configuration file:

    $ export MINARD_SETTINGS=`pwd`/settings.conf

Now, you can start up the webserver:

    $ ./runserver.py

And you should be able to open your web browser to localhost:5000 and see it.

Note that you will probably see lots of errors since the flask app isn't able
to connect to the redis server. To install and run the redis server see
http://redis.io/topics/quickstart.
