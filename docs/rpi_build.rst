.. _rpi_build:

Building for a Raspberry Pi
===========================

The build does not need to be done on the Pi.

To do so, go to ``tests/`` and call ``./build_arm.sh``, it will build all
necessary images for arm.

To push the locally built images to a remote server, run ``./deploy_to_pi.sh``.
Docker 18.09+ is needed to use ``-H ssh://<user>@<host>``.

Adjustments
-----------

``build_arm.sh`` uses some variables passed as ``build-arg`` to docker-compose:

- ``ALPINE_VER``: version of ALPINE to use
- ``DISTRO``: is the main distro used. Dockerfiles are set on Alpine 3.10, and
  build script overrides for ``balenalib/rpi-alpine:3.10``
- ``QEMU``: Used by webmails dockerfiles. It will add ``qemu-arm-static`` only
  if ``QEMU`` is set to ``arm``
- ``ARCH``: Architecture to use for ``admin``, and ``webmails`` as their images
  are available for those architectures.
