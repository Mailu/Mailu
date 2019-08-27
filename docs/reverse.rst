Using an external reverse proxy
===============================

One of Mailu's use cases is as part of a larger services platform, where maybe
other Web services are available on other FQDNs served from the same IP address.

In such a configuration, one would usually run a front-end reverse proxy to serve all
Web contents based on criteria like the requested hostname (virtual hosts).

.. _traefik_proxy:

Traefik as reverse proxy
------------------------

In your docker-compose.yml, remove the `ports` section of the `front` container
and add a section like follows:

.. code-block:: yaml

<<<<<<< HEAD
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
=======
    labels:
      - "traefik.enable=true"
      - "traefik.port=80"
      - "traefik.frontend.rule=Host:$TRAEFIK_DOMAIN"

.. note:: Please don’t forget to add ``TRAEFIK_DOMAIN=[...]`` TO YOUR ``.env``

If your Traefik is configured to automatically request certificates from *letsencrypt*, then you’ll have a certificate for ``mail.your.doma.in`` now. However,
``mail.your.doma.in`` might only be the location where you want the Mailu web-interfaces to live — your mail should be sent/received from ``your.doma.in``,
and this is the ``DOMAIN`` in your ``.env``?
To support that use-case, Traefik can request ``SANs`` for your domain. Lets add something like

.. code-block:: yaml

  [acme]
    [[acme.domains]]
      main = "your.doma.in" # this is the same as $TRAEFIK_DOMAIN!
      sans = ["mail.your.doma.in", "webmail.your.doma.in", "smtp.your.doma.in"]

to your ``traefik.toml``. You might need to clear your ``acme.json``, if a certificate for one of these domains already exists.

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
>>>>>>> a09d166d (Docs: fix some build warnings)
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
