from mailu.internal import internal

from flask import current_app as app
import flask

@internal.route("/autoconfig/mozilla")
def autoconfig_mozilla():
    # https://wiki.mozilla.org/Thunderbird:Autoconfiguration:ConfigFileFormat
    hostname = app.config['HOSTNAME']
    xml = f'''<?xml version=\"1.0\"?>
<clientConfig version=\"1.1\">
<emailProvider id=\"%EMAILDOMAIN%\">
<domain>%EMAILDOMAIN%</domain>

<displayName>Email</displayName>
<displayShortName>Email</displayShortName>

<incomingServer type=\"imap\">
<hostname>{hostname}</hostname>
<port>993</port>
<socketType>SSL</socketType>
<username>%EMAILADDRESS%</username>
<authentication>password-cleartext</authentication>
</incomingServer>

<outgoingServer type=\"smtp\">
<hostname>{hostname}</hostname>
<port>465</port>
<socketType>SSL</socketType>
<username>%EMAILADDRESS%</username>
<authentication>password-cleartext</authentication>
<addThisServer>true</addThisServer>
<useGlobalPreferredServer>true</useGlobalPreferredServer>
</outgoingServer>

<documentation url=\"https://{hostname}/admin/client\">
<descr lang=\"en\">Configure your email client</descr>
</documentation>
</emailProvider>
</clientConfig>\r\n
'''
    return flask.Response(xml, mimetype='text/xml', status=200)
