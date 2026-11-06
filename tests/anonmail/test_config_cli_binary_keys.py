"""Config CLI round-trips binary credentials through a text representation."""

import base64
import json

from mailu import models, oauth2, spam_settings


def test_config_export_includes_effective_spam_defaults_without_saved_row(app):
    with app.app_context():
        exported = app.test_cli_runner().invoke(
            args=['mailu', 'config-export', '--json'],
        )

        assert exported.exit_code == 0, exported.output
        data = json.loads(exported.output)
        spam_config = next(
            item['value'] for item in data['config']
            if item['name'] == spam_settings.CONFIG_KEY
        )
        assert spam_config['greylist_ips'] == spam_settings.MAP_DEFAULTS[
            'greylist_ips']
        assert spam_config['summary_enabled'] is True
        assert spam_config['summary_periodicity'] == '1w'


def test_config_cli_round_trips_binary_keys_and_durable_oauth_state(app):
    with app.app_context():
        domain = models.Domain(name='example.com')
        domain.generate_dkim_key(algorithm='ed25519', active=True)
        domain.generate_dkim_key(algorithm='ed25519', active=False)
        user = models.User(localpart='alice', domain_name='example.com')
        user.set_password('test-password')
        token = models.Token(comment='CLI round-trip')
        token.set_password('test-token')
        user.tokens.append(token)
        user.passkeys.append(models.Passkey(
            credential_id=b'credential\x00id',
            public_key=b'public\x00key\xff',
            aaguid='00000000-0000-0000-0000-000000000000',
            name='Test key',
        ))
        user.oauth2_grants.append(models.OAuth2Grant(
            grant_id='abcdefghijklmnopqrstuv',
            client_id='mailu-native-client',
            scope='imap pop3 smtp',
            token_generation=3,
            access_expires_at=2_000_000_000,
            refresh_expires_at=2_100_000_000,
            client_name='Mail client',
            last_refresh_at=1_900_000_000,
        ))
        signing_key_hex = 'ab' * 32
        spam_config = {
            **spam_settings.DEFAULTS,
            'greylist_ips': '192.0.2.1\n2001:db8::1',
            'blacklist_domains': 'bad.example',
            'summary_enabled': False,
            'summary_periodicity': '1d',
            'summary_subject': 'Your quarantine digest',
            '_defaults_version': spam_settings.SETTINGS_VERSION,
        }
        models.db.session.add_all([
            domain,
            user,
            models.Config(name='oauth2_signing_key', value=signing_key_hex),
            models.Config(name=spam_settings.CONFIG_KEY, value=spam_config),
        ])
        models.db.session.commit()
        oauth2_key_before = oauth2._oauth2_signing_key()
        expected_dkim_keys = {key.private_key for key in domain.dkim_keys}

        runner = app.test_cli_runner()
        exported = runner.invoke(
            args=['mailu', 'config-export', '--json', '--secrets'],
        )

        assert exported.exit_code == 0, exported.output
        data = json.loads(exported.output)
        passkey_data = data['user'][0]['passkeys'][0]
        grant_data = data['user'][0]['oauth2_grants'][0]
        assert 'oauth2_authorization_codes' not in data['user'][0]
        assert data['user'][0]['tokens'][0]['user_email'] == 'alice@example.com'
        assert passkey_data['credential_id'] == base64.b64encode(
            b'credential\x00id').decode('ascii')
        assert passkey_data['public_key'] == base64.b64encode(
            b'public\x00key\xff').decode('ascii')
        assert grant_data == {
            'grant_id': 'abcdefghijklmnopqrstuv',
            'user_email': 'alice@example.com',
            'client_id': 'mailu-native-client',
            'token_generation': 3,
            'scope': 'imap pop3 smtp',
            'access_expires_at': 2_000_000_000,
            'refresh_expires_at': 2_100_000_000,
            'client_name': 'Mail client',
            'last_refresh_at': 1_900_000_000,
        }
        dkim_keys = data['domain'][0]['dkim_keys']
        assert len(dkim_keys) == 2
        assert {item['private_key'] for item in dkim_keys} == {
            base64.b64encode(key).decode('ascii') for key in expected_dkim_keys
        }
        config_data = {item['name']: item['value'] for item in data['config']}
        assert config_data['oauth2_signing_key'] == base64.b64encode(
            bytes.fromhex(signing_key_hex)).decode('ascii')
        assert config_data[spam_settings.CONFIG_KEY] == spam_config

        # Ensure the import restores the exported key rather than merely
        # leaving the current database value untouched.
        models.db.session.get(models.Config, 'oauth2_signing_key').value = 'cd' * 32
        models.db.session.get(models.Config, spam_settings.CONFIG_KEY).value = {
            'greylist_ips': '198.51.100.10',
        }
        models.db.session.commit()
        del app.oauth2_signing_key

        imported = runner.invoke(
            args=['mailu', 'config-import', '--secrets', '-'],
            input=exported.output,
        )
        assert imported.exit_code == 0, imported.output

        restored = models.db.session.get(models.User, 'alice@example.com')
        assert len(restored.passkeys) == 1
        assert restored.passkeys[0].credential_id == b'credential\x00id'
        assert restored.passkeys[0].public_key == b'public\x00key\xff'
        restored_grant = restored.oauth2_grants[0]
        assert restored_grant.grant_id == 'abcdefghijklmnopqrstuv'
        assert restored_grant.token_generation == 3
        assert restored_grant.scope == 'imap pop3 smtp'
        assert restored_grant.client_id == 'mailu-native-client'
        restored_domain = models.db.session.get(models.Domain, 'example.com')
        assert {key.private_key for key in restored_domain.dkim_keys} == {
            key for key in expected_dkim_keys
        }
        assert models.db.session.get(models.Config, 'oauth2_signing_key').value == signing_key_hex
        assert models.db.session.get(models.Config, spam_settings.CONFIG_KEY).value == spam_config
        assert oauth2._oauth2_signing_key() == oauth2_key_before
