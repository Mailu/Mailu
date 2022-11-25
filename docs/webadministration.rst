Web administration interface
============================

The web administration interface is the main website for maintaining your Mailu installation.
For brevity the web administration interface will now be mentioned as admin gui.
It offers the following configuration options:

* change display name.

* change the logged in user's password.

* change user defined spam filter tolerance.

* configure automatic forwarding.

* configure automatic email replies (out of office replies).

* configure fetchmail for automatic email retrieval (from 3rd-party servers).

* configure application passwords.

* send broadcast messages to all users.

* configure global administration users.

* configure relayed domains.

* access Rspamd webui.

* Configure all email domains served by Mailu, including:

    * generating dkim and dmarc keys for a domain.

    * view email domain information on how to configure your SPF, DMARC, DKIM and MX dns records for an email domain.

    * Add new email domains.

    * For existing domains, configure users, quotas, aliases, administrators and alternative domain names.

* access the webmail site.

* lookup settings for configuring your email client.


Access the web administration interface
---------------------------------------

The admin GUI is by default accessed via the URL `https://<my domain>/admin`, when it's enabled in the setup utility 
or by manually setting `ADMIN=true` in `mailu.env`.
To login the admin GUI enter the email address and password of an user.

Only global administrator users have access to all configuration settings and the Rspamd webgui. Other users will be 
presented with settings for only their account, and domains they are managers of.
To create a user who is a global administrator for a new installation, the Mailu.env file can be adapted.
For more information see the section 'Admin account - automatic creation' in :ref:`the configuration reference <admin_account>`.

The following sections are only accessible for global administrators:

* send broadcast messages to all users (Menu item Broadcasts)

* configure global administration users (Menu item Administrators)

* configure relayed domains (Menu item Relayed domains)

* access Rspamd webui (Menu item Antispam)

* Configure all email domains served by Mailu (Menu item Mail domains)


.. _webadministration_settings:

Settings
--------
After logging in the web administration interface, the settings page is loaded.
On the settings page the settings of the currently logged in user can be changed.
Changes are saved and effective immediately after clicking the Save Settings button at the bottom of the page.


Display name
````````````

On the settings page the displayed name can be changed of the logged in user.
This display name is only used within the web administration interface.


Antispam
````````

Under the section `Antispam` the spam filter can be enabled or disabled for the logged in user. By default the spam filter is enabled.

When the spam filter is disabled, all received email messages will go to the inbox folder of the logged in user.
The exception to this rule, are email messages with an extremely high spam score. These email messages are always rejected by Rspamd.

When the spam filter is enabled, received email messages will be moved to the logged in user's inbox folder or junk folder depending on the user defined spam filter tolerance.

The user defined spam filter tolerance determines when an email is classified as ham (moved to the inbox folder) or spam (moved to the junk folder).
The default value is 80%. The lower the spam filter tolerance, the more false positives (ham classified as spam). The higher the spam filter tolerance, the more false negatives (spam classified as ham).
For more information see the :ref:`antispam documentation <antispam_howto>`.

Auto-forward
`````````````
Under the section `Auto-forward`, the automatic forwarding of received email messages can be enabled. When enabled, all received email messages are forwarded to the specified email address.

The option "Keep a copy of the emails" can be ticked, to keep a copy of the received email message in the inbox folder.

In the destination textbox, the email addresses can be entered for automatic forwarding. When entering multiple email addresses the comma (',') must be used as delimiter.


Update password
---------------

On the `update password` page, the password of the logged in user can be changed. Changes are effective immediately.


.. _webadministration_auto-reply:

Auto-reply
----------

On the `auto-reply` page, automatic replies can be configured. This is also known as out of office (ooo) or out of facility (oof) replies.

To enable automatic replies tick the checkbox 'Enable automatic reply'.

Under Reply subject the email subject for automatic replies can be configured. When a reply subject is entered, this subject will be used for the automatic reply.

When no reply subject is entered, the automatic reply will have the subject `auto: <subject from received email>`.
E.g. if the email subject of the received email message is "how are you?", then the email subject of the automatic reply is `auto: how are you?`.


.. _webadministration_fetched_accounts:

Fetched accounts
----------------

This page is only available when the Fetchmail container is part of your Mailu deployment.
Fetchmail can be enabled when creating the docker-compose.yml file with the setup utility (https://setup.mailu.io).

On the `fetched accounts` page you can configure email accounts from which email messages will be retrieved.
Only unread email messages are retrieved from the specified email account.
By default Fetchmail will retrieve email messages every 10 minutes. This can be changed in the Mailu.env file.
For more information on changing the polling interval see :ref:`the configuration reference <fetchmail>`.


You can add a fetched account by clicking on the `Add an account` button on the top right of the page. To add an fetched account, the following settings must be configured:

* Protocol (IMAP or POP3). The protocol used for accessing the email server.

* Hostname or IP. The hostname or IP address of the email server.

* TCP port. The TCP port the email server listens on. Common ports are 993 (IMAPS with TLS), 143 (IMAP with STARTTLS), 995 (POP3S with TLS) or 110 (POP3 with STARTTLS).

* Enable TLS. Tick this setting if the email server requires TLS/SSL instead of STARTTLS.

* Username. The user name for logging in to the email server. Normally this is the email address or the email address' local-part (the part before @).

* Password. The password for logging in to the email server.

* Keep emails on the server. When ticked, retains the email message in the email account after retrieving it.

* Scan emails. When ticked, all the fetched emails will go through the local filters (rspamd, clamav, ...).

* Folders. A comma separated list of folders to fetch from the server. This is optional, by default only the INBOX will be pulled.

Click the submit button to apply settings. With the default polling interval, fetchmail will start polling the email account after ``FETCHMAIL_DELAY``.


Authentication tokens
---------------------

On the `authentication tokens` page, authentication tokens can be created. Authentications tokens are also known as application passwords.
The purpose of an authentication token is to create a unique and strong password that can be used by a single application to authenticate as the logged in user's email account.
The application will use this authentication token instead of the logged in user's password for sending/receiving email.
This allows safe access to the logged in user's email account. At any moment, the authentication token can be deleted so that the application has no access to the logged in user's email account anymore.

By clicking on the New token button on the top right of the page, a new authentication token can be created. On this page the generated authentication token will only be displayed once.
After saving the application token it is not possible anymore to view the unique password.

The comment field can be used to enter a description for the authentication token. For example the name of the application the application token is created for.

In the Authorized IP field a white listed IP address can be entered. When an IP address is entered, then the application token can only be used when the IP address of the client matches with this IP address.
When no IP address is entered, there is no restriction on IP address. It is not possible to enter multiple IP addresses.


Announcement
------------

On the `announcement` page, the global administrator can send an email message to all email accounts on the Mailu server. This message will be received as an email message in the inbox folder of each user on the Mailu server.
On the announcement page there are the following options:

* Announcement subject. The subject of the announcement email message.

* Announcement body. The body of the announcement email message.

Click on send to send the announcement email message to all users.


Administrators
--------------

On the `administrators` page, global administrators can be added. A global administrator must be an existing user on the Mailu server.
A global administrator can change `any setting` in the admin GUI. Be careful that you trust the user who you make a global administrator.


Relayed domains
---------------

On the `relayed domains list` page, destination domains can be added that Mailu will relay email messages for without authentication.
This means that for these destination domains, other email clients or email servers can send email via Mailu unauthenticated via port 25 to this destination domain.
For example if the destination domain example.com is added. Any emails to example.com (john@example.com) will be relayed to example.com.
Example scenario's are:

* relay domain from a backup server.

* allow relay for a specific domain for technical reasons.

* relay mails to mailing list servers.


On the new relayed domain page the following options can be entered for a new relayed domain:

* Relayed domain name. The domain name that is relayed. Email messages addressed to this domain (To: John@example.com), will be forwarded to this domain.
  No authentication is required.

* Remote host (optional). The host that will be used for relaying the email message.
  When this field is blank, the Mailu server will directly send the email message to the mail server  of the relayed domain.
  When a remote host is specified it can be prefixed by ``mx:`` or ``lmtp:`` and followed by a port number: ``:port``).

  ================  =====================================  =========================
  Remote host       Description                            postfix transport:nexthop
  ================  =====================================  =========================
  empty             use MX of relay domain                 smtp:domain
  :port             use MX of relay domain and use port    smtp:domain:port
  target            resolve A/AAAA of target               smtp:[target]
  target:port       resolve A/AAAA of target and use port  smtp:[target]:port
  mx:target         resolve MX of target                   smtp:target
  mx:target:port    resolve MX of target and use port      smtp:target:port
  lmtp:target       resolve A/AAAA of target               lmtp:target
  lmtp:target:port  resolve A/AAAA of target and use port  lmtp:target:port
  ================  =====================================  =========================

  `target` can also be an IPv4 or IPv6 address (an IPv6 address must be enclosed in []: ``[2001:DB8::]``).

* Comment. A text field where a comment can be entered to describe the entry.

Changes are effective immediately after clicking the Save button.

Antispam
--------

The menu item Antispam opens the Rspamd webgui. For more information how spam filtering works in Mailu see the :ref:`Spam filtering page <antispam_howto_block>`.
The spam filtering page also contains a section that describes how to create a local blacklist for blocking email messages from specific domains.
The Rspamd webgui offers basic functions for setting metric actions, scores, viewing statistics and learning.

The following settings are not persisent and are *lost* when the Antispam container is recreated or restarted:

* On the configuration tab, any changes to config files that do not reside in /var/lib or /etc/rspamd/override.d. The last location is mapped to the Mailu overrides folder.

* All information on the History tab.


The following settings are persistent and will survive container recreation:

* All information on the Status tab

* All information on the Throughput tab.

* On the Configuration tab, the changes made to action values (greylist, probably spam ....) and config files that reside in /var/lib or /etc/rspamd/override.d. The last location is mapped to the Mailu overrides folder.

* Any changes made on the Symbols tab.

* Any email messages that have been submitted for spam/ham learning on the Scan/Learn tab.


Mail domains
------------

On the `Mail domains` page all the domains served by Mailu are configured. Via the new domain button (top right) a new mail domain can be added. Please note that you may have to add the new domain to `HOSTNAMES` in your :ref:`mailu.env file <common_cfg>`. For existing domains you can access settings via the icons in the Actions column and Manage column. From left to right you have the following options within the Action column and Manage column.

Details
```````

This page is also accessible for domain managers. On the details page all DNS settings are displayed for configuring your DNS server. It contains information on what to configure as MX record and SPF record. On this page it is also possible to (re-)generate the keys for DKIM and DMARC. The option for generating keys for DKIM and DMARC is only available for global administrators.  After generating the keys for DKIM and DMARC, this page will also show the DNS records for configuring the DKIM/DMARC records on the DNS server.


Edit
````

This page is only accessible for global administrators. On the edit page, the global settings for the domain can be changed.

* Maximum user count. The maximum amount of users that can be created under this domain. Once this limit is reached it is not possible anymore to add users to the domain; and it is also not possible for users to self-register.

* Maximum alias count. The maximum amount of aliases that can be created for an email account.

* Maximum user quota. The maximum amount of quota that can be assigned to a user. When creating or editing a user, this sets the limit on the maximum amount of quota that can be assigned to the user.

* Enable sign-up. When this option is ticked, self-registration is enabled. When the Admin GUI is accessed, in the menu list the option Signup becomes available.
  Obviously this menu item is only visible when signed out. On the Signup page a user can create an email account.
  If your Admin GUI is available to the public internet, this means your Mailu installation basically becomes a free email provider.
  Use this option with care!

* Comment. Description for the domain. This description is visible on the parent domains list page.

Delete
``````

This page is only accessible for global administrators. This page allows you to delete the domain. The Admin GUI will ask for confirmation if the domain must be really deleted.


Users
`````

This page is also accessible for domain managers. On the users page new users can be added via the Add user button (top right of page). For existing users the following options are available via the columns Actions and User settings (from left to right)

* Edit. For all available options see :ref:`the Add user page <webadministration_add_user>`.

* Delete. Deletes the user. The Admin GUI will ask for confirmation if the user must be really deleted.

* Setting. Access the settings page of the user. See :ref:`the settings page <webadministration_settings>` for more information.

* Auto-reply. Access the auto-reply page of the user. See the :ref:`auto-reply page <webadministration_auto-reply>` for more information.

* Fetched accounts. Access the fetched accounts page of the user. See the :ref:`fetched accounts page <webadministration_fetched_accounts>` for more information.

This page also shows an overview of the following settings of an user:

* Email. The email address of the user.

* Features. Shows if IMAP or POP3 access is enabled and whether the user should be allowed to spoof emails.

* Storage quota. Shows how much assigned storage has been consumed.

* Sending Quota. The sending quota is the limit of messages a single user can send per day. 

* Comment. A description for the user.

* Created. Date when the user was created.

* Last edit. Last date when the user was modified. 

.. _webadministration_add_user:

Add user
^^^^^^^^

For adding a new user the following options can be configured.

* E-mail. The email address of the new user.

* Password/Confirm password. The password for the new user. The new user can change his password after logging in the Admin GUI.

* Displayed name. The display name of the user within the Admin GUI.

* Comment. A description for the user. This description is shown on the Users page.

* Enabled. Tick this checkbox to enable the user account. When an user is disabled, the user is unable to login to the Admin GUI or webmail or access his email via IMAP/POP3 or send mail.
  The email inbox of the user is still retained. This option can be used to temporarily suspend an user account.

* Storage Quota. The maximum quota for the user's email box.

* Allow IMAP access. When ticked, allows email retrieval via the IMAP protocol.

* Allow POP3 access. When ticked, allows email retrieval via the POP3 protocol.

* Allow the user to spoof the sender. When ticked, allows the user to send email as anyone.


Aliases
```````

This page is also accessible for domain managers. On the aliases page, aliases can be added for email addresses. An alias is a way to disguise another email address.
Everything sent to an alias email address is actually received in the primary email account's inbox of the destination email address.
Aliases can diversify a single email account without having to create multiple email addresses (users).
It is also possible to add multiple email addresses to the destination field. All incoming mails will be sent to each users inbox in this case.

The following options are available when adding an alias:

* Alias. The alias to create for the specified email address. You cannot use an existing email address.

* Use SQL LIKE Syntax (e.g. for catch-all aliases). When this option is ticked, you can use SQL LIKE syntax as alias.
  The SQL LIKE syntax is used to match text values against a pattern using wildcards. There are two wildcards that can be used with SQL LIKE syntax:

    * % - The percent sign represents zero, one, or multiple characters
    * _ - The underscore represents a single character

  Examples are:
    * a% - Finds any values that start with "a"
    * %a - Finds any values that end with "a"
    * %or% - Finds any values that have "or" in any position
    * _r% - Finds any values that have "r" in the second position
    * a_% - Finds any values that start with "a" and are at least 2 characters in length
    * a__% - Finds any values that start with "a" and are at least 3 characters in length
    * a%o - Finds any values that start with "a" and ends with "o"

* Destination. The destination email address for the alias. Click in the Destination text box to access a drop down list where you can select a destination email address.

* Comment. A description for the alias. This description is visible on the Alias list page.


Managers
````````

This page is also accessible for domain managers. On the `managers list` page, managers can be added for the domain and can be deleted.
Managers have access to configuration settings of the domain.
On the `add manager` page you can click on the manager email text box to access a drop down list of users that can be made a manager of the domain.


Alternatives
````````````

This page is only accessible for global administrators. On the alternatives page, alternative domains can be added for the domain.
An alternative domain acts as a copy of a given domain.
Everything sent to an alternative domain, is actually received in the domain the alternative is created for.
This allows you to receive emails for multiple domains while using a single domain.
For example if the main domain has the email address user@example.com, and the alternative domain is mymail.com,
then email send to user@mymail.com will end up in the email box of user@example.com.

New domain
`````````````````

This page is only accessible for global administrators. Via this page a new domain can be added to Mailu. The following options must be defined for adding a domain:

* domain name. The name of the domain.

* Maximum user count. The maximum amount of users that can be created under this domain. Once this limit is reached it is not possible anymore to add users to the domain; and it is also not possible for users to self-register.

* Maximum alias count. The maximum amount of aliases that can be made for an email account.

* Maximum user quota. The maximum amount of quota that can be assigned to a user. When creating or editing a user, this sets the limit on the maximum amount of quota that can be assigned to the user.

* Enable sign-up. When this option is ticked, self-registration is enabled. When the Admin GUI is accessed, in the menu list the option Signup becomes available.
  Obviously this menu item is only visible when signed out. On the Signup page a user can create an email account.
  If your Admin GUI is available to the public internet, this means your Mailu installation basically becomes a free email provider.
  Use this option with care!

* Comment. Description for the domain. This description is visible on the parent domains list page.


Webmail
-------

The menu item `Webmail` opens the webmail page. This option is only available if the webmail container is running and is enabled in the mailu.env file.


Client setup
------------

The menu item `Client setup` shows all settings for configuring your email client for connecting to Mailu.


Website
-------

The menu item `Website` forwards the user to the URL that is configured in variable WEBSITE=xxxxx in the mailu.env environment file.



Help
----

The menu item `Help` links to the official Mailu documentation website https://mailu.io/


Sign out
--------

The menu item `Sign out` signs out the currently logged in user.
