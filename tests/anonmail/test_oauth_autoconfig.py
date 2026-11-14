from xml.etree import ElementTree as ET


def test_oauth_autoconfig_publishes_mailu_issuer_and_password_fallback(app, client):
    app.config.update(
        HOSTNAME='mail.example.org',
        HOSTNAMES='mail.example.org,alias.example.org',
        OAUTH2_ISSUER='https://mail.example.org',
        OAUTH2_AUTH_URL='https://mail.example.org/admin/oauth2/authorize',
        OAUTH2_TOKEN_URL='https://mail.example.org/admin/oauth2/token',
        OAUTH2_CLIENT_ID='mailu',
        OAUTH2_SCOPE='imap smtp offline_access',
    )

    response = client.get('/internal/autoconfig/client', base_url='https://alias.example.org')
    root = ET.fromstring(response.get_data(as_text=True))

    assert root.attrib['version'] == '1.2'
    provider = root.find('emailProvider')
    assert provider.find('incomingServer/authentication').text == 'OAuth2'
    assert provider.find('incomingServer/authentication[2]').text == 'password-cleartext'
    assert provider.find('outgoingServer/authentication').text == 'OAuth2'
    oauth2 = root.find('oAuth2')
    assert provider.findtext('incomingServer/hostname') == 'alias.example.org'
    assert oauth2.findtext('issuer') == 'https://alias.example.org'
    assert oauth2.findtext('authURL') == 'https://alias.example.org/admin/oauth2/authorize'
    assert oauth2.findtext('tokenURL') == 'https://alias.example.org/admin/oauth2/token'
    assert oauth2.findtext('clientID') == 'mailu'
    assert oauth2.findtext('scope') == 'imap smtp offline_access'


def test_legacy_autoconfig_prefers_oauth_with_password_fallback(client):
    response = client.get('/internal/autoconfig/mozilla')
    root = ET.fromstring(response.get_data(as_text=True))

    assert root.attrib['version'] == '1.1'
    assert [item.text for item in root.findall('.//emailProvider//authentication')] == [
        'OAuth2', 'password-cleartext', 'OAuth2', 'password-cleartext',
    ]
    assert root.find('oAuth2') is None
