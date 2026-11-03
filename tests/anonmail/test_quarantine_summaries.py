from datetime import datetime, timedelta, timezone
from uuid import uuid4

from mailu import models, quarantine, spam_settings


def _create_mailbox(domain_name, localpart):
    domain = models.db.session.get(models.Domain, domain_name)
    if domain is None:
        domain = models.Domain(name=domain_name)
        models.db.session.add(domain)
    mailbox = models.User(localpart=localpart, domain_name=domain_name)
    mailbox.set_password('test-password')
    models.db.session.add(mailbox)
    models.db.session.commit()
    return mailbox


def test_summary_renders_escaped_mailbox_scoped_rows_and_links(app):
    with app.app_context():
        app.config['HOSTNAMES'] = 'mail.example.net'
        user = type('Mailbox', (), {'email': 'alice@example.net'})()
        settings = spam_settings.get_settings()
        now = datetime.now(timezone.utc)
        message_id = str(uuid4())
        entries = [{
            'id': message_id,
            'received': (now - timedelta(hours=1)).isoformat(),
            'from': '<img src=x onerror=alert(1)>@bad.example',
            'subject': '<script>alert(1)</script>',
            'score': 17.5,
            'recipients': ['alice@example.net'],
        }, {
            'id': str(uuid4()),
            'received': (now - timedelta(hours=1)).isoformat(),
            'subject': 'Other mailbox only',
            'recipients': ['bob@example.net'],
        }]

        subject, plain, html_body = quarantine.render_summary(settings, user, entries, now=now)

    assert subject == 'Quarantine summary for alice@example.net'
    assert 'alice@example.net' in plain
    assert f'/admin/quarantine/{message_id}' in html_body
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in html_body
    assert '<script>alert(1)</script>' not in html_body
    assert 'Other mailbox only' not in html_body


def test_summary_table_placeholder_replaces_editor_paragraph(app):
    with app.app_context():
        app.config['HOSTNAMES'] = 'mail.example.net'
        user = type('Mailbox', (), {'email': 'alice@example.net'})()
        settings = spam_settings.get_settings()
        settings['summary_template'] = (
            '<p>Before</p><p>{{ quarantine_table }}</p><p>After</p>'
        )
        _, _, html_body = quarantine.render_summary(settings, user, [])

    assert '<p>{{ quarantine_table }}</p>' not in html_body
    assert '<p>Before</p><table ' in html_body
    assert '</table><p>After</p>' in html_body


def test_summary_restores_editor_encoded_url_placeholder(app):
    with app.app_context():
        app.config['HOSTNAMES'] = 'mail.example.net'
        user = type('Mailbox', (), {'email': 'alice@example.net'})()
        settings = spam_settings.get_settings()
        settings['summary_template'] = (
            '<p><a href="http://%7B%7B%20quarantine_url%20%7D%7D">Open quarantine</a></p>'
            '<p>{{  quarantine_table  }}</p>'
        )
        _, _, html_body = quarantine.render_summary(settings, user, [])

    assert 'href="https://mail.example.net/admin/quarantine"' in html_body
    assert '{{ quarantine_url }}' not in html_body
    assert '{{ quarantine_table }}' not in html_body


def test_summary_settings_normalize_editor_changes_inside_table_token(app):
    with app.app_context():
        settings = spam_settings.get_settings()
        settings['summary_template'] = '<p>{{ quarantine_<strong>table</strong> }}</p>'
        normalized = spam_settings.normalize_settings(settings)

    assert normalized['summary_template'] == '<p>{{ quarantine_table }}</p>'


def test_summary_settings_normalize_html_escaped_table_token(app):
    with app.app_context():
        settings = spam_settings.get_settings()
        settings['summary_template'] = '<p>&#123;&#123; quarantine_table &#125;&#125;</p>'
        normalized = spam_settings.normalize_settings(settings)

    assert normalized['summary_template'] == '<p>{{ quarantine_table }}</p>'


def test_due_summaries_send_only_to_matching_mailboxes_once(app, monkeypatch):
    with app.app_context():
        alice = _create_mailbox('example.net', 'alice')
        bob = _create_mailbox('example.net', 'bob')
        settings = spam_settings.get_settings()
        settings.update(summary_enabled=True, summary_periodicity='1w')
        spam_settings.save_settings(settings)

        received = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        entries = [
            {'id': str(uuid4()), 'received': received, 'subject': 'Alice message',
             'recipients': [alice.email]},
            {'id': str(uuid4()), 'received': received, 'subject': 'Bob message',
             'recipients': [bob.email]},
        ]
        monkeypatch.setattr(quarantine, 'entries', lambda: entries)
        sent = []

        def sendmail(user, subject, body, *, html_body=None):
            sent.append((user.email, subject, body, html_body))
            return True

        monkeypatch.setattr(models.User, 'sendmail', sendmail)

        assert quarantine.send_due_summaries() == 2
        assert {email for email, *_ in sent} == {alice.email, bob.email}
        assert 'Alice message' in next(body for email, _, body, _ in sent if email == alice.email)
        assert 'Bob message' not in next(body for email, _, body, _ in sent if email == alice.email)
        assert quarantine.send_due_summaries() == 0


def test_send_test_button_sends_unsaved_template_to_signed_in_admin(app, monkeypatch):
    with app.app_context():
        admin = _create_mailbox('example.net', 'admin')
        florent = _create_mailbox('daigniere.com', 'florent')
        florent_email = florent.email
        admin.global_admin = True
        models.db.session.commit()
        email = admin.email
        app.config['WTF_CSRF_ENABLED'] = False
        now = datetime.now(timezone.utc)
        monkeypatch.setattr(quarantine, 'entries', lambda: [{
            'id': str(uuid4()), 'received': (now - timedelta(hours=1)).isoformat(),
            'subject': 'Test row', 'recipients': [email],
        }, {
            'id': str(uuid4()), 'received': (now - timedelta(hours=2)).isoformat(),
            'subject': 'Florent row', 'recipients': [florent_email],
        }])
        sent = []
        monkeypatch.setattr(models.User, 'sendmail',
                            lambda user, subject, body, *, html_body=None:
                            sent.append((user.email, subject, body, html_body)) or True)

    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = email
        session['_fresh'] = True
    data = dict(spam_settings.MAP_DEFAULTS)
    data.update({
        'summary_enabled': 'y',
        'summary_periodicity': '1d',
        'summary_subject': 'Custom {{ mailbox }}',
        'summary_template': '<p>Preview for {{ mailbox }}</p>{{ quarantine_table }}',
        'send_test': 'Send me a test',
    })
    response = client.post('/admin/spam/settings', data=data)
    assert response.status_code == 200
    assert len(sent) == 1
    assert sent[0][0] == email
    assert sent[0][1] == f'[TEST] Custom {email}'
    assert 'Test row' in sent[0][3]
    assert 'Florent row' in sent[0][3]
    assert florent_email in sent[0][3]


def test_send_test_button_does_not_send_empty_summary(app, monkeypatch):
    with app.app_context():
        admin = _create_mailbox('example.net', 'empty-admin')
        admin.global_admin = True
        models.db.session.commit()
        email = admin.email
        app.config['WTF_CSRF_ENABLED'] = False
        monkeypatch.setattr(quarantine, 'entries', lambda: [])
        sent = []
        monkeypatch.setattr(models.User, 'sendmail',
                            lambda *args, **kwargs: sent.append(args) or True)

    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = email
        session['_fresh'] = True
    data = dict(spam_settings.MAP_DEFAULTS)
    data.update({
        'summary_enabled': 'y',
        'summary_periodicity': '1d',
        'summary_subject': 'Custom {{ mailbox }}',
        'summary_template': '<p>Preview for {{ mailbox }}</p>{{ quarantine_table }}',
        'send_test': 'Send me a test',
    })

    response = client.post('/admin/spam/settings', data=data)

    assert response.status_code == 200
    assert sent == []
    assert b'no test email was sent' in response.data
