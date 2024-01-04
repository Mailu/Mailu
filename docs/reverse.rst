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
      - "--entrypoints.submission.address=:submission"
      - "--entrypoints.submissions.address=:submissions"
      - "--entrypoints.imap.address=:imap"
      - "--entrypoints.imaps.address=:imaps"
      - "--entrypoints.pop3.address=:pop3"
      - "--entrypoints.pop3s.address=:pop3s"
      - "--entrypoints.sieve.address=:sieve"
      # - "--api.insecure=true"
      # - "--log.level=DEBUG"
    ports:
      - "25:25"
      - "80:80"
      - "443:443"
      - "465:465"
      - "587:587"
      - "993:993"
      - "995:995"
      - "110:110"
      - "143:143"
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

      - "traefik.tcp.routers.submission.rule=HostSNI(`*`)"
      - "traefik.tcp.routers.submission.entrypoints=submission"
      - "traefik.tcp.routers.submission.service=submission"
      - "traefik.tcp.services.submission.loadbalancer.server.port=587"
      - "traefik.tcp.services.submission.loadbalancer.proxyProtocol.version=2"

      - "traefik.tcp.routers.submissions.rule=HostSNI(`*`)"
      - "traefik.tcp.routers.submissions.entrypoints=submissions"
      - "traefik.tcp.routers.submissions.service=submissions"
      - "traefik.tcp.services.submissions.loadbalancer.server.port=465"
      - "traefik.tcp.services.submissions.loadbalancer.proxyProtocol.version=2"

      - "traefik.tcp.routers.imap.rule=HostSNI(`*`)"
      - "traefik.tcp.routers.imap.entrypoints=imap"
      - "traefik.tcp.routers.imap.service=imap"
      - "traefik.tcp.services.imap.loadbalancer.server.port=143"
      - "traefik.tcp.services.imap.loadbalancer.proxyProtocol.version=2"

      - "traefik.tcp.routers.imaps.rule=HostSNI(`*`)"
      - "traefik.tcp.routers.imaps.entrypoints=imaps"
      - "traefik.tcp.routers.imaps.service=imaps"
      - "traefik.tcp.services.imaps.loadbalancer.server.port=993"
      - "traefik.tcp.services.imaps.loadbalancer.proxyProtocol.version=2"

      - "traefik.tcp.routers.pop3.rule=HostSNI(`*`)"
      - "traefik.tcp.routers.pop3.entrypoints=pop3"
      - "traefik.tcp.routers.pop3.service=pop3"
      - "traefik.tcp.services.pop3.loadbalancer.server.port=110"
      - "traefik.tcp.services.pop3.loadbalancer.proxyProtocol.version=2"

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
  PROXY_PROTOCOL=all-but-http
  TRAEFIK_VERSION=v2
  TLS_FLAVOR=mail-letsencrypt
  WEBROOT_REDIRECT=/sso/login

Using the above configuration, Traefik will proxy all the traffic related to Mailu's FQDNs without requiring duplicate certificates.
