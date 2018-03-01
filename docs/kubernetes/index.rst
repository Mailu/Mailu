Kubernetes setup
================

Please note that Kubernetes setup is not yet well supported or documented, all
tests currently run on Docker Compose. The configuration has not yet been updated
to work properly with ngin authentication proxy.

Prepare the environment
-----------------------

The resource configurations in this folder assume that you have `Kubernetes Ingress`_
set up for your cluster. If you are not using the `NGINX Ingress Controller for Kubernetes`_,
please ensure that the configuration specified in the file matches your set up.

.. _`Kubernetes Ingress`: https://kubernetes.io/docs/concepts/services-networking/ingress/
.. _`NGINX Ingress Controller for Kubernetes`: https://github.com/kubernetes/ingress/tree/master/controllers/nginx

Setup the Kubernetes service
----------------------------

Using the resource configurations is simple:

1. ``kubectl apply -f kubernetes-nginx-ingress-controller.yaml`` to configure an ingress controller with the proper settings. (If you have one set up already you may need to port the configuration to your own ingress).
2. ``kubectl apply -f kubernetes-mailu.yaml`` to create the resources required to run Mailu.

Based on the configuration, your Mailu instance should be available at ``mail.<hostname>.tld/admin`` (note that visiting just ``mail.<hostname>.tld`` will likely result in a 404 error).
