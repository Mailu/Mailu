import json
import os
import base64
import io

from mailu import models, quarantine
from mailu.ui.views.quarantine import _release_recipients, _symbols, _visible, _visible_recipients


def test_quarantine_store_reads_and_deletes_message(app, tmp_path, monkeypatch):
    monkeypatch.setattr(quarantine, 'directory', lambda: tmp_path)
    app.config['QUARANTINE_RETENTION_DAYS'] = 90
    metadata = {'recipients': ['user@example.com'], 'score': 17.5, 'symbols': [{'name': 'TEST', 'score': 2.0}]}

    with app.app_context():
        message_id = quarantine.store(b'Subject: test\r\n\r\nbody', metadata)
        loaded = quarantine.get(message_id)
        assert loaded is not None
        assert loaded[0]['score'] == 17.5
        assert loaded[0]['size'] == len(b'Subject: test\r\n\r\nbody')
        assert loaded[0]['id'] == message_id
        assert loaded[1].read_bytes() == b'Subject: test\r\n\r\nbody'
        assert quarantine.get('../../etc/passwd') is None
        assert quarantine.delete(message_id)
        assert quarantine.get(message_id) is None


def test_quarantine_expiry_removes_message_and_metadata(app, tmp_path, monkeypatch):
    monkeypatch.setattr(quarantine, 'directory', lambda: tmp_path)
    app.config['QUARANTINE_RETENTION_DAYS'] = 90
    with app.app_context():
        message_id = quarantine.store(b'raw', {'recipients': ['user@example.com']})
        for path in (tmp_path / f'{message_id}.eml', tmp_path / f'{message_id}.json'):
            os.utime(path, (0, 0))
        assert quarantine.entries() == []
        assert not (tmp_path / f'{message_id}.eml').exists()
        assert not (tmp_path / f'{message_id}.json').exists()


def test_quarantine_flush_only_removes_requested_messages(app, tmp_path, monkeypatch):
    monkeypatch.setattr(quarantine, 'directory', lambda: tmp_path)
    with app.app_context():
        visible_id = quarantine.store(b'Subject: visible\r\n\r\nbody',
                                      {'recipients': ['user@example.com']})
        other_id = quarantine.store(b'Subject: other\r\n\r\nbody',
                                    {'recipients': ['other@example.net']})
        (tmp_path / 'orphan.json').write_text('{}', encoding='utf-8')
        (tmp_path / 'orphan.eml').write_bytes(b'raw')
        assert quarantine.flush([visible_id]) == 1
        assert quarantine.get(visible_id) is None
        assert quarantine.get(other_id) is not None
        assert (tmp_path / 'orphan.json').exists()
        assert (tmp_path / 'orphan.eml').exists()


def test_quarantine_learn_ham_uses_same_rspamd_commands_as_sieve(app, monkeypatch):
    calls = []

    class Response:
        def raise_for_status(self):
            pass

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(quarantine.requests, 'post', post)
    app.config['ANTISPAM_ADDRESS'] = 'antispam.test'
    with app.app_context():
        assert quarantine.learn_ham(b'Subject: ham\r\n\r\nbody') == []
    assert [call[0] for call in calls] == [
        'http://antispam.test:11334/learnham',
        'http://antispam.test:11334/fuzzydel',
        'http://antispam.test:11334/fuzzyadd',
    ]
    assert calls[0][1]['headers']['Password'] == 'mailu'
    assert calls[1][1]['headers']['Flag'] == '11'
    assert calls[2][1]['headers']['Flag'] == '13'
    assert all(call[1]['data'] == b'Subject: ham\r\n\r\nbody' for call in calls)


def test_quarantine_learn_ham_reports_failed_command_and_reason(app, monkeypatch):
    class Response:
        status_code = 403

        def raise_for_status(self):
            raise quarantine.requests.HTTPError(response=self)

    monkeypatch.setattr(quarantine.requests, 'post', lambda *args, **kwargs: Response())
    with app.app_context():
        assert quarantine.learn_ham(b'message') == [
            'learnham: HTTP 403', 'fuzzydel: HTTP 403', 'fuzzyadd: HTTP 403'
        ]


def test_expired_message_cannot_be_opened(app, tmp_path, monkeypatch):
    monkeypatch.setattr(quarantine, 'directory', lambda: tmp_path)
    app.config['QUARANTINE_RETENTION_DAYS'] = 90
    with app.app_context():
        message_id = quarantine.store(b'raw', {'recipients': ['user@example.com']})
        os.utime(tmp_path / f'{message_id}.json', (0, 0))
        assert quarantine.get(message_id) is None


def test_quarantine_visibility_is_scoped():
    recipient = type('Recipient', (), {'global_admin': False, 'email': 'user@example.com', 'manager_of': []})()
    admin = type('Admin', (), {'global_admin': True, 'email': 'admin@example.com', 'manager_of': []})()
    metadata = {'recipients': ['user@example.com']}
    assert _visible(metadata, recipient)
    assert not _visible(metadata, type('Other', (), {'global_admin': False, 'email': 'other@example.com', 'manager_of': []})())
    assert _visible(metadata, admin)


def test_quarantine_release_recipients_are_scoped():
    manager = type('Manager', (), {
        'global_admin': False, 'email': 'manager@example.com',
        'manager_of': [object()],
        'get_managed_domains': lambda self: [type('Domain', (), {'name': 'example.com'})()],
    })()
    metadata = {'recipients': ['user@example.com', 'outside.test', 'manager@example.com']}
    assert _visible_recipients(metadata, manager) == ['user@example.com', 'manager@example.com']
    assert _release_recipients(metadata, manager) == [
        'user@example.com', 'manager@example.com'
    ]


def test_quarantine_release_always_offers_logged_in_user_once():
    user = type('User', (), {
        'global_admin': True, 'email': 'admin@example.com', 'manager_of': [],
    })()
    assert _release_recipients({'recipients': ['user@example.com']}, user) == [
        'user@example.com', 'admin@example.com'
    ]
    assert _release_recipients({'recipients': ['ADMIN@example.com']}, user) == [
        'ADMIN@example.com'
    ]


def test_global_admin_release_preserves_original_envelope_recipients():
    admin = type('Admin', (), {
        'global_admin': True, 'email': 'admin@example.com', 'manager_of': [],
    })()
    metadata = {
        'recipients': ['mailbox@example.com'],
        'envelope_recipients': ['alias@relay.example.net'],
    }
    assert _release_recipients(metadata, admin) == [
        'alias@relay.example.net', 'admin@example.com',
    ]


def test_quarantine_symbols_are_presented_as_named_scores_and_options():
    assert _symbols([
        {'name': 'BAYES_SPAM', 'score': 3.2, 'options': ['high']},
        {'name': 'NEGATIVE_SCORE', 'score': -4.5},
        'MISSING_HEADERS',
        {'unexpected': 'ignored'},
    ]) == [
        {'name': 'NEGATIVE_SCORE', 'score': -4.5, 'options': []},
        {'name': 'BAYES_SPAM', 'score': 3.2, 'options': ['high']},
        {'name': 'MISSING_HEADERS', 'score': None, 'options': []},
    ]


def test_quarantine_list_and_release_use_message_uuid(app, client, tmp_path, monkeypatch):
    monkeypatch.setattr(quarantine, 'directory', lambda: tmp_path)
    app.config['WTF_CSRF_ENABLED'] = False
    app.config.setdefault('SMTP_ADDRESS', 'smtp')
    with app.app_context():
        domain = models.Domain(name='example.com')
        models.db.session.add(domain)
        models.db.session.commit()
        admin = models.User(localpart='admin', domain_name='example.com', global_admin=True)
        admin.set_password('password')
        models.db.session.add(admin)
        models.db.session.commit()
        message_id = quarantine.store(
            b'Subject: test\r\n\r\nbody',
            {'recipients': [admin.email], 'subject': 'test', 'score': 12.0,
             'from': 'sender@example.net'},
        )
        delete_id = quarantine.store(b'Subject: delete\r\n\r\nbody',
                                     {'recipients': [admin.email], 'subject': 'delete'})
        with client.session_transaction() as session:
            session['_user_id'] = admin.get_id()
            session['_fresh'] = True

        prefix = app.config['WEB_ADMIN']
        listing = client.get(f'{prefix}/quarantine')
        assert listing.status_code == 200
        assert f'{prefix}/quarantine/{message_id}/release'.encode() in listing.data
        assert f'{prefix}/quarantine/{delete_id}/delete'.encode() in listing.data
        assert b'View' in listing.data and b'Release' in listing.data and b'Delete' in listing.data
        assert b'Flush all' in listing.data
        assert b'Flush visible' not in listing.data
        assert b'data-order="21"' in listing.data
        delete_url = f'{prefix}/quarantine/{delete_id}/delete'
        assert client.get(delete_url).status_code == 200
        assert client.post(delete_url, data={'submit': 'Delete permanently'}).status_code == 302
        assert quarantine.get(delete_id) is None
        release_url = f'{prefix}/quarantine/{message_id}/release'
        page = client.get(release_url)
        assert page.status_code == 200
        assert b'name="recipients"' in page.data

        deliveries = []
        learned = []
        monkeypatch.setattr(quarantine, 'learn_ham', lambda raw: learned.append(raw) or [])

        class FakeSMTP:
            def __init__(self, **kwargs):
                smtp_options.append(kwargs)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def sendmail(self, sender, recipients, message):
                deliveries.append((sender, recipients, message))
                return {}

        smtp_options = []
        monkeypatch.setattr('mailu.ui.views.quarantine.smtplib.SMTP', FakeSMTP)
        response = client.post(release_url, data={'recipients': admin.email, 'submit': 'Release'})
        assert response.status_code == 302
        assert smtp_options == [{
            'host': app.config.get('SMTP_ADDRESS', 'smtp'), 'port': 10026, 'timeout': 10,
        }]
        assert deliveries == [('sender@example.net',
                               [admin.email], b'Subject: test\r\n\r\nbody')]
        assert learned == [b'Subject: test\r\n\r\nbody']
        assert quarantine.get(message_id) is None

        failed_learn_id = quarantine.store(
            b'Subject: training error\r\n\r\nbody',
            {'recipients': [admin.email], 'subject': 'training error'},
        )
        monkeypatch.setattr(quarantine, 'learn_ham', lambda raw: ['learnham: HTTP 503'])
        failed_learn_response = client.post(
            f'{prefix}/quarantine/{failed_learn_id}/release',
            data={'recipients': admin.email, 'submit': 'Release'},
        )
        assert failed_learn_response.status_code == 302
        assert quarantine.get(failed_learn_id) is None
        assert b'learnham: HTTP 503' in client.get(failed_learn_response.location).data
        assert len(deliveries) == 2

        flush_id = quarantine.store(b'Subject: flush\r\n\r\nbody',
                                    {'recipients': [admin.email], 'subject': 'flush'})
        flush_url = f'{prefix}/quarantine/flush'
        assert client.get(flush_url).status_code == 200
        assert client.post(flush_url, data={'submit': 'Delete permanently'}).status_code == 302
        assert quarantine.get(flush_id) is None


def test_quarantine_release_reinjects_external_recipient(app, client, tmp_path, monkeypatch):
    monkeypatch.setattr(quarantine, 'directory', lambda: tmp_path)
    app.config['WTF_CSRF_ENABLED'] = False
    app.config.setdefault('SMTP_ADDRESS', 'smtp')
    relay_recipient = 'recipient@relay.example.net'
    with app.app_context():
        domain = models.Domain(name='example.com')
        models.db.session.add(domain)
        admin = models.User(localpart='admin', domain_name='example.com', global_admin=True)
        admin.set_password('password')
        models.db.session.add_all([admin, models.Relay(name='relay.example.net', smtp='smtp:25')])
        models.db.session.commit()
        message_id = quarantine.store(
            b'Subject: relayed message\r\n\r\nbody',
            {
                'recipients': [relay_recipient],
                'envelope_recipients': [relay_recipient],
                'from': 'sender@example.net',
                'subject': 'relayed message',
            },
        )
        with client.session_transaction() as session:
            session['_user_id'] = admin.get_id()
            session['_fresh'] = True

    page = client.get(f"{app.config['WEB_ADMIN']}/quarantine/{message_id}/release")
    assert page.status_code == 200
    assert relay_recipient.encode() in page.data

    events = []
    monkeypatch.setattr(quarantine, 'learn_ham', lambda raw: events.append(('learn', raw)) or [])

    class FakeSMTP:
        def __init__(self, **kwargs):
            events.append(('connect', kwargs))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def sendmail(self, sender, recipients, message):
            events.append(('send', sender, recipients, message))
            return {}

    monkeypatch.setattr('mailu.ui.views.quarantine.smtplib.SMTP', FakeSMTP)
    response = client.post(
        f"{app.config['WEB_ADMIN']}/quarantine/{message_id}/release",
        data={'recipients': relay_recipient, 'submit': 'Release'},
    )

    assert response.status_code == 302
    assert events == [
        ('learn', b'Subject: relayed message\r\n\r\nbody'),
        ('connect', {
            'host': app.config.get('SMTP_ADDRESS', 'smtp'), 'port': 10026, 'timeout': 10,
        }),
        ('send', 'sender@example.net', [relay_recipient],
         b'Subject: relayed message\r\n\r\nbody'),
    ]
    assert quarantine.get(message_id) is None


def test_quarantine_flush_only_deletes_messages_visible_to_user(app, client, tmp_path, monkeypatch):
    monkeypatch.setattr(quarantine, 'directory', lambda: tmp_path)
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        models.db.session.add_all([
            models.Domain(name='example.com'),
            models.Domain(name='other.example'),
        ])
        models.db.session.commit()
        user = models.User(localpart='user', domain_name='example.com')
        user.set_password('password')
        models.db.session.add(user)
        models.db.session.commit()
        own_id = quarantine.store(b'Subject: own\r\n\r\nbody',
                                  {'recipients': [user.email], 'subject': 'own'})
        other_id = quarantine.store(b'Subject: other\r\n\r\nbody',
                                    {'recipients': ['other@other.example'], 'subject': 'other'})
        with client.session_transaction() as session:
            session['_user_id'] = user.get_id()
            session['_fresh'] = True

        prefix = app.config['WEB_ADMIN']
        flush_url = f'{prefix}/quarantine/flush'
        assert client.get(flush_url).status_code == 200
        assert client.post(flush_url, data={'submit': 'Delete permanently'}).status_code == 302
        assert quarantine.get(own_id) is None
        assert quarantine.get(other_id) is not None


def test_quarantine_preview_is_inert_text(app, tmp_path):
    message_path = tmp_path / 'message.eml'
    message_path.write_bytes(b'Content-Type: text/html; charset=utf-8\r\n\r\n<script>alert(1)</script>')
    with app.app_context():
        preview = quarantine.safe_preview(message_path)
        rendered = app.jinja_env.from_string('{{ body }}').render(body=preview)
    assert '<script>' in preview
    assert '&lt;script&gt;' in rendered


def test_internal_capture_requires_secret_and_stores_multipart(client, app, tmp_path, monkeypatch):
    monkeypatch.setattr(quarantine, 'directory', lambda: tmp_path)
    def payload():
        return {'metadata': json.dumps({'action': 'reject', 'rcpt': ['user@example.com'], 'score': 18.0, 'symbols': []}),
                'message': (io.BytesIO(b'Subject: held\r\n\r\nbody'), 'message.eml')}
    denied = client.post('/internal/rspamd/quarantine', data=payload(), content_type='multipart/form-data')
    assert denied.status_code == 403

    app.config['QUARANTINE_KEY'] = 'test-quarantine-key'
    accepted = client.post('/internal/rspamd/quarantine', data=payload(), content_type='multipart/form-data',
                           headers={'Authorization': 'Basic ' + base64.b64encode(
                               b'quarantine:test-quarantine-key'
                           ).decode()})
    assert accepted.status_code == 201
    record = quarantine.get(accepted.json['id'])
    assert record[1].read_bytes() == b'Subject: held\r\n\r\nbody'
    assert record[0]['recipients'] == ['user@example.com']
