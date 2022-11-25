Project guidelines
==================

Why these guidelines
--------------------

This page is written as an evolving memo of the main development guidelines
that we follow or should follow as contributors. Some are basic development
constraints, some are architectural opinions.

If you contribute to this project, please read through them all and read the
architectural documentation. Reviewers will check that your contributions
match these guidelines among other things.

If you feel one of the guidelines is wrong or incomplete, please come and
discuss on our messaging channel, then open a pull request including the
change you would like to make and the reasons why in the description, we can
then formally discuss it and review it following our usual review process.

General
-------

What features should be included
````````````````````````````````

Mailu is a mail server. That said, mail works in an ecosystem and we should set
clear boundaries on what Mailu is and what it is not. Beyond mail, we include
features that mail is dependent on in some way, not the other way around.

For instance, we include contact management and a dav service for synchronizing
contacts, because sending mail is made easier with manageable contacts. We do
not include a calendar management app or file sharing app, because mail is not
dependent on them.

Examples of features we will not include in Mailu are: calendars, documents and
file sharing, full-sized groupware, instant messaging, password management. If
you want these features, have success in connecting them to Mailu and want to share, please
write some useful documentation for others to do the same.

What behavior is tolerated
``````````````````````````

Be respectful of others and others contributions. If you find a whole part of
Maiu is terribly written or badly designed, please open an issue to discuss it
calmly or come and have a chat on our channel.

Any PR that just rewrites a huge part of the code by making mostly cosmetic or
opinionated changes without prior discussion will be received with a polite
"no".

Architecture
------------

What setups should be supported
```````````````````````````````

Mailu supports out-of-the-box Docker Compose and Kubernetes
environments. In those environments, it consists of many containers and
supports hosting some of those containers in a separate environment.

It supports hosting the data outside of the environment, in as many types of
database servers as can be documented.

It supports spreading and scaling the containers across hosts, except for
those that share volumes. The intention is to stop sharing volumes between
containers.

What is a Mailu container
`````````````````````````

A Mailu container should provide one service and run one type of process only.
A new Webmail should be in a separate container, a new antivirus or a new
antispam should be in a separate container.

A container is developed as a single directory under the proper category in
the main repository, the only exception being service containers that should
only use official Docker images. Categories are:

- core, for mandatory components
- optional, for optional components
- webmail, for webmails

A container image name must explicitly state the technology being used.
Container versions are synchronized and all containers are always built at
once. The service name associated in the Compose file or Kubernetes configuration
should match the container image name.

How configuration should be managed
```````````````````````````````````

Anything that is static should be managed using environment variables.
Configuration files should be compiled at runtime by the container `start.py`
script and all conditional syntax should be handled using Jinja logic.

The `socrate` Python package should include relevant functions for container
lifecycle management.

Anything that is not static, i.e. able to change at runtime, either due to
configuration in the admin UI or user behavior, should take advantage of the
admin API. The `podop` package binds mail specific software (Postfix and Dovecot
at the moment) to the admin API, other containers should use specific API calls.

What traffic should go through the nginx container
``````````````````````````````````````````````````

All of it. All traffic, including HTTP(S), IMAP, SMTP, POP3, should go through
the front container.

More generally, the front container is responsible for routing that traffic based
on the incoming port or the HTTP browsing logic. It handles protocol rewriting
for security, authentication, rejects based on identity or IP address.

How browsing should be managed
``````````````````````````````

The nginx container is responsible for routing all Web traffic. Web traffic should
go directly from the nginx container to the target container.

All traffic to a container should be accessed at ``/<container_name>`` for a given
container. If multiple types of traffic are routed for a specific container, they
should be accessed at ``/<container_name>/<traffic_type_a>`` and
``/<container_name>/<traffic_type_b>``, for instance ``/admin/ui`` or
``/admin/api``.

Traffic directed to ``/`` should be routed to an endpoint on the admin container
responsible for dynamically redirecting it. That last redirect must use a
302.

Any traffic to a non existing endpoint must return a 404.


How authentication should work
``````````````````````````````

Authentication should be managed by the nginx container, based on the admin
container API. The only exception is authentication to the admin container
itself, that is handled directly.

Authentication API in the admin container should contain the logic for
account management (allowed features, etc.) and rate limiting.

Configuration
-------------

Where should configuration files be stored
``````````````````````````````````````````

Configuration files should ideally be stored in the most standard place for the
tool being configured. For instance, if the tool usually accepts configuration
files in ``/etc``, then configuration should be written there.

Should we use default configuration
```````````````````````````````````

Some tools ship with default configuration, that handles the standard behavior.
Using this configuration is prone to later changes and unexpected side effects.
We should always provide all required configuration, including the base files,
and not rely on default configuration files from the distribution.

For that reason, in case the tool looks for specific files and include them
automatically, we should overwrite them or delete them.

How should configuration be overridden
``````````````````````````````````````

Some containers support configuration override. For this feature, we should
ideally look for conditional configuration inclusion in the configuration syntax
and use it. If the tool supports multiple methods of overrides, we should use
the one that supports overriding the most configuration.

In case the tool does not support conditional inclusion, we can add the
override logic in the `start.py` script.

How much should configuration be documented
```````````````````````````````````````````

We should not keep default documentation included by the distribution when
providing configuration files.
We should organize configuration files in section relevant to the type of things
we configure.
We should add comments, and point to Github issues or public documentation when
required, in order to make our choices explicit.

Coding
------

Coding standards
````````````````

All Python code should comply with PEP-8. We should review our code using
pylint.

We should comply with architectural recommendations from the Flask
documentation.

Models and database
```````````````````

All model classes should only use generic types that are compatible with most
supported database backends.

No database specific configuration should be included in the models, no table
name should be forced and no schema specifics should be configured. These
should be handled by the migration scripts and only used when absolutely
necessary.

Updating the dependencies
`````````````````````````

Every major change to the admin Python code should be preceded by an upgrade
of the dependencies. The dependency upgrade should be tested then provided
as a separate PR before the actual changes.
