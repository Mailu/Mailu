Development environment
=======================

Docker containers
-----------------

The development environment is quite similar to the production one. You should always use
the ``master`` version when developing.

Building images
```````````````

We supply a separate ``test/build.yml`` file for
convenience. To build all Mailu containers:

.. code-block:: bash

  docker-compose -f tests/build.yml build

The ``build.yml`` file has two variables:

#. ``$DOCKER_ORG``: First part of the image tag. Defaults to *mailu* and needs to be changed
   only  when pushing to your own Docker hub account.
#. ``$VERSION``: Last part of the image tag. Defaults to *local* to differentiate from pulled
   images.

To re-build only specific containers at a later time.

.. code-block:: bash

  docker-compose -f tests/build.yml build admin webdav

If you have to push the images to Docker Hub for testing in Docker Swarm or a remote
host, you have to define ``DOCKER_ORG`` (usually your Docker user-name) and login to
the hub.

.. code-block:: bash

  docker login
  Username: Foo
  Password: Bar
  export DOCKER_ORG="Foo"
  export VERSION="feat-extra-app"
  docker-compose -f tests/build.yml build
  docker-compose -f tests/build.yml push

Running containers
``````````````````

To run the newly created images: ``cd`` to your project directory. Edit ``.env`` to set
``VERSION`` to the same value as used during the build, which defaults to ``local``.
After that you can run:

.. code-block:: bash

  docker-compose up -d

If you wish to run commands inside a container, simply run (example):

.. code-block:: bash

  docker-compose exec admin ls -lah /

Or if you wish to start a shell for debugging:

.. code-block:: bash

  docker-compose exec admin sh

Finally, if you need to install packages inside the containers for debugging:

.. code-block:: bash

  docker-compose exec admin apk add --no-cache package-name

Web administration
------------------

The administration Web interface requires a proper dev environment that can easily be setup using ``virtualenv`` (make sure you are using Python 3) :

.. code-block:: bash

  cd core/admin
  virtualenv .
  source bin/activate
  pip install -r requirements.txt

You can then export the path to the development database (use four slashes for absolute path):

.. code-block:: bash

  export SQLALCHEMY_DATABASE_URI=sqlite:///path/to/dev.db

And finally run the server with debug enabled:

.. code-block:: bash

  python run.py

Any change to the files will automatically restart the Web server and reload the files.

When using the development environment, a debugging toolbar is displayed on the right side
of the screen, that you can open to access query details, internal variables, etc.

Documentation
-------------

Documentation is maintained in the ``docs`` directory and are maintained as `reStructuredText`_ files. It is possible to run a local documentation server for reviewing purposes, using Docker:

.. code-block:: bash

  cd <Mailu repo>
  docker build -t docs docs
  docker run -p 127.0.0.1:8080:80 docs

You can now read the local documentation by navigating to http://localhost:8080.

.. note:: After modifying the documentation, the image needs to be rebuild and the container restarted for the changes to become visible.

.. _`reStructuredText`: http://docutils.sourceforge.net/rst.html
