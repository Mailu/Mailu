Using an external reverse proxy
===============================

One of Mailu use cases is as part of a larger services platform, where maybe other Web services are available than Mailu Webmail and admin interface.

In such a configuration, one would usually run a frontend reverse proxy to serve all Web contents based on criteria like the requested hostname (virtual hosts) and/or the requested path. Mailu Admin Web frontend is disabled in the default setup for security reasons, it is however expected that most users will enable it at some point. Also, due to Docker Compose configuration structure, it is impossible for us to make disabling the Web frontend completely available through a configuration variable. This guide was written to help users setup such an architecture.

There are basically three options, from the most to the least recommended one:

- `have Mailu Web frontend listen locally and use your own Web frontend on top of it`_
- `use Traefik in another container as central system-reverse-proxy`_
- `override Mailu Web frontend configuration`_

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

Because the admin interface is served as ``/admin``, the Webmail as ``/webmail``, the single sign on page as ``/sso`` and webdav as ``/webdav``, you may also want to use a single virtual host and serve other applications (still Nginx):

.. code-block:: nginx

  server {
    # [...] here goes your standard configuration

    location /webmail {
      proxy_pass https://localhost:8443/webmail;
    }

    location /admin {
      proxy_pass https://localhost:8443/admin;
      proxy_set_header Host $http_host;
    }

    location /sso {
      proxy_pass https://localhost:8443/sso;
      proxy_set_header Host $http_host;
    }

    location /webdav {
      proxy_pass https://localhost:8443/webdav;
      proxy_set_header Host $http_host;
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
    server_name external.example.com;
    # [...] here goes your standard configuration

    location /webmail {
      proxy_pass https://localhost:8443/webmail;
    }
  }

  server {
    listen <internal_ip>:443;
    server_name internal.example.com;
    # [...] here goes your standard configuration

    location /admin {
      proxy_pass https://localhost:8443/admin;
      proxy_set_header Host $http_host;
    }

  }

Depending on how you access the front server, you might want to add a ``proxy_redirect`` directive to your ``location`` blocks:

.. code-block:: nginx

  proxy_redirect https://localhost https://example.com;

This will stop redirects (301 and 302) sent by the Webmail, nginx front and admin interface from sending you to ``localhost``.

.. _traefik_proxy:

Traefik as reverse proxy
------------------------

`Traefik`_ is a popular reverse-proxy aimed at containerized systems.
As such, many may wish to integrate Mailu into a system which already uses Traefik as its sole ingress/reverse-proxy.

As the ``mailu/front`` container uses Nginx not only for ``HTTP`` forwarding, but also for the mail-protocols like ``SMTP``, ``IMAP``, etc, we need to keep this
container around even when using another ``HTTP`` reverse-proxy. Furthermore, Traefik is neither able to forward non-HTTP, nor can it easily forward HTTPS-to-HTTPS. 
This, however, means 3 things:

- ``mailu/front`` needs to listen internally on ``HTTP`` rather than ``HTTPS``
- ``mailu/front`` is not exposed to the outside world on ``HTTP``
- ``mailu/front`` still needs ``SSL`` certificates (here, we assume ``letsencrypt``) for a well-behaved mail service

This makes the setup with Traefik a bit harder: Traefik saves its certificates in a proprietary *JSON* file, which is not readable by Nginx in the ``front``-container.
To solve this, your ``acme.json`` needs to be exposed to the host or a ``docker-volume``. It will then be read by a script in another container,
which will dump the certificates as ``PEM`` files, readable for Nginx. The ``front`` container will automatically reload Nginx whenever these certificates change.

To set this up, first set ``TLS_FLAVOR=mail`` in your ``.env``. This tells ``mailu/front`` not to try to request certificates using ``letsencrypt``,
but to read provided certificates, and use them only for mail-protocols, not for ``HTTP``.
Next, in your ``docker-compose.yml``, comment out the ``port`` lines of the ``front`` section for port ``…:80`` and ``…:443``.
Add the respective Traefik labels for your domain/configuration, like

.. code-block:: yaml

    labels:
      - "traefik.enable=true"
      - "traefik.port=80"
      - "traefik.frontend.rule=Host:$TRAEFIK_DOMAIN"

.. note:: Please don’t forget to add ``TRAEFIK_DOMAIN=[...]`` TO YOUR ``.env``

If your Traefik is configured to automatically request certificates from *letsencrypt*, then you’ll have a certificate for ``mail.your.example.com`` now. However,
``mail.your.example.com`` might only be the location where you want the Mailu web-interfaces to live — your mail should be sent/received from ``your.example.com``,
and this is the ``DOMAIN`` in your ``.env``?
To support that use-case, Traefik can request ``SANs`` for your domain. The configuration for this will depend on your Traefik version.

----

Traefik 2.x using labels configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add the appropriate labels for your domain(s) to the ``front`` container in ``docker-compose.yml``.

.. code-block:: yaml

  services:
    front:
      labels:
        # Enable TLS
        - "traefik.http.routers.mailu-secure.tls"
        # Your main domain
        - "traefik.http.routers.mailu-secure.tls.domains[0].main=your.example.com"
        # Optional SANs for your main domain
        - "traefik.http.routers.mailu-secure.tls.domains[0].sans=mail.your.example.com,webmail.your.example.com,smtp.your.example.com"
        # Optionally add other domains
        - "traefik.http.routers.mailu-secure.tls.domains[1].main=mail.other.example.com"
        - "traefik.http.routers.mailu-secure.tls.domains[1].sans=mail2.other.example.com,mail3.other.example.com"
        # Your ACME certificate resolver
        - "traefik.http.routers.mailu-secure.tls.certResolver=foo"

Of course, be sure to define the Certificate Resolver ``foo`` in the static configuration as well.

Alternatively, you can define SANs in the Traefik static configuration using routers, or in the static configuration using entrypoints. Refer to the Traefik documentation for more details.

Traefik 1.x with TOML configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Lets add something like

.. code-block:: yaml

  [acme]
    [[acme.domains]]
      main = "your.example.com" # this is the same as $TRAEFIK_DOMAIN!
      sans = ["mail.your.example.com", "webmail.your.example.com", "smtp.your.example.com"]

to your ``traefik.toml``.

----

You might need to clear your ``acme.json``, if a certificate for one of these domains already exists.

You will need some solution which dumps the certificates in ``acme.json``, so you can include them in the ``mailu/front`` container.
One such example is ``mailu/traefik-certdumper``, which has been adapted for use in Mailu. You can add it to your ``docker-compose.yml`` like:

.. code-block:: yaml

  certdumper:
    restart: always
    image: mailu/traefik-certdumper:$VERSION
    environment:
    # Make sure this is the same as the main=-domain in traefik.toml
    # !!! Also don’t forget to add "TRAEFIK_DOMAIN=[...]" to your .env!
      - DOMAIN=$TRAEFIK_DOMAIN
    volumes:
      # Folder, which contains the acme.json
      - "/data/traefik:/traefik"
      # Folder, where cert.pem and key.pem will be written
      - "/data/mailu/certs:/output"


Assuming you have ``volume-mounted`` your ``acme.json`` put to ``/data/traefik`` on your host. The dumper will then write out ``/data/mailu/certs/cert.pem`` and ``/data/mailu/certs/key.pem`` whenever ``acme.json`` is updated.
Yay! Now let’s mount this to our ``front`` container like:

.. code-block:: yaml

    volumes:
      - /data/mailu/certs:/certs

This works, because we set ``TLS_FLAVOR=mail``, which picks up the key-certificate pair (e.g., ``cert.pem`` and ``key.pem``) from the certs folder in the root path (``/certs/``).

.. _`Traefik`: https://traefik.io/

Override Mailu configuration
----------------------------

If you do not have the resources for running a separate reverse proxy, you could override Mailu reverse proxy configuration by using a Docker volume.
Simply store your configuration file (Nginx format), in ``/mailu/nginx.conf`` for instance.

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

You can also download the example configuration files:

- :download:`compose/traefik/docker-compose.yml`
- :download:`compose/traefik/traefik.toml`

.. _have Mailu Web frontend listen locally and use your own Web frontend on top of it: #have-mailu-web-frontend-listen-locally
.. _use Traefik in another container as central system-reverse-proxy: #traefik-as-reverse-proxy
.. _override Mailu Web frontend configuration: #override-mailu-configuration

