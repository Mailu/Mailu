.. _kubernetes:

Kubernetes setup
================

Prequisites
-----------

Structure
~~~~~~~~~

There’s chosen to have a double NGINX stack for Mailu, this way the main
ingress can still be used to access other websites/domains on your
cluster. This is the current structure:

-  ``NGINX Ingress controller``: Listens to the nodes ports 80 & 443. We have chosen to have a double NGINX stack for Mailu.
-  ``Cert manager``: Creates automatic Lets Encrypt certificates based on an ``Ingress``-objects domain name.
-  ``Mailu NGINX Front daemonset``: This daemonset runs in parallel with the Nginx Ingress Controller and only listens on all E-mail specific ports (25, 110, 143, 587,...). It also listens on 80 and delegates the various http endpoints to the correct services.
-  ``Mailu components``: All Mailu components (imap, smtp, security, webmail,...) are split into separate files to make them more handy to use, you can find the ``YAML`` files in this directory

What you need
~~~~~~~~~~~~~

-  A working Kubernetes cluster (tested with 1.10.5)
-  A working `cert-manager`_ installation
-  A working nginx-ingress controller needed for the lets-encrypt
   certificates. You can find those files in the ``nginx`` subfolder.
   Other ingress controllers that support cert-manager (e.g. traefik)
   should also work.

Cert manager
^^^^^^^^^^^^

The ``Cert-manager`` is quite easy to deploy using Helm when reading the
`docs`_. After booting the ``Cert-manager`` you’ll need a
``ClusterIssuer`` which takes care of all required certificates through
``Ingress`` items. We chose to provide a ``clusterIssuer`` so you can provide SSL certificates
for other namespaces (different websites/services), if you don't need this option, you can easily change this by
changing ``clusterIssuer`` to ``Issuer`` and adding the ``namespace: mailu-mailserver`` to the metadata.
An example of a production and a staging ``clusterIssuer``:

.. code:: yaml

   # This clusterIssuer example uses the staging environment for testing first
   apiVersion: certmanager.k8s.io/v1alpha1
   kind: ClusterIssuer
   metadata:
     name: letsencrypt-stage
   spec:
     acme:
       email: something@example.com
       http01: {}
       privateKeySecretRef:
         name: letsencrypt-stage
       server: https://acme-staging-v02.api.letsencrypt.org/directory

.. code:: yaml

   # This clusterIssuer example uses the production environment
   apiVersion: certmanager.k8s.io/v1alpha1
   kind: ClusterIssuer
   metadata:
     name: letsencrypt-prod
   spec:
     acme:
       email: something@example.com
       http01: {}
       privateKeySecretRef:
         name: letsencrypt-prod
       server: https://acme-v02.api.letsencrypt.org/directory

**IMPORTANT**: ``ingress.yaml`` uses the ``letsencrypt-stage`` ``clusterIssuer``. If you are ready for production,
change this field in ``ingress.yaml`` file to ``letsencrypt-prod`` or whatever name you chose for the production.
If you choose for ``Issuer`` instead of ``clusterIssuer`` you also need to change the annotation to ``certmanager.k8s.io/issuer`` instead of ``certmanager.k8s.io/cluster-issuer``

Deploying Mailu
---------------

All manifests can be found in the ``mailu`` subdirectory. All commands
below need to be run from this subdirectory

Personalization
~~~~~~~~~~~~~~~

-  All services run in the same namespace, currently ``mailu-mailserver``. So if you want to use a different one, change the ``namespace`` value in **every** file
-  Check the ``storage-class`` field in the ``pvc.yaml`` file, you can also change the sizes to your liking. Note that you need ``RWX`` (read-write-many) and ``RWO`` (read-write-once) storageclasses.
-  Check the ``configmap.yaml`` and adapt it to your needs. Be sure to check the kubernetes DNS values at the end (if you use a different namespace)
-  Check the ``ingress.yaml`` file and change it to the domain you want (this is for the kubernetes ingress controller to handle the admin, webmail, webdav and auth connections)

Installation
------------

Boot the Mailu components
~~~~~~~~~~~~~~~~~~~~~~~~~

To start Mailu, run the following commands from the ``docs/kubernetes/mailu`` directory

.. code-block:: bash

    kubectl create -f rbac.yaml
    kubectl create -f configmap.yaml
    kubectl create -f pvc.yaml
    kubectl create -f redis.yaml
    kubectl create -f front.yaml
    kubectl create -f webmail.yaml
    kubectl create -f imap.yaml
    kubectl create -f security.yaml
    kubectl create -f smtp.yaml
    kubectl create -f fetchmail.yaml
    kubectl create -f admin.yaml
    kubectl create -f webdav.yaml
    kubectl create -f ingress.yaml


Create the first admin account
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When the cluster is online you need to create you master user to access https://mail.example.com/admin

You can create it now manually, or have the system create it automatically.

If you want the system to create the admin user account automatically, see :ref:`admin_account`
about the environment variables needed (``INITIAL_ADMIN_*``).
Also, important, taking into consideration that a pod in Kubernetes can be stopped/rescheduled at
any time, you should set ``INITIAL_ADMIN_MODE`` to either ``update`` or ``ifmissing`` - depending on what you 
want to happen to its password.


To create the admin user account manually, enter the main ``admin`` pod:

.. code-block:: bash

    kubectl -n mailu-mailserver get po
    kubectl -n mailu-mailserver exec -it mailu-admin-.... /bin/sh

And in the pod run the following command. The command uses following entries:

.. code-block:: bash

    flask mailu admin root example.com password

- ``admin`` Make it an admin user
- ``root`` The first part of the e-mail address (ROOT@example.com)
- ``example.com`` the domain appendix
- ``password`` the chosen password for the user


Now you should be able to login on the mail account: https://mail.example.com/admin


Adaptations
-----------

Dovecot
~~~~~~~

- If you are using Dovecot on a shared file system (Glusterfs, NFS,...), you need to create a special override otherwise a lot of indexing errors will occur on your Dovecot pod.
- I also higher the number of max connections per IP. Now it's limited to 10.

Enter the dovecot pod:

.. code:: bash

    kubectl -n mailu-mailserver get po
    kubectl -n mailu-mailserver exec -it mailu-imap-.... /bin/sh

Create the file ``overrides/dovecot.conf``

.. code:: bash

    vi /overrides/dovecot.conf

And enter following contents:

.. code:: bash

    mail_nfs_index = yes
    mail_nfs_storage = yes
    mail_fsync = always
    mmap_disable = yes
    mail_max_userip_connections=100

Save and close the file and delete the imap pod to get it recreated.

.. code:: bash

    kubectl -n mailu-mailserver delete po/mailu-imap-....

Wait for the pod to recreate and you're online!
Happy mailing!

.. _here: https://github.com/hacor/Mailu/blob/master/core/postfix/conf/main.cf#L35
.. _cert-manager: https://github.com/jetstack/cert-manager
.. _docs: https://cert-manager.io/docs/installation/kubernetes/#installing-with-helm

Imap login fix
~~~~~~~~~~~~~~

If it seems you're not able to login using IMAP on your Mailu accounts, check the logs of the imap container to see whether it's a permissions problem on the database.
This problem can be easily fixed by running following commands:

.. code:: bash

    kubectl -n mailu-mailserver exec -it mailu-imap-... /bin/sh
    chmod 777 /data/main.db

If the login problem still persists, or more specific, happens now and then and you see some Auth problems on your webmail or mail client, try following steps:

- Add ``auth_debug=yes`` to the ``/overrides/dovecot.conf`` file and delete the pod in order to start a new one, which loads the configuration
- Depending on your network configuration you could still see some ``allow_nets check failed`` results in the logs. This means that the IP is not allowed a login
- If this is happening your network plugin has troubles with the Nginx Ingress Controller using the ``hostNetwork: true`` option. Known cases: Flannel and Calico.
- You should uncomment ``POD_ADDRESS_RANGE`` in the ``configmap.yaml`` file and add the IP range of your pod network bridge (the range that sadly has failed the ``allowed_nets`` test)
- Delete the Admin pod and wait for it to restart

.. code:: bash

    kubectl -n mailu-mailserver get po
    kubectl -n mailu-mailserver delete po/mailu-admin...

Happy mailing!
