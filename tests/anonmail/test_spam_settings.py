import pytest

from mailu import models, spam_settings


def test_spam_settings_defaults_are_seeded_and_served_as_maps(app):
    with app.app_context():
        models.db.session.add_all([
            models.Domain(name='example.net'),
            models.Domain(name='mail.example.org'),
        ])
        models.db.session.commit()
        assert spam_settings.map_content('arc-signers').splitlines() == [
            'google.com', 'microsoft.com', 'yahoo.com', 'mailgun.org',
            'mailchannels.net', 'dkim.mimecast.com', 'checkpointcloudsec.com',
            'pphosted.com', 'sendgrid.net', 'amazonses.com',
        ]
        assert spam_settings.map_content('redirector-domains').splitlines() == [
            'example.net', 'mail.example.org',
        ]
        assert spam_settings.map_content('greylist-domains') == '\n'
        assert spam_settings.map_content('unknown') is None


def test_spam_settings_save_and_maps_normalize_entries(app):
    with app.app_context():
        settings = spam_settings.get_settings()
        settings['greylist_domains'] = 'example.org\r\n# comment\r\nmail.example.net\r\n'
        spam_settings.save_settings(settings)

        assert spam_settings.map_content('greylist-domains') == 'example.org\nmail.example.net\n'
        assert spam_settings.get_settings()['arc_signers'] == spam_settings.MAP_DEFAULTS['arc_signers']


def test_legacy_spam_settings_seed_new_defaults_once(app):
    with app.app_context():
        models.db.session.add(models.Domain(name='example.net'))
        models.db.session.add(models.Config(
            name=spam_settings.CONFIG_KEY,
            value={
                'arc_signers': 'google.com\nmicrosoft.com\nyahoo.com',
                'redirector_domains': '',
            },
        ))
        models.db.session.commit()

        settings = spam_settings.get_settings()
        assert settings['arc_signers'].splitlines()[-1] == 'amazonses.com'
        assert settings['redirector_domains'] == 'example.net'

        spam_settings.save_settings(settings)
        settings['redirector_domains'] = ''
        spam_settings.save_settings(settings)
        assert spam_settings.get_settings()['redirector_domains'] == ''


@pytest.mark.parametrize('value', ['a' * 2049, 'valid.example\x01bad'])
def test_spam_settings_reject_invalid_map_entries(value):
    with pytest.raises(ValueError):
        spam_settings.normalize_lines(value)


def test_domain_admin_can_open_shared_spam_settings_page(app):
    with app.app_context():
        domain = models.Domain(name='example.net')
        admin = models.User(localpart='manager', domain_name='example.net')
        admin.set_password('test-password')
        domain.managers.append(admin)
        models.db.session.add_all([domain, admin])
        models.db.session.commit()
        email = admin.email

    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = email
        session['_fresh'] = True
    response = client.get('/admin/spam/settings')
    assert response.status_code == 200
    assert b'google.com' in response.data
    assert b'URL redirectors' in response.data
    assert b'composer.css' in response.data
