Using an external reverse proxy
===============================

One of Mailu use cases is as part of a larger services platform, where maybe other Web services are available than Mailu Webmail and admin interface.

In such a configuration, one would usually run a frontend reverse proxy to serve all Web contents based on criteria like the requested hostname (virtual hosts) and/or the requested path. Mailu Web frontend is disabled in the default setup for security reasons, it is however expected that most users will enable it at some point. Also, due to Docker Compose configuration structure, it is impossible for us to make disabling the Web frontend completely available through a configuration variable. This guide was written to help users setup such an architecture.

There are basically three options, from the most to the least recommended one:
- have Mailu Web frontend listen locally and use your own Web frontend on top of it
- override Mailu Web frontend configuration
- disable Mailu Web frontend completely and use your own

All options will require that you modify the ``docker-compose.yml`` file.

Have Mailu Web frontend listen locally
--------------------------------------

The simplest and safest option is to modify the port forwards for Mailu Web frontend and have your own frontend point there. For instance, in the ``front`` section of Mailu ``docker-compose.yml``, use local ports 8080 and 8443 respectively for HTTP and HTTPS:

.. code-block:: yaml

  front:
    # build: nginx
    image: mailu/nginx:$VERSION
    restart: always
    env_file: .env
    ports:
      - "127.0.0.1:8080:80"
      - "127.0.0.1:8443:443"
      ...
    volumes:
      - "$ROOT/certs:/certs"

Then on your own frontend, point to these local ports. In practice, you only need to point to the HTTPS port (as the HTTP port simply redirects there). Here is an example Nginx configuration:

.. code-block:: nginx

  server {
    listen 443;
    server_name mymailhost.tld;

    # [...] here goes your standard configuration

    location / {
      proxy_pass https://localhost:8443;
    }
  }

Because the admin interface is served as ``/admin`` and the Webmail as ``/webmail`` you may also want to use a single virtual host and serve other applications (still Nginx):

.. code-block:: nginx

  server {
    # [...] here goes your standard configuration

    location /webmail {
      proxy_pass https://localhost:8443/webmail;
    }

    location /admin {
      proxy_pass https://localhost:8443/admin;
    }

    location /main_app {
      proxy_pass https://some-host;
    }

    location /other_app {
      proxy_pass https://some-other-host;
    }

    location /local_app {
      root /path/to/your/files;
    }

    location / {
      return 301 $scheme://$host/main_app;
    }
  }

Finally, you might want to serve the admin interface on a separate virtual host but not expose the admin container directly (have your own HTTPS virtual hosts on top of Mailu, one public for the Webmail and one internal for administration for instance).

Here is an example configuration :

.. code-block:: nginx

  server {
    listen <public_ip>:443;
    server_name yourpublicname.tld;
    # [...] here goes your standard configuration

    location /webmail {
      proxy_pass https://localhost:8443/webmail;
    }
  }

  server {
    listen <internal_ip>:443;
    server_name yourinternalname.tld;
    # [...] here goes your standard configuration

    location /admin {
      proxy_pass https://localhost:8443/admin;
    }

  }

Depending on how you access the front server, you might want to add a ``proxy_redirect`` directive to your ``location`` blocks:

.. code-block:: nginx

  proxy_redirect https://localhost https://your-domain.com;

This will stop redirects (301 and 302) sent by the Webmail, nginx front and admin interface from sending you to ``localhost``.


Override Mailu configuration
----------------------------

If you do not have the resources for running a separate reverse proxy, you could override Mailu reverse proxy configuration by using a Docker volume. Simply store your configuration file (Nginx format), in ``/mailu/nginx.conf`` for instance.

Then modify your ``docker-compose.yml`` file and change the ``front`` section to add a mount:

.. code-block:: nginx

  front:
    build: nginx
    image: mailu/nginx:$VERSION
    restart: always
    env_file: .env
    ports:
      [...]
    volumes:
      - "$ROOT/certs:/certs"
      - "$ROOT/nginx.conf:/etc/nginx/nginx.conf"

You can use our default configuration file as a sane base for your configuration.

Disable completely Mailu reverse proxy
--------------------------------------

You can simply disable Mailu reverse proxy by removing the ``front`` section from the ``docker-compose.yml`` and use your own means to reverse proxy requests to the proper containers.

Be careful with this method as resolving container addresses outside the Docker Compose structure is a tricky task: there is no guarantee that addresses will remain after a restart and you are almost certain that addresses will change after every upgrade (and whenever containers are recreated).
