from xml.etree import ElementTree as ET

from mailu.models import Domain


def test_webdav_dns_discovery_records(app):
    app.config.update(
        HOSTNAME='mail.example.org',
        PORTS='443',
        TLS_FLAVOR='letsencrypt',
        WEBDAV='radicale',
    )
    records = Domain(name='example.org').dns_autoconfig

    assert '_carddavs._tcp.example.org. 600 IN SRV 10 1 443 mail.example.org.' in records
    assert '_caldavs._tcp.example.org. 600 IN SRV 10 1 443 mail.example.org.' in records
    assert '_carddavs._tcp.example.org. 600 IN TXT "path=/webdav/"' in records
    assert '_caldavs._tcp.example.org. 600 IN TXT "path=/webdav/"' in records
    assert not any('_carddav._tcp.' in record or '_caldav._tcp.' in record for record in records)

    app.config.update(PORTS='80', TLS_FLAVOR='notls')
    records = Domain(name='example.org').dns_autoconfig
    assert '_carddav._tcp.example.org. 600 IN SRV 10 1 80 mail.example.org.' in records
    assert '_caldav._tcp.example.org. 600 IN SRV 10 1 80 mail.example.org.' in records
    assert not any('_carddavs._tcp.' in record or '_caldavs._tcp.' in record for record in records)

    app.config['WEBDAV'] = 'none'
    records = Domain(name='example.org').dns_autoconfig
    assert not any('carddav' in record or 'caldav' in record for record in records)


def test_webdav_autoconfig_is_conditional_and_valid_xml(app, client):
    app.config.update(
        HOSTNAME='mail.example.org',
        SITENAME='Mailu',
        WEBDAV='radicale',
        TLS_FLAVOR='notls',
    )

    mozilla = client.get('/internal/autoconfig/mozilla').get_data(as_text=True)
    assert '<addressBook type="carddav">' in mozilla
    assert '<calendar type="caldav">' in mozilla
    assert 'http://mail.example.org/webdav/' in mozilla
    ET.fromstring(mozilla)

    autodiscover_request = b'''<?xml version="1.0"?>
<Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/outlook/requestschema/2006">
  <Request>
    <EMailAddress>user@example.org</EMailAddress>
    <AcceptableResponseSchema>http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a</AcceptableResponseSchema>
  </Request>
</Autodiscover>'''
    microsoft = client.post('/internal/autoconfig/microsoft', data=autodiscover_request).get_data(as_text=True)
    assert '<Type>DAV</Type>' in microsoft
    assert '<Server>http://mail.example.org/webdav/</Server>' in microsoft
    ET.fromstring(microsoft)

    apple = client.get('/internal/autoconfig/apple').get_data(as_text=True)
    assert '<string>com.apple.carddav.account</string>' in apple
    assert '<string>com.apple.caldav.account</string>' in apple
    assert '<string>http://mail.example.org/webdav/</string>' in apple
    ET.fromstring(apple)

    app.config['WEBDAV'] = 'none'
    disabled = client.get('/internal/autoconfig/mozilla').get_data(as_text=True)
    assert '<addressBook' not in disabled
    assert '<calendar' not in disabled
