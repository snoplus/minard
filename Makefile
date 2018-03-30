default: build

INSTALL=install

.DEFAULT:
	./setup.py $@

build:
	./setup.py build

docs:
	$(MAKE) -C docs html
	cp -r docs/_build/html minard/static/docs

/opt/minard/bin/activate:
	virtualenv --system-site-packages /opt/minard

install: /opt/minard/bin/activate
	# clean the build/ directory since it contains scripts with the shebang
	# pointing to /usr/bin/python after running make build
	python setup.py clean --all
	/opt/minard/bin/pip install .
	# reinstall minard with -I flag so that it reinstalls even
	# if the version doesn't change
	/opt/minard/bin/pip install --no-deps -I .
	# need to install gunicorn in virtual environment so that the
	# script /opt/minard/bin/gunicorn exists
	/opt/minard/bin/pip install -I gunicorn
	mkdir -p /var/www/minard
	# copy static files to /var/www/minard so that nginx
	# can serve them instead of flask
	cp -r minard/static /var/www/minard
	$(INSTALL) init/gunicorn /etc/init.d/
	$(INSTALL) init/gunicorn_snoplus_log /etc/init.d/
	$(INSTALL) init/minard_dispatch_push /etc/init.d/
	$(INSTALL) init/minard_dispatch_pull /etc/init.d/
	$(INSTALL) init/data_consumer_cmos /etc/init.d/
	$(INSTALL) init/data_consumer_base /etc/init.d/
	$(INSTALL) init/baseline_monitor /etc/init.d/
	chkconfig gunicorn on
	chkconfig gunicorn_snoplus_log on
	chkconfig minard_dispatch_push on
	chkconfig minard_dispatch_pull on
	chkconfig data_consumer_cmos on
	chkconfig data_consumer_base on
	chkconfig baseline_monitor on
	service gunicorn restart

.PHONY: install build docs
