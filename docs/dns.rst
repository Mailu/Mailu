.. _dns_setup:

Setting up your DNS
===================

E-mail has a decentralized architecture: pretty much every e-mail provider on the Internet has the ability to communicate with every other provider to deliver e-mails, much like post-office services from different cities or countries communicate to deliver standard mail.

The analogy stops when it comes to discovery and responsibilities. In the e-mail model, there are most of the time two, maximum three actors in delivering a message: the emitter, an (optional) relay and the recipient server (some architectures are much more complex, but either they can be simplified for the purpose of this document or they are extremely rare). Forgetting about the relay, the emitter has to discover where the recipient server is located around the Internet, which is based on DNS.

Setting up a DNS domain is (almost) mandatory to exchange e-mail on the Internet. Before you start using Mailu, you must have at least one domain setup to receive emails.

The mail server hostname
------------------------

Your mail server will have a unique hostname. That hostname is a fully qualified domain name, that points to your server IP address. How you pick the hostname is up to you, it must of course belong to a domain name that you own or manage and could belong to a domain that your server will receive mail for.

You should pick a meaningful hostname that you can give your users to access the Web interface and other email services. For instance, if your main mail domain is ``mydomain.com`` (the one you setup in ``DOMAIN`` in your configuration file), then you could use ``mail.mydomain.com`` as a mail server hostname.

Set that name in the ``HOSTNAME`` configuration entry. Then depending on your domain provider, make sure that you have an address record (``A``) serving the public IP address of your server:

.. code-block:: bash

  mail.mydomain.com.  IN  A  a.b.c.d

Also, ``a.b.c.d`` should be set in your ``BIND_INTERFACE`` configuration unless your server is in a DMZ and you are using port forwards to expose the services.

Finally, make sure that you have a proper TLS certificate for your mail server hostname and install it according to the instructions in the [[Setup Guide]].

MX entries
----------

Once your server is running and accessible at your mail server hostname, you can simply add new domains in the Web interface.

For every domain that your mail server is responsible for, you must have a corresponding ``MX`` entry in the domain's DNS configuration. That entry is required for other mail servers to discover the hostname of the mail server responsible for receiving the messages, and then its IP address using the ``A`` record you setup earlier.

To setup an ``MX`` record, exact actions will depend on your DNS provider and hoster, but assuming you are using a zone file, you should add for ``mydomain.com``:

.. code-block:: bash

  mydomain.com.  IN  MX  10 mail.mydomain.com.

The number is the ``MX`` priority, which has little importance if you are running a single mail server but should be adjusted if you run a separate backup server.

And for another domain, ``myotherdomain.com`` for example:

.. code-block:: bash

  myotherdomain.com.  IN  MX  10 mail.mydomain.com.

Note that both point to the same mail server hostname, which is unique to your server.

Reverse DNS entries
-------------------

For a mail system, it's highly recommended to set up reverse DNS as well. That means, if your hostname
``mail.mydomain.com`` resolves to ``a.b.c.d``, the IP ``a.b.c.d`` should also resolve back to the same hostname.

You can verify this with

.. code-block:: bash

  nslookup a.b.c.d

Reverse DNS must be set up by the "owner" of the IP address which is usually your hosting provider. You can look it up with ``whois a.b.c.d`` in most cases.

With incorrect reverse DNS setup, most mail systems will reject your emails as spam.


DKIM/SPF & DMARC Entries
------------------------

Finally, you'll need to visit the admin dashboard (or use the cli) to regenerate your DMARC, SPF, and DKIM records.

Once the DNS changes to your host have propagated (and if SSL / domain rules were setup correctly), visit your admin
dashboard at https://example.com/admin/domain/details/example.com. Click on `regenerate keys` and add the required
records to your DNS provider. If you've enabled DKIM/SPF / DMARC and haven't added these entries, your mail might
not get delivered.
