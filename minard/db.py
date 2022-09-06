import sqlalchemy
from .views import app

engine = sqlalchemy.create_engine('postgresql://%s:%s@%s:%i/%s' %
                                 (app.config['DB_USER'], app.config['DB_PASS'],
                                  app.config['DB_HOST'], app.config['DB_PORT'],
                                  app.config['DB_NAME']),
                                  pool_recycle=3600)

engine_nl = sqlalchemy.create_engine('postgresql://%s:%s@%s:%i/%s' %
                                    (app.config['DB_USER'], app.config['DB_PASS'],
                                     app.config['DB_HOST_NEARLINE'], 
                                     app.config['DB_PORT_NEARLINE'],
                                     app.config['DB_NAME_NEARLINE']),
                                     pool_recycle=3600)

engine_test = sqlalchemy.create_engine('postgresql://%s:%s@%s:%i/%s' %
                                    (app.config['DB_USER'], app.config['DB_PASS'],
                                     app.config['DB_HOST_TEST'], 
                                     app.config['DB_PORT_TEST'],
                                     app.config['DB_NAME_TEST']),
                                     pool_recycle=3600)