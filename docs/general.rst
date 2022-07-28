General concepts
================

Philosophy
----------

The philosophy behind Mailu is very simple and based on applying the
following principles, with decreasing priority:

 1. a proper mail server runs only free software
 2. a proper mail server is easy to setup and maintain
 3. a proper mail server offers proper security
 4. a proper mail server has a simple and beautiful user interface

Mailu was designed and is kept up to date based on these. Among the 
structuring choices, the following were quite challenging:

 - Mailu is based on containers (plural) so that any part can be reused
   in separate projects and that updating or swapping any component does
   not require changing other ones.
 - Mailu offers mail and does not bloat the default setup.
   Additional features are available but not required.
 - Mailu has a central front container that routes all HTTP and mail
   traffic.
 - Mailu has a Web administration interface that exposes both a Web UI
   and internal API.
 - Mailu authors are all equal in regard to copyright, thus the license
   will remain free unless all contributors agree otherwise.

History
-------

Mailu started in late 2014 and was named Freeposte, the Freeposte.io at
the time. Early Mailu versions were maintained by a french nonprofit
named TeDomum, the initial purpose being to re-design their free e-mail
hosting service as Docker containers and add some fresh UI to the mix
in order to replace old interfaces like PostfixAdmin.

At the time, Post.io was one of the most interesting solutions out there
and was only lacking a free software licence (hence Mailu's initial
name). Later, around late 2015, Mailu became a public project including
contributions from third parties.

Today, Mailu is running many mail instances, but remains a community
project, where everyone is welcome to take part.

