Using an external reverse proxy
===============================

One of Mailu's use cases is as part of a larger services platform, where maybe
other Web services are available on other FQDNs served from the same IP address.

<<<<<<< HEAD
In such a configuration, one would usually run a front-end reverse proxy to serve all
Web contents based on criteria like the requested hostname (virtual hosts).
=======
In such a configuration, one would usually run a frontend reverse proxy to serve all Web contents based on criteria like the requested hostname (virtual hosts) and/or the requested path. Mailu Admin Web frontend is disabled in the default setup for security reasons, it is however expected that most users will enable it at some point. Also, due to Docker Compose configuration structure, it is impossible for us to make disabling the Web frontend completely available through a configuration variable. This guide was written to help users setup such an architecture.

There are basically three options, from the most to the least recommended one:

- `have Mailu Web frontend listen locally and use your own Web frontend on top of it`_
- `use Traefik in another container as central system-reverse-proxy`_
- `override Mailu Web frontend configuration`_

All options will require that you modify the ``docker-compose.yml`` and ``mailu.env`` file.

Mailu must also be configured with the information what header is used by the reverse proxy for passing the remote client IP. 
This is configured in the mailu.env file. See the :ref:`configuration reference <reverse_proxy_headers>` for more information.

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
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_pass https://localhost:8443;
    }
  }

.. code-block:: docker

  #mailu.env file
  REAL_IP_HEADER=X-Real-IP
  REAL_IP_FROM=x.x.x.x,y.y.y.y.y
  #x.x.x.x,y.y.y.y.y is the static IP address your reverse proxy uses for connecting to Mailu. 
  
Because the admin interface is served as ``/admin``, the Webmail as ``/webmail``, the single sign on page as ``/sso``, webdav as ``/webdav``, the client-autoconfiguration and the static files endpoint as ``/static``, you may also want to use a single virtual host and serve other applications (still Nginx):

.. code-block:: nginx

  server {
    # [...] here goes your standard configuration

    location ~* ^/(admin|sso|static|webdav|webmail|(apple\.)?mobileconfig|(\.well\-known/autoconfig/)?mail/|Autodiscover/Autodiscover) {
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_pass https://localhost:8443;     
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

.. note:: Please don’t add a ``/`` at the end of the location pattern or all your redirects will fail with 404 because the ``/`` would be missing, and you would have to add it manually to move on

.. code-block:: docker
  
  #mailu.env file
  REAL_IP_HEADER=X-Real-IP
  REAL_IP_FROM=x.x.x.x,y.y.y.y.y
  #x.x.x.x,y.y.y.y.y is the static IP address your reverse proxy uses for connecting to Mailu. 

Finally, you might want to serve the admin interface on a separate virtual host but not expose the admin container directly (have your own HTTPS virtual hosts on top of Mailu, one public for the Webmail and one internal for administration for instance).

Here is an example configuration :

.. code-block:: nginx

  server {
    listen <public_ip>:443;
    server_name external.example.com;
    # [...] here goes your standard configuration

    location /webmail {
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_pass https://localhost:8443/webmail;
    }
  }

  server {
    listen <internal_ip>:443;
    server_name internal.example.com;
    # [...] here goes your standard configuration

    location /admin {
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_pass https://localhost:8443/admin;
      proxy_set_header Host $http_host;
    }

  }

.. code-block:: docker

  #mailu.env file
  REAL_IP_HEADER=X-Real-IP
  REAL_IP_FROM=x.x.x.x,y.y.y.y.y
  #x.x.x.x,y.y.y.y.y is the static IP address your reverse proxy uses for connecting to Mailu. 

Depending on how you access the front server, you might want to add a ``proxy_redirect`` directive to your ``location`` blocks:

.. code-block:: nginx

  proxy_redirect https://localhost https://example.com;

This will stop redirects (301 and 302) sent by the Webmail, nginx front and admin interface from sending you to ``localhost``.
>>>>>>> 00b78b73 (Adding missing semicolon after remote_addr)

.. _traefik_proxy:

Traefik as reverse proxy
------------------------

In your docker-compose.yml, remove the `ports` section of the `front` container
and add a section like follows:

.. code-block:: yaml

  reverse-proxy:
    # The official v2 Traefik docker image
    image: traefik:v2.11
    # Enables the web UI and tells Traefik to listen to docker
    command:
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--providers.docker.allowEmptyServices=true"
      - "--entrypoints.web.address=:http"
      - "--entrypoints.websecure.address=:https"
      - "--entrypoints.smtp.address=:smtp"
      - "--entrypoints.submissions.address=:submissions"
      - "--entrypoints.imaps.address=:imaps"
      - "--entrypoints.pop3s.address=:pop3s"
      - "--entrypoints.sieve.address=:sieve"
      # - "--api.insecure=true"
      # - "--log.level=DEBUG"
    ports:
      - "25:25"
      - "80:80"
      - "443:443"
      - "465:465"
      - "993:993"
      - "995:995"
      - "4190:4190"
      # The Web UI (enabled by --api.insecure=true)
      # - "8080:8080"
    volumes:
      # So that Traefik can listen to the Docker events
      - /var/run/docker.sock:/var/run/docker.sock

and then add the following to the front section:

.. code-block:: yaml

  labels:
      - "traefik.enable=true"

      # the second part is important to ensure Mailu can get certificates from letsencrypt for all hostnames
      - "traefik.http.routers.web.rule=Host(`mail.example.com`) || PathPrefix(`/.well-known/acme-challenge/`)"
      - "traefik.http.routers.web.entrypoints=web"
      - "traefik.http.services.web.loadbalancer.server.port=80"

      # other FQDNS can be added here:
      - "traefik.tcp.routers.websecure.rule=HostSNI(`mail.example.com`) || HostSNI(`autoconfig.example.com`) || HostSNI(`mta-sts.example.com`)"
      - "traefik.tcp.routers.websecure.entrypoints=websecure"
      - "traefik.tcp.routers.websecure.tls.passthrough=true"
      - "traefik.tcp.routers.websecure.service=websecure"
      - "traefik.tcp.services.websecure.loadbalancer.server.port=443"
      - "traefik.tcp.services.websecure.loadbalancer.proxyProtocol.version=2"

      - "traefik.tcp.routers.smtp.rule=HostSNI(`*`)"
      - "traefik.tcp.routers.smtp.entrypoints=smtp"
      - "traefik.tcp.routers.smtp.service=smtp"
      - "traefik.tcp.services.smtp.loadbalancer.server.port=25"
      - "traefik.tcp.services.smtp.loadbalancer.proxyProtocol.version=2"

      - "traefik.tcp.routers.submissions.rule=HostSNI(`*`)"
      - "traefik.tcp.routers.submissions.entrypoints=submissions"
      - "traefik.tcp.routers.submissions.service=submissions"
      - "traefik.tcp.services.submissions.loadbalancer.server.port=465"
      - "traefik.tcp.services.submissions.loadbalancer.proxyProtocol.version=2"

      - "traefik.tcp.routers.imaps.rule=HostSNI(`*`)"
      - "traefik.tcp.routers.imaps.entrypoints=imaps"
      - "traefik.tcp.routers.imaps.service=imaps"
      - "traefik.tcp.services.imaps.loadbalancer.server.port=993"
      - "traefik.tcp.services.imaps.loadbalancer.proxyProtocol.version=2"

      - "traefik.tcp.routers.pop3s.rule=HostSNI(`*`)"
      - "traefik.tcp.routers.pop3s.entrypoints=pop3s"
      - "traefik.tcp.routers.pop3s.service=pop3s"
      - "traefik.tcp.services.pop3s.loadbalancer.server.port=995"
      - "traefik.tcp.services.pop3s.loadbalancer.proxyProtocol.version=2"

      - "traefik.tcp.routers.sieve.rule=HostSNI(`*`)"
      - "traefik.tcp.routers.sieve.entrypoints=sieve"
      - "traefik.tcp.routers.sieve.service=sieve"
      - "traefik.tcp.services.sieve.loadbalancer.server.port=4190"
      - "traefik.tcp.services.sieve.loadbalancer.proxyProtocol.version=2"
    healthcheck:
      test: ['NONE']

in mailu.env:

.. code-block:: docker

  REAL_IP_FROM=192.168.203.0/24
  PROXY_PROTOCOL=25,443,465,993,995,4190
  TRAEFIK_VERSION=v2
  TLS_FLAVOR=letsencrypt
  WEBROOT_REDIRECT=/sso/login

Using the above configuration, Traefik will proxy all the traffic related to Mailu's FQDNs without requiring duplicate certificates.
