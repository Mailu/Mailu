Using an external reverse proxy
===============================

One of Mailu's use cases is as part of a larger services platform, where maybe
other Web services are available on other FQDNs served from the same IP address.

In such a configuration, one would usually run a front-end reverse proxy to serve all
Web contents based on criteria like the requested hostname (virtual hosts).

The Mailu team recommends to use Traefik as reverse proxy. This program is solely designed
to act as reverse proxy. It is easy to configure and offers a streamlined experienced when
used with other docker containers on the same host.

When using a reverse proxy, Mailu should still be used for requesting certificates.
This prevents duplicate certificates.
Other reasons are:

- Mailu controls the ciphers and keys used for certificates (Mailu has both RSA and ECDSA certs)
- Mailu cerbot client is configured to prevent hitting ratelimits of the CA
- Due to usage of proxy protocol it is less likely that Mailu becomes an open relay due to misconfiguration of special headers.
- No special scripting is required to copy over certs from the proxy to Mailu

When using Mailu with Traefik as reverse proxy. Traefik is configured to use proxy protocol for all ports, but port 80.
Port 80 is configured to let through the letsencrypt HTTP challenges for Mailu.
This means that if Traefik must request certificates for other services than Mailu, Traefik should use the TLS (TLS-ALPN-01)
challenge method. The HTTP challenge (HTTP-01) cannot be used since this is already used by Mailu.

.. _traefik_proxy:

Traefik as reverse proxy (same host)
------------------------------------

This example is for when Traefik (reverse proxy) runs on the same host as Mailu.
It makes use of the docker configuration method for Traefik.

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

.. code-block:: bash

  REAL_IP_FROM=192.168.203.0/24
  PROXY_PROTOCOL=25,443,465,993,995,4190
  TRAEFIK_VERSION=v2
  TLS_FLAVOR=letsencrypt
  WEBROOT_REDIRECT=/sso/login

Using the above configuration, Traefik will proxy all the traffic related to Mailu's FQDNs without requiring duplicate certificates.

Traefik as reverse proxy (different host)
-----------------------------------------

This example is for when Traefik (reverse proxy) runs on a different server than the Mailu server.
This example makes use of the File configuration method (File Provider) of Traefik.
It makes use of a single static configuration file and one or more dynamic configuration files.

This example uses V3 of Traefik. V2 and V3 of Traefik have some differences in the configuration method.

The contents for the static configuration file. The static configuration file must be provided as argument to Traefik.

.. code-block:: yaml

  #STATIC CONFIGURATION FILE
  #Below value for 'directory' is the location where the dynamic configuration files reside:
  #When a change is made in this folder, Traefik automatically loads or reloads it.
  providers:
    file:
      directory: "/etc/traefik/conf"

  entryPoints:
    web:
      address: :80
    websecure:
      address: :443
    mailu-smtp:
      address: :25
    mailu-imaps:
      address: :993
    mailu-pop3s:
      address: :995
    mailu-submissions:
      address: :465
    mailu-sieve:
      address: :4190

  #Optional, enables access logging at:
  accessLog:
    filePath: "/var/log/traefik_access.log"

  #Optional, enables normal logging at:
  log:
    level: INFO
    filePath: "/var/log/traefik.log"


This is the contents for the dynamic configuration. You can use any filename you want.
The extension must end with .yml and the file must be placed in the configured directory for
dynamic configuration files.


.. code-block:: yaml

  http:
    routers:
      mailu-web:
        entryPoints:
          - web
        rule: "Host(`mail.example.com) || PathPrefix(`/.well-known/acme-challenge/`))"
        service: "mailu-web"
    services:
      mailu-web:
        loadBalancer:
          servers:
            - url: "http://mailu-server"

  tcp:
    routers:
      mailu-websecure:
        entryPoints:
          - websecure
        # Add other FQDN's here
        rule: "HostSNI(`mail.example.com`) || HostSNI(`autoconfig.example.com`) || HostSNI(`mta-sts.example.com`)"
        service: "mailu-websecure"
        tls:
          passthrough: true
      mailu-submissions:
        entryPoints:
          - mailu-submissions
        rule: "HostSNI(`*`)"
        service: "mailu-submissions"
      mailu-imaps:
        entryPoints:
          - mailu-imaps
        rule: "HostSNI(`*`)"
        service: "mailu-imaps"
        tls:
          passthrough: true
      mailu-pop3s:
        entryPoints:
          - mailu-pop3s
        rule: "HostSNI(`*`)"
        service: "mailu-pop3s"
        tls:
          passthrough: true
      mailu-submissions:
        entryPoints:
          - mailu-submissions
        rule: "HostSNI(`*`)"
        service: "mailu-submissions"
        tls:
          passthrough: true
      mailu-sieve:
        entryPoints:
          - mailu-sieve
        rule: "HostSNI(`*`)"
        service: "mailu-sieve"
    services:
      mailu-websecure:
        loadBalancer:
          proxyProtocol:
            version: 2
          servers:
            - address: "mailu-server:443"
      mailu-smtp:
        loadBalancer:
          proxyProtocol:
            version: 2
          servers:
            - address: "mailu-server:25"
      mailu-submissions:
        loadBalancer:
          proxyProtocol:
            version: 2
          servers:
            - address: "mailu-server:465"
      mailu-imaps:
        loadBalancer:
          proxyProtocol:
            version: 2
          servers:
            - address: "mailu-server:993"
      mailu-pop3s:
        loadBalancer:
          proxyProtocol:
            version: 2
          servers:
            - address: "mailu-server:995"
      mailu-sieve:
        loadBalancer:
          proxyProtocol:
            version: 2
          servers:
            - address: "mailu-server:4190"


In the mailu.env file add the following:


.. code-block:: bash

  #Add the IP address of the Traefik server as value for REAL_IP_FROM
  REAL_IP_FROM=192.168.2.300/32
  PROXY_PROTOCOL=25,443,465,993,995,4190
  TLS_FLAVOR=letsencrypt
  WEBROOT_REDIRECT=/sso/login


Using the above configuration, Traefik will proxy all the traffic related to Mailu's FQDNs without requiring duplicate certificates.

.. _caddy_proxy:

Alternative: Using Caddy as reverse proxy
-----------------------------------------

This setup is suitable for when you want to serve Wordpress or other web-facing applications (on port 80 and 443)
on your domains from the same machine as Mailu.

Using Caddy like this will only reverse-proxy the web-facing applications,
leaving MailU to serve the ports related to sendmail and its related services (25, 110, 143, 465, 587, 993, 995, 4190).

.. note::
  In the following example, I assume that MailU is set up in `/opt/mailu` and Wordpress in `/opt/wordpress`.

In your docker-compose.yml, remove 80 and 443 from the `ports` section of the `front` container.

Create a standalone docker-compose file for Caddy, in `/opt/caddy` with something similar to the following:

.. code-block:: yaml

  services:
    caddy:
      image: caddy:2
      restart: unless-stopped
      volumes:
        - "/opt/caddy/conf:/etc/caddy"
        - "/opt/caddy/data:/data"
        - /opt/mailu/certs/letsencrypt:/certs:ro
      ports:
        - "80:80"
        - "443:443"
        - "443:443/udp"
      healthcheck:
        test:
          - "CMD"
          - "sh"
          - "-c"
          - >
            echo -e 'GET /health HTTP/1.1\r\nHost:
            localhost\r\nConnection: close\r\n\r\n' |
            nc localhost 80 | grep -q 'HTTP/1.1 200 OK'
        interval: 30s
        timeout: 5s
        retries: 3
      dns:
        - 192.168.203.254
      networks:
        - mailu_default
        - wordpress_default
  networks:
    mailu_default:
      external: true
    wordpress_default:
      external: true

The volumes section is important, as it mounts the Let's Encrypt certificates into the container (readonly), so
that Caddy can use them to serve the SSL certificates. Also note that the caddy container is on the same network
as the front and wordpress containers, so that it can reach them.

In `/opt/caddy/conf/`, create a file called `Caddyfile` with the following contents:

.. code-block:: caddy


  {
    auto_https disable_redirects
  }

  (healthcheck) {
    handle /health {
      respond "OK"
    }
  }
  (acme) {
    handle /.well-known/acme-challenge/* {
      reverse_proxy front:80
    }
  }
  (mta-sts) {
    handle /.well-known/mta-sts.txt {
      respond <<MTA_STS
        version: STSv1
        mode: enforce
        max_age: 604800
        mx: mail.example.com

        MTA_STS 200
    }
  }
  (tls_certs) {
    tls /certs/live/mailu/fullchain.pem /certs/live/mailu/privkey.pem
    tls /certs/live/mailu-ecdsa/fullchain.pem /certs/live/mailu-ecdsa/privkey.pem
  }

  (proxy_to) {
    import tls_certs
    import acme
    import mta-sts
    reverse_proxy {args[0]} {
      header_up X-Forwarded-For {remote_host}:{remote_port}
      header_up X-Real-IP {remote_host}
      header_up X-Real-Port {remote_port}
    }
  }

  # Handle ACME challenge requests and MTA-STS first
  http:// {
    import healthcheck
    import acme
    import mta-sts
    # Redirect all other HTTP traffic to HTTPS
    handle {
      redir https://{host}{uri}
    }
  }

  www.example.com, example.com {
    import proxy_to wordpress:80
  }

  mail.example.com, mta-sts.example.com {
    handle /*.mobileconfig {
      reverse_proxy front:80 {
        header_down Content-Type application/x-apple-aspen-config
      }
    }
    import proxy_to front:80
  }

This Caddy configuration handles ACME challenge and MTA-STS queries before applying HTTP to HTTPS redirection.

Note that this setup leaves the responsibility of managing and refreshing the Let's Encrypt certificates to Mailu,
and Caddy will only be responsible for serving the SSL certificates given to it.

If you are serving multiple web-facing applications using different names, you can add those names
to the `Caddyfile` as well, reverse-proxying them to the correct container and port for each application,
and make sure that the container is accessible from the Caddy container by adding its network to the
networks section of the Caddy container's Docker Compose file.

In addition, make sure to add the following to the `mailu.env` file:

.. code-block:: docker

  REAL_IP_FROM=192.168.203.0/24
  REAL_IP_HEADER=X-Forwarded-For

This ensures that the X-Forwarded-For header is used to determine the client IP address, instead of the
local IP address of the Caddy container (and will interact properly with the builtin rate-limiting).