.. _rpi_build:

Building for a Raspberry Pi
===========================

The build does not need to be done on the Pi.

To do so, go to ``tests/`` and call ``./build_arm.sh``, it will build all necessary images for arm.

To push the locally built images to a remote server, run ``./deploy_to_pi.sh``. Docker 18.09+ is needed to use ``-H ssh://<user>@<host>``.

Adjustments
-----------

``build_arm.sh`` uses some variables passed as ``build-arg`` to docker-compose:

- ``DISTRO``: is the main distro used (ie: alpine:3.8)
- ``PHP_DISTRO``: is used for the ``rainloop`` and ``roundcube`` images
- ``EDGE_DISTRO``: is used for ``radicale`` as edge has dulwich and radicale as packages
