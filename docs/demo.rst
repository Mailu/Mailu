Demonstration server
====================

The demo server is for demonstration and test purposes only. Please be
respectful and keep the demo server functional for others to be able to try it
out.

The server is reset every day at 3am, french time. If you find the server is
unusable, you can still ask for someone to reset it manually on our Matrix
chat channel. Please do not open tickets everytime the server is down. Please
do not open tickets if the server is quite slow: it *is* slow because the
machine is a cheap leased server.

Keep in mind that the demo server is also used for some automated tests and runs
the latest unstable version. If you find actual bugs when using the demo
server, please report these!

Connecting to the server
------------------------

 * Server name : ``test.mailu.io``
 * IP address : ``51.15.169.20``
 * Webmail : https://test.mailu.io/webmail/
 * Admin UI : https://test.mailu.io/admin/
 * Admin login : ``admin@test.mailu.io``
 * Admin password : ``letmein``

Adding domains
--------------

If you wish to add new domains to the server for test purposes, you could
either direct the MX for one of you domains to ``test.mailu.io`` or have your
MX  point to the server's IP address.

Also, all subdomains of ``test.mailu.io`` point to this server. Thus, you can
simply add ``foo.test.mailu.io`` and ``bar.test.mailu.io`` for your tests.
