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

@internal.route("/autoconfig/apple")
def autoconfig_apple():
    # https://developer.apple.com/business/documentation/Configuration-Profile-Reference.pdf
    hostname = app.config['HOSTNAME']
    sitename = app.config['SITENAME']
    xml = f'''<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\"
\"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">
<plist version=\"1.0\">
<dict>
<key>PayloadContent</key>
<array>
<dict>
<key>EmailAccountDescription</key>
<string>{sitename}</string>
<key>EmailAccountName</key>
<string>{hostname}</string>
<key>EmailAccountType</key>
<string>EmailTypeIMAP</string>
<key>EmailAddress</key>
<string></string>
<key>IncomingMailServerAuthentication</key>
<string>EmailAuthPassword</string>
<key>IncomingMailServerHostName</key>
<string>{hostname}</string>
<key>IncomingMailServerPortNumber</key>
<integer>993</integer>
<key>IncomingMailServerUseSSL</key>
<true/>
<key>IncomingMailServerUsername</key>
<string></string>
<key>IncomingPassword</key>
<string></string>
<key>OutgoingMailServerAuthentication</key>
<string>EmailAuthPassword</string>
<key>OutgoingMailServerHostName</key>
<string>{hostname}</string>
<key>OutgoingMailServerPortNumber</key>
<integer>465</integer>
<key>OutgoingMailServerUseSSL</key>
<true/>
<key>OutgoingMailServerUsername</key>
<string></string>
<key>OutgoingPasswordSameAsIncomingPassword</key>
<true/>
<key>PayloadDescription</key>
<string>{sitename}</string>
<key>PayloadDisplayName</key>
<string>{hostname}</string>
<key>PayloadIdentifier</key>
<string>{hostname}.email</string>
<key>PayloadOrganization</key>
<string></string>
<key>PayloadType</key>
<string>com.apple.mail.managed</string>
<key>PayloadUUID</key>
<string>72e152e2-d285-4588-9741-25bdd50c4d11</string>
<key>PayloadVersion</key>
<integer>1</integer>
<key>PreventAppSheet</key>
<true/>
<key>PreventMove</key>
<false/>
<key>SMIMEEnabled</key>
<false/>
<key>disableMailRecentsSyncing</key>
<false/>
</dict>
</array>
<key>PayloadDescription</key>
<string>{hostname} - E-Mail Account Configuration</string>
<key>PayloadDisplayName</key>
<string>E-Mail Account {hostname}</string>
<key>PayloadIdentifier</key>
<string>E-Mail Account {hostname}</string>
<key>PayloadOrganization</key>
<string>{hostname}</string>
<key>PayloadRemovalDisallowed</key>
<false/>
<key>PayloadType</key>
<string>Configuration</string>
<key>PayloadUUID</key>
<string>56db43a5-d29e-4609-a908-dce94d0be48e</string>
<key>PayloadVersion</key>
<integer>1</integer>
</dict>
</plist>\r\n'''
    return flask.Response(xml, mimetype='text/xml', status=200)