Development environment
=======================

Docker containers
-----------------

The development environment is quite similar to the production one. You should always use
the ``master`` version when developing. Simply add a build directive to the images
you are working on in the ``docker-compose.yml``:

.. code-block:: yaml

  webdav:
    build: ./optional/radicale
    image: mailu/$WEBDAV:$VERSION
    restart: always
    env_file: .env
    volumes:
      - "$ROOT/dav:/data"

  admin:
    build: ./core/admin
    image: mailu/admin:$VERSION
    restart: always
    env_file: .env
    volumes:
      - "$ROOT/data:/data"
      - "$ROOT/dkim:/dkim"
      - /var/run/docker.sock:/var/run/docker.sock:ro
    depends_on:
      - redis


The build these containers.

.. code-block:: bash

  docker-compose build admin webdav

Then you can simply start the stack as normal, newly-built images will be used.

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
