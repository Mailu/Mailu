import io
import json
from datetime import datetime, timezone

from mailu import greylist, models, quarantine


def test_greylisted_message_is_removed_when_retry_passes(app, tmp_path, monkeypatch):
    monkeypatch.setattr(greylist, 'directory', lambda: tmp_path)
    with app.app_context():
        assert greylist.record({
            'message_id': '<retry@example.net>', 'action': 'soft reject',
            'from': 'sender@example.net', 'subject': 'Wait for retry',
            'rcpt': ['user@example.com'], 'score': 5.0,
        })
        [entry] = greylist.entries()
        assert entry['message_id'] == 'retry@example.net'
        assert entry['recipients'] == ['user@example.com']

        assert greylist.record({'message_id': 'retry@example.net', 'action': 'add header'}) is False
        assert greylist.entries() == []


def test_greylist_entries_expire(app, tmp_path, monkeypatch):
    monkeypatch.setattr(greylist, 'directory', lambda: tmp_path)
    with app.app_context():
        greylist.record({'message_id': 'expired@example.net', 'action': 'soft reject'})
        [path] = tmp_path.glob('*.json')
        data = path.read_text(encoding='utf-8').replace(
            datetime.now(timezone.utc).date().isoformat(), '2000-01-01'
        )
        path.write_text(data, encoding='utf-8')
        assert greylist.entries() == []
        assert not path.exists()


def test_greylist_record_rejects_invalid_message_ids(tmp_path, monkeypatch):
    monkeypatch.setattr(greylist, 'directory', lambda: tmp_path)
    assert greylist.record({'message_id': 'bad\x01id', 'action': 'soft reject'}) is None
    assert list(tmp_path.glob('*.json')) == []


def test_greylist_message_copy_is_removed_after_accepted_retry(app, tmp_path, monkeypatch):
    monkeypatch.setattr(greylist, 'directory', lambda: tmp_path)
    with app.app_context():
        metadata = {'message_id': 'retry@example.net', 'action': 'soft reject'}
        assert greylist.record(metadata, b'Subject: retry\r\n\r\nbody')
        [entry] = greylist.entries()
        assert entry['size'] == len(b'Subject: retry\r\n\r\nbody')

        assert greylist.record({**metadata, 'action': 'no action'}) is False
        assert greylist.entries() == []
        assert list(tmp_path.iterdir()) == []


def test_greylist_endpoint_stores_multipart_copy_and_clears_on_delivery(app, tmp_path, monkeypatch):
    monkeypatch.setattr(greylist, 'directory', lambda: tmp_path)
    message = b'Subject: retry\r\nMessage-ID: <retry@example.net>\r\n\r\nbody'
    metadata = {
        'message-id': '<retry@example.net>', 'action': 'soft reject',
        'from': 'sender@example.org', 'rcpt': ['alice@example.net'],
    }
    client = app.test_client()
    auth = ('quarantine', app.config['QUARANTINE_KEY'])
    response = client.post('/internal/rspamd/greylist', auth=auth, data={
        'metadata': json.dumps(metadata), 'message': (io.BytesIO(message), 'message.eml'),
    })
    assert response.status_code == 200
    [entry] = greylist.entries()
    assert entry['kind'] == 'greylist'
    assert (tmp_path / f"{entry['id']}.json").is_file()
    assert greylist.get(entry['id'])[1].read_bytes() == message

    response = client.post('/internal/rspamd/greylist', auth=auth, json={
        **metadata, 'action': 'no action',
    })
    assert response.status_code == 200
    assert greylist.entries() == []
    assert list(tmp_path.iterdir()) == []


def test_accepted_retry_clear_keeps_rejected_messages_and_clears_greylist_only(
        app, tmp_path, monkeypatch):
    monkeypatch.setattr(greylist, 'directory', lambda: tmp_path)
    monkeypatch.setattr(quarantine, 'directory', lambda: tmp_path)
    app.config['WTF_CSRF_ENABLED'] = False
    client = app.test_client()
    auth = ('quarantine', app.config['QUARANTINE_KEY'])
    message = b'Subject: retry\r\n\r\nbody'
    with app.app_context():
        greylist.record({'message_id': 'retry@example.net', 'action': 'soft reject'}, message)
        rejected_id = quarantine.store(message, {'recipients': ['user@example.net']})

    response = client.post('/internal/rspamd/greylist', auth=auth, json={
        'message_id': 'retry@example.net', 'action': 'no action',
    })

    assert response.status_code == 200
    with app.app_context():
        assert greylist.entries() == []
        assert quarantine.get(rejected_id) is not None
        assert len(quarantine.all_entries()) == 1


def test_clear_endpoint_handles_delivery_actions_but_preserves_rejects(app, tmp_path, monkeypatch):
    monkeypatch.setattr(greylist, 'directory', lambda: tmp_path)
    monkeypatch.setattr(quarantine, 'directory', lambda: tmp_path)
    client = app.test_client()
    auth = ('quarantine', app.config['QUARANTINE_KEY'])
    delivery_actions = ('no action', 'accept', 'add header', 'rewrite subject')

    for index, action in enumerate(delivery_actions):
        message_id = f'accepted-{index}@example.net'
        greylist.record({'message_id': message_id, 'action': 'soft reject'},
                        b'Subject: retry\r\n\r\nbody')
        response = client.post('/internal/rspamd/greylist', auth=auth, json={
            'message_id': message_id, 'action': action,
        })
        assert response.status_code == 200
        assert greylist.get(greylist._key(message_id)) is None

    rejected_id = 'rejected@example.net'
    greylist.record({'message_id': rejected_id, 'action': 'soft reject'},
                    b'Subject: retry\r\n\r\nbody')
    response = client.post('/internal/rspamd/greylist', auth=auth, json={
        'message_id': rejected_id, 'action': 'reject',
    })
    assert response.status_code == 200
    assert greylist.get(greylist._key(rejected_id)) is not None


def test_quarantine_endpoint_clears_matching_greylist_copy(app, tmp_path, monkeypatch):
    monkeypatch.setattr(greylist, 'directory', lambda: tmp_path)
    monkeypatch.setattr(quarantine, 'directory', lambda: tmp_path)
    app.config['WTF_CSRF_ENABLED'] = False
    message_id = '<later-quarantined@example.net>'
    message = b'Subject: quarantined\r\nMessage-ID: ' + message_id.encode() + b'\r\n\r\nbody'
    with app.app_context():
        greylist.record({
            'message_id': message_id, 'action': 'soft reject',
            'rcpt': ['user@example.net'],
        }, message)
        [greylist_entry] = greylist.entries()

    client = app.test_client()
    auth = ('quarantine', app.config['QUARANTINE_KEY'])
    response = client.post('/internal/rspamd/quarantine', auth=auth, data={
        'metadata': json.dumps({
            'message_id': message_id, 'action': 'reject',
            'rcpt': ['user@example.net'], 'symbols': [],
        }),
        'message': (io.BytesIO(message), 'message.eml'),
    })

    assert response.status_code == 201
    with app.app_context():
        assert greylist.get(greylist_entry['id']) is None
        [quarantine_entry] = quarantine.all_entries()
        assert quarantine_entry['kind'] == 'quarantine'
        assert quarantine.get(response.json['id']) is not None


def test_quarantine_and_greylist_records_share_one_repository(app, tmp_path, monkeypatch):
    monkeypatch.setattr(greylist, 'directory', lambda: tmp_path)
    monkeypatch.setattr(quarantine, 'directory', lambda: tmp_path)
    with app.app_context():
        assert greylist.directory() == quarantine.directory()
        greylist.record({
            'message_id': 'shared@example.net', 'action': 'soft reject',
            'recipients': ['user@example.net'],
        }, b'Subject: greylist\r\n\r\nbody')
        quarantine_id = quarantine.store(
            b'Subject: quarantine\r\n\r\nbody',
            {'recipients': ['user@example.net']},
        )
        entries = quarantine.all_entries()
        assert {entry['kind'] for entry in entries} == {'greylist', 'quarantine'}
        assert len(list(tmp_path.glob('*.json'))) == 2
        assert len(list(tmp_path.glob('*.eml'))) == 2
        assert quarantine.flush(entry['id'] for entry in entries) == 2
        assert quarantine.all_entries() == []

    assert len(quarantine_id) == 36


def test_domain_admin_sees_greylist_and_can_release_it_on_quarantine_page(app, tmp_path, monkeypatch):
    monkeypatch.setattr(greylist, 'directory', lambda: tmp_path)
    monkeypatch.setattr(quarantine, 'directory', lambda: tmp_path)
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        domain = models.Domain(name='example.net')
        admin = models.User(localpart='manager', domain_name='example.net')
        admin.set_password('test-password')
        recipient = models.User(localpart='user', domain_name='example.net')
        recipient.set_password('test-password')
        domain.managers.append(admin)
        models.db.session.add_all([domain, admin, recipient])
        models.db.session.commit()
        email = admin.email
        greylist.record({
            'message_id': 'untrusted@example.org', 'action': 'soft reject',
            'subject': '<script>alert(1)</script>', 'rcpt': [recipient.email],
        }, b'Subject: greylist\r\n\r\nbody')
        [entry] = greylist.entries()

    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = email
        session['_fresh'] = True
    response = client.get('/admin/quarantine')
    assert response.status_code == 200
    assert b'Flush all' in response.data
    assert b'Flush visible' not in response.data
    assert b'Release now' in response.data
    assert b'class="user-disabled text-body-secondary"' in response.data
    assert b'btn-outline-secondary' in response.data
    assert b'&lt;script&gt;alert(1)&lt;/script&gt;' in response.data
    assert b'<script>alert(1)</script>' not in response.data

    released = []
    monkeypatch.setattr('mailu.ui.views.quarantine.quarantine.learn_ham', lambda raw: [])

    class FakeLMTP:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def sendmail(self, sender, recipients, message):
            released.append((recipients, message))
            return {}

    monkeypatch.setattr('mailu.ui.views.quarantine.smtplib.LMTP', FakeLMTP)
    release_url = f"/admin/quarantine/greylist/{entry['id']}/release"
    assert client.get(release_url).status_code == 200
    result = client.post(release_url, data={'recipients': 'user@example.net', 'submit': 'Release selected'})
    assert result.status_code == 302
    assert released == [(['user@example.net'], b'Subject: greylist\r\n\r\nbody')]
    assert greylist.get(entry['id']) is None

    with app.app_context():
        greylist.record({
            'message_id': 'delete-copy@example.org', 'action': 'soft reject',
            'recipients': [recipient.email], 'subject': 'delete this saved copy',
        }, b'Subject: delete this saved copy\r\n\r\nbody')
        [delete_entry] = greylist.entries()
    delete_url = f"/admin/quarantine/{delete_entry['id']}/delete"
    listing = client.get('/admin/quarantine')
    assert delete_url.encode() in listing.data
    assert b'Delete copy' in listing.data
    assert client.get(delete_url).status_code == 200
    assert client.post(delete_url, data={'submit': 'Delete permanently'}).status_code == 302
    assert greylist.get(delete_entry['id']) is None
