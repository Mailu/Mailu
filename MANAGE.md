
Upgrading the mail server
=========================

First check upstream for changes in the ``docker-compose.yml`` or in the
``freeposte.env`` files. Update these files, then simply pull the latest
images and recreate the containers :

```
docker-compose pull
docker-compose up -d
```

Monitoring the mail server
==========================

Logs are managed by Docker directly. You can easily read your logs using :

```
docker-compose logs
```

Docker is able to forward logs to multiple log engines. Read the following documentation or details: https://docs.docker.com/engine/admin/logging/overview/.