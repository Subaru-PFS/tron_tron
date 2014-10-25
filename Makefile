all:
	echo nothing to do for all

clean:
	find . \( -name '*.pyc' -o -name '*.pyo' -o -name '*~' -o -name *.core -o -name TAGS \) -print | xargs rm

check:
	pychecker hub.py

tags:
	etags `find . -name '*.py' -print`

install:
	echo Installing tron to $(PREFIX)
	sleep 1
	mkdir -p $(PREFIX)
	cp -pr . $(PREFIX)

