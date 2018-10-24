Maintain a Mailu server
=======================

Upgrading the mail server
-------------------------

First check upstream for changes in the ``docker-compose.yml`` or in the
``.env`` files. Also, check ``CHANGELOG.md`` for changes that you
might not want to include.

Update your ``.env`` file to reflect the version that you wish to install (if
you are running ``stable`` or ``latest``, you may skip this and proceed), then
simply pull the latest images and recreate the containers :

.. code-block:: bash

  docker-compose pull
  docker-compose up -d

Monitoring the mail server
--------------------------

Logs are managed by Docker directly. You can easily read your logs using:

.. code-block:: bash

  docker-compose logs

Docker is able to forward logs to multiple log engines. Read the following documentation for details: https://docs.docker.com/engine/admin/logging/overview/.

Migrating an instance
---------------------

The SMTP protocol has an embedded retry mechanism and multiple MX that can serve a single domain, so that most migration processes or maintenance processes do not require any specific care.

Mailu relies heavily on files for storing everything, which helps the migration process, that can be performed based on file synchronization.

The suggested migration process consists of setting up a new backup server that drops incoming emails (Mailu not started), synchronizing both servers, stopping the main server and launching the backup server. Then, the backup server is switched as a main MX and the old server is deleted.

1. Prepare your new server, copy your ``docker-compose.yml``, ``.env`` and basic configuration files to the server, so that it is ready to start configuration Mailu, *do not start Mailu*
2. Setup your DNS so that the backup server is an additional, deprioritized MX for the domain; this can be complex if you serve many domains, in which case you can simply accept that some remote MX will retry for a couple of minutes, skip this step
3. While your DNS TTL expires and your modification propagates, start *rsyncing* your Mailu directory (``data``, ``dkim``, ``mail``, etc.) to the new server, repeat until there are only a couple files synchronized
4. Stop Mailu on the old server and run a final ``rsync`` while no process is writing to the files
5. Start Mailu on the new server, and production should be back to normal
6. Set your new server as the main MX for your domains, if you did not set an additional MX, make sure you still change the ``A`` and ``AAAA`` record for your MX name.
