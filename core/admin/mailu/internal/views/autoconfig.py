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
</clientConfig>\r\n'''
    return flask.Response(xml, mimetype='text/xml', status=200)

@internal.route("/autoconfig/microsoft")
def autoconfig_microsoft():
    # https://docs.microsoft.com/en-us/previous-versions/office/office-2010/cc511507(v=office.14)?redirectedfrom=MSDN#Anchor_3
    hostname = app.config['HOSTNAME']
    xml = f'''<?xml version=\"1.0\" encoding=\"utf-8\" ?>
<Autodiscover xmlns=\"https://schemas.microsoft.com/exchange/autodiscover/responseschema/2006\">
<Response xmlns=\"https://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a\">
<Account>
<AccountType>email</AccountType>
<Action>settings</Action>
<Protocol>
<Type>IMAP</Type>
<Server>{hostname}</Server>
<Port>993</Port>
<DomainRequired>on</DomainRequired>
<SPA>off</SPA>
<SSL>on</SSL>
<AuthRequired>on</AuthRequired>
</Protocol>
<Protocol>
<Type>SMTP</Type>
<Server>{hostname}</Server>
<Port>465</Port>
<DomainRequired>on</DomainRequired>
<SPA>off</SPA>
<SSL>on</SSL>
<AuthRequired>on</AuthRequired>
</Protocol>
</Account>
</Response>
</Autodiscover>\r\n'''
    return flask.Response(xml, mimetype='text/xml', status=200)
