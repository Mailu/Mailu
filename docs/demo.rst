Demonstration server
====================

The demo server is for demonstration and test purposes only. Please be
respectful and keep the demo server functional for others to be able to try it
out.

If you find the server is unusable, you can ask for someone to reset it manually on our Matrix
chat channel. Please do not open tickets every time the server is down.
Please do not open tickets if the server is quite slow: it *is* slow because the
services have only limited resources available.

Keep in mind that the demo server runs the latest unstable (master) version.
If you find actual bugs when using the demo server, please report these!

Functionality
-------------

- The server is reset every day at 3am, 12pm, 8pm UTC.
- You can send mail from any client to the server.
  However, the SMTP server is made incapable of relaying the e-mail to the destination server.
  As such, the mail will never arrive. This is to prevent abuse of the server.
- The server is capable of receiving mail for any configured domains.
- The server exposes IMAP, POP3 and SMTP as usual for connection with mail clients such as Thunderbird.
- The RESTful API is enabled.
- The containers have limited (throttled) CPU, this means it can respond slow during heavy operations.
- The containers have limited memory available and will be killed when exceeded.
  This is to prevent people from doing nasty things to the server as a whole.

Connecting to the server
------------------------

 * Server name : ``test.mailu.io``
 * IP address : ``173.249.45.89``
 * Webmail : https://test.mailu.io/webmail/
 * Admin UI : https://test.mailu.io/admin/
 * Admin login : ``admin@test.mailu.io``
 * Admin password : ``Mailu+Demo@test.mailu.io`` (remove + and @test.mailu.io to get the correct password).
 * RESTful API: https://test.mailu.io/api
 * API token: ``Bearer APITokenForMailu``

Adding domains
--------------

If you wish to add new domains to the server for test purposes, you could
either direct the MX for one of your domains to ``test.mailu.io`` or have your
MX  point to the server's IP address.

Also, all subdomains of ``test.mailu.io`` point to this server. Thus, you can
simply add ``foo.test.mailu.io`` and ``bar.test.mailu.io`` for your tests.
