.. _arm_images:

Arm images for Mailu
====================

Using Mailu arm images
----------------------

The Mailu project makes use of github actions for automatic CI/CD.
Github actions only has x64 (amd64) runners. This means we can build the arm images
using QEMU, but we cannot test the images. For this reason the arm images have
a BETA status. We only guarantee that the images could be built.


We strongly recommend to make use of the pinned version (tag 1.9.10 vs tag 1.9).
Pinned versions (tag x.y.z) are not updated. This allows upgrading manually by changing the
tag to the next pinned version.


Whenever images are deployed for master and for releases (branch x.y),
images are also built for arm.

The images are pushed with -arm appended to the tag. For example:

- admin:master-arm
- admin:1.10-arm

To use these images, simply use setup.mailu.io for generating the docker-composse.yml
file and mailu.env file. Then in the docker-compose.yml file append -arm to the tags of
all images from the mailu docker repository.

Build manually
--------------
It is possible to build the images manually. There are two possibilities for this.

Github actions
``````````````
The main workflow build-test-deploy can be triggered manually.
Via the parameter ``architecture`` the target platform can be specified.
Use the value ``'linux/arm64,linux/arm/v7'``.


To use it:

1. Fork the Mailu github project.
2. In the settings of your forked project, configure the secrets Docker_Login and Docker_Password. For more information on these secrets, see the comments in the build-test-deploy.yml file.
3. In the forked project, trigger the workflow build-test-deploy manually.
4. For the parameter architecture use the value ``'linux/arm64,linux/arm/v7'``.


Manually
````````
It is also possible to build the images manually on bare-metal.
The buildx file ``tests/build.hcl`` can be used for this.


To build manually:

1. Install QEMU static binaries. This is only required, if you don't built on an arm machine. For Ubuntu install qemu-user-static.
2. Clone the Mailu github project.
3. Export the parameters.
4. Create a buildx builder instance
5. Run buildx overriding the architecture.

For example:

.. code-block:: bash

  docker login
  Username: Foo
  Password: Bar
  export DOCKER_ORG="Foo"
  export MAILU_VERSION="master-arm"
  export MAILU_PINNED_VERSION="hash"
  docker buildx create --use
  docker buildx bake -f tests/build.hcl --push --set *.platform=linux/arm64,linux/arm/v7
