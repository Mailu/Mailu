"""Behavioral coverage for sign-in routing and announcement delivery."""
import ipaddress
import re
from email import message_from_string
from unittest.mock import MagicMock

import pytest
from mailu import models, announcements

@pytest.fixture
def users(app, client):
    app.config.update(WTF_CSRF_ENABLED=False, WEBMAIL='roundcube', ADMIN=True)
    domain = models.Domain(name='ux.example')
    admin = models.User(localpart='admin', domain=domain, global_admin=True)
    user = models.User(localpart='alice', domain=domain)
    for item in (admin, user):
        item.set_password('test-password')
    models.db.session.add_all([domain, admin, user])
    models.db.session.commit()
    return admin, user

def authenticate(client, user):
    with client.session_transaction() as session:
        session['_user_id'] = user.email
        session['_fresh'] = True

def password_login(client, path='/sso/login', **data):
    return client.post(path, data=dict(email='alice@ux.example', pw='test-password', **data))

@pytest.mark.parametrize('path,destination', [('/sso/login/admin', '/admin'), ('/sso/login/webmail', '/webmail'), ('/sso/login', '/webmail')])
def test_password_destinations(client, users, path, destination):
    assert client.get(path).status_code == 200
    assert password_login(client, path).location == destination

def test_deep_link_survives_invalid_password(client, users):
    response = client.get('/admin/user/password?source=bookmark')
    assert response.location == '/sso/login'
    client.get(response.location)
    client.post('/sso/login', data={'email': users[1].email, 'pw': 'wrong'})
    assert password_login(client).location == '/admin/user/password?source=bookmark'
    with client.session_transaction() as session:
        assert 'signin_destination' not in session

def test_explicit_route_overrides_pending_link(client, users):
    client.get('/admin/user/password')
    client.get('/sso/login/webmail')
    assert password_login(client, '/sso/login/webmail').location == '/webmail'

def test_explicit_destination_selection_overrides_pending_link(client, users):
    client.get(
        '/sso/login',
        query_string={'url': 'http://localhost/webmail/?return=mail'},
    )
    response = password_login(
        client,
        destination='admin',
        destination_explicit='1',
    )
    assert response.location == '/admin'

@pytest.mark.parametrize('url', ['https://evil.example/', '//evil.example/', 'https://localhost.evil.example/', '/sso/login', '/\\evil.example/'])
def test_legacy_external_redirect_rejected(client, users, url):
    client.get('/sso/login', query_string={'url': url})
    assert password_login(client).location == '/webmail'

def test_legacy_local_bookmark(client, users):
    client.get('/sso/login', query_string={'url': 'http://localhost/admin/user/password?x=1'})
    assert password_login(client).location == '/admin/user/password?x=1'

def test_proxy_explicit_route_and_password_change(client, app, users):
    app.config['PROXY_AUTH_WHITELIST'] = {ipaddress.ip_network('127.0.0.0/8')}
    response = client.get('/sso/login/webmail', headers={'X-Auth-Email': users[1].email})
    assert response.location == '/webmail'
    users[1].change_pw_next_login = True
    models.db.session.commit()
    response = client.get('/sso/login/admin', headers={'X-Auth-Email': users[1].email})
    assert response.location == '/sso/pw_change'
    with client.session_transaction() as session:
        assert session['required_actions_destination'].endswith('/admin')

def test_password_change_passkey_escape_uses_logout_only_menu(client, users):
    users[1].change_pw_next_login = True
    models.db.session.commit()
    authenticate(client, users[1])

    forced_change = client.get('/sso/pw_change')
    assert b'href="/admin/user/passkeys"' in forced_change.data

    response = client.get('/admin/user/passkeys')

    assert response.status_code == 200
    assert b'Sign out' in response.data
    assert b'My account' not in response.data
    assert b'Auto-reply' not in response.data

def test_passkey_options_keep_destination_after_retry(client, users):
    client.get('/admin/user/password?x=1')
    client.get('/sso/login')
    for _ in range(2):
        response = client.post('/sso/passkey/options', json={'target': 'webmail'})
        assert response.status_code == 200
        assert 'allowCredentials' not in response.json
        with client.session_transaction() as session:
            assert session['passkey_login_destination'] == '/admin/user/password?x=1'

def test_alias_destination_search_excludes_anonymous_aliases(client, users):
    authenticate(client, users[0])
    domain = users[0].domain
    models.db.session.add_all([
        models.Alias(localpart='team', domain_name=domain.name),
        models.Alias(localpart='private', domain_name=domain.name, owner_email=users[1].email),
    ])
    models.db.session.commit()

    response = client.get('/admin/destinations/options', query_string={'q': 'ux.example'})
    assert response.status_code == 200
    addresses = {option['value'] for option in response.json['options']}
    assert users[0].email in addresses and users[1].email in addresses
    assert 'team@ux.example' in addresses
    assert 'private@ux.example' not in addresses

def test_anonymous_login_and_passkey_verification_require_csrf(client, app, users):
    app.config['WTF_CSRF_ENABLED'] = True
    response = client.get('/sso/login')
    token = re.search(rb'<input[^>]*name="csrf_token"[^>]*value="([^"]+)"', response.data).group(1).decode()

    missing_token = client.post('/sso/login', data={'email': users[1].email, 'pw': 'wrong'})
    assert missing_token.status_code == 200
    assert b'Wrong e-mail or password' not in missing_token.data
    valid_token = client.post('/sso/login', data={
        'csrf_token': token, 'email': users[1].email, 'pw': 'wrong',
    })
    assert valid_token.status_code == 200
    assert b'Wrong e-mail or password' in valid_token.data

    assert client.post('/sso/passkey/options', json={'target': 'webmail'}).status_code == 200
    assert client.post('/sso/passkey/verify', json={}, headers={}).status_code == 400
    verification = client.post('/sso/passkey/verify', json={}, headers={'X-CSRFToken': token})
    assert verification.status_code == 400
    assert verification.json['error'] == 'Sign-in expired. Please try again.'

def test_disabled_destination(client, app, users):
    app.config['WEBMAIL'] = 'none'
    assert client.get('/sso/login/webmail').status_code == 404
    assert password_login(client).location == '/admin'

PAYLOAD = dict(announcement_subject='Maintenance ✓', announcement_body='<h2>Hello</h2><p>Visit <a href="https://example.com">our site</a>.</p>')

def preview(client, **overrides):
    response = client.post('/admin/announcement', data={**PAYLOAD, **overrides, 'action': 'preview'})
    assert response.status_code == 200
    return re.search(rb'name="draft_token" value="([^"]+)"', response.data).group(1).decode(), response

def test_preview_and_test_do_not_broadcast(client, users, monkeypatch):
    authenticate(client, users[0])
    deliveries = []
    monkeypatch.setattr(models.User, 'sendmail', lambda user, *args, **kw: deliveries.append((user.email, args, kw)) or True)
    token, response = preview(client)
    assert b'Plain-text version' in response.data and not deliveries
    response = client.post('/admin/announcement', data={**PAYLOAD, 'action': 'test'})
    assert response.status_code == 200
    assert len(deliveries) == 1 and deliveries[0][0] == users[0].email
    assert deliveries[0][1][0].startswith('[TEST]')
    assert b'Maintenance' in response.data

def test_confirmed_snapshot_sent_once(client, users, monkeypatch):
    authenticate(client, users[0])
    deliveries = []
    monkeypatch.setattr(models.User, 'sendmail', lambda user, *args, **kw: deliveries.append((user.email, args, kw)) or True)
    token, _ = preview(client)
    data = {**PAYLOAD, 'announcement_subject': 'Tampered', 'action': 'send', 'draft_token': token}
    assert client.post('/admin/announcement', data=data).status_code == 302
    assert len(deliveries) == 2
    assert all(item[1][0] == PAYLOAD['announcement_subject'] for item in deliveries)
    assert client.post('/admin/announcement', data=data).status_code == 200
    assert len(deliveries) == 2

def test_partial_failure_retry_excludes_successes(client, users, monkeypatch):
    authenticate(client, users[0])
    deliveries = []
    def deliver(user, *args, **kw):
        deliveries.append(user.email)
        return user.email != users[1].email
    monkeypatch.setattr(models.User, 'sendmail', deliver)
    token, _ = preview(client)
    response = client.post('/admin/announcement', data={**PAYLOAD, 'action': 'send', 'draft_token': token})
    assert b'1 delivered; 1 failed.' in response.data
    retry_token = re.search(rb'name="retry_token" value="([^"]+)"', response.data).group(1).decode()
    retry, _ = preview(client, retry_token=retry_token)
    with client.application.test_request_context():
        draft = announcements.load(retry, users[0].email)
        assert draft['recipients'] == [users[1].email]
    assert users[0].email in deliveries

def test_announcement_permissions(client, users):
    authenticate(client, users[1])
    assert client.get('/admin/announcement').status_code == 403
    assert client.post('/admin/announcement', data=PAYLOAD).status_code == 403

def test_sanitization_and_empty_content(app):
    html, plain = announcements.sanitize('<script>alert(1)</script><p>Hello <a href="javascript:alert(1)">world</a><img src="x" onerror="x"></p>')
    assert 'script' not in html and 'javascript' not in html and '<img' not in html
    assert 'Hello world' in plain
    with pytest.raises(ValueError):
        announcements.sanitize('<p><br></p>')

def test_multipart_delivery_and_plaintext_compatibility(app, users, monkeypatch):
    app.config['FRONT_ADDRESS'] = 'front'
    lmtp = MagicMock()
    monkeypatch.setattr('mailu.models.smtplib.LMTP', lambda **kwargs: lmtp)
    for html in [None, '<p>Hello ✓</p>']:
        assert users[0].sendmail('Subject ✓', 'Hello ✓', html_body=html)
        message = message_from_string(lmtp.__enter__.return_value.sendmail.call_args.args[2])
        assert message.is_multipart() == (html is not None)
        if html:
            assert [part.get_content_type() for part in message.get_payload()] == ['text/plain', 'text/html']
            assert message.get_payload(1).get_payload(decode=True).decode() == html


def test_locale_falls_back_without_accept_language(client, users):
    response = client.get('/sso/login')
    assert b'lang="en"' in response.data
    assert b'lang="None"' not in response.data


def test_subject_newline_rejected(client, users, monkeypatch):
    authenticate(client, users[0])
    deliveries = []
    monkeypatch.setattr(models.User, 'sendmail', lambda *args, **kw: deliveries.append(args))
    response = client.post('/admin/announcement', data={**PAYLOAD, 'announcement_subject': 'Subject\n', 'action': 'test'})
    assert response.status_code == 200 and not deliveries
    assert b'Enter a subject on one line.' in response.data


def test_expired_retry_does_not_expand_to_all_recipients(client, users):
    authenticate(client, users[0])
    response = client.post('/admin/announcement', data={**PAYLOAD, 'action': 'preview', 'retry_token': 'expired'})
    assert b'This retry expired.' in response.data
    assert b'name="draft_token"' not in response.data


def test_draft_is_owner_bound_and_expires(app, users, monkeypatch):
    with app.test_request_context():
        token, draft = announcements.save('Subject', '<p>Hello</p>', 'Hello', [users[1].email], users[0].email)
        assert announcements.load(token, users[1].email, consume=True) is None
        assert announcements.load(token, users[0].email) is not None
        monkeypatch.setattr(announcements.time, 'time', lambda: draft['expires'] + 1)
        assert announcements.load(token, users[0].email, consume=True) is None


def test_invalid_openpgp_preserves_values_and_opens_advanced_section(client, users, monkeypatch):
    authenticate(client, users[1])
    monkeypatch.setattr('mailu.openpgp.parse_public_key', lambda *args, **kwargs: (None, []))
    response = client.post('/admin/user/settings', data={'displayed_name': 'Draft display name', 'spam_threshold': 80, 'gpg_key': 'invalid key'})
    assert response.status_code == 200
    assert b'value="Draft display name"' in response.data
    assert re.search(rb'<details\b[^>]*\bopen(?:\s|>)', response.data)
    assert b'Enter a valid OpenPGP public key' in response.data


@pytest.mark.parametrize('target', ['admin', 'webmail'])
def test_successful_login_remembers_destination(client, users, target):
    response = password_login(client, '/sso/login/' + target)
    assert response.status_code == 302
    cookie = client.get_cookie('mailu_signin_target', path='/sso')
    assert cookie and cookie.value == target
    client.get('/sso/logout')
    response = client.get('/sso/login')
    assert ('value="' + target + '" selected').encode() in response.data or ('selected value="' + target + '"').encode() in response.data
    other = 'webmail' if target == 'admin' else 'admin'
    client.get('/sso/login/' + other)
    assert password_login(client, '/sso/login/' + other).location == ('/webmail' if other == 'webmail' else '/admin')


def test_failed_login_does_not_remember_destination(client, users):
    client.post('/sso/login/admin', data={'email': users[1].email, 'pw': 'wrong'})
    assert client.get_cookie('mailu_signin_target', path='/sso') is None


def test_cookie_never_overrides_protected_page(client, users):
    client.set_cookie('mailu_signin_target', 'webmail', path='/sso')
    client.get('/admin/user/password')
    assert password_login(client).location == '/admin/user/password'


REPLY = dict(reply_enabled='y', reply_subject='Away', reply_body='Hello', reply_schedule='dates', reply_startdate='2026-10-20', reply_enddate='2026-10-22')


def test_formatted_reply_and_inclusive_schedule(client, users):
    authenticate(client, users[1])
    response = client.post('/admin/user/reply', data={**REPLY, 'reply_formatted': '1', 'reply_body_html': '<p>Hello <strong>world</strong></p>'})
    assert response.status_code == 302
    user = models.User.get(users[1].email)
    assert user.reply_body == 'Hello world'
    assert '<strong>world</strong>' in user.reply_body_html
    assert str(user.reply_startdate) == '2026-10-20' and str(user.reply_enddate) == '2026-10-22'
    mime = message_from_string(user.reply_mime)
    assert [part.get_content_type() for part in mime.get_payload()] == ['text/plain', 'text/html']
    assert mime.get_payload(0).get_payload(decode=True).decode() == 'Hello world'


@pytest.mark.parametrize('start,end', [('2026-10-22','2026-10-20'), ('','2026-10-20'), ('2026-10-20','')])
def test_reply_rejects_incomplete_or_reversed_dates(client, users, start, end):
    authenticate(client, users[1])
    response = client.post('/admin/user/reply', data={**REPLY, 'reply_startdate': start, 'reply_enddate': end})
    assert response.status_code == 200
    assert not models.User.get(users[1].email).reply_enabled
    assert b'is-invalid' in response.data


def test_single_day_reply_and_plaintext_fallback(client, users):
    authenticate(client, users[1])
    response = client.post('/admin/user/reply', data={**REPLY, 'reply_body': 'Literal <text>\nSecond line', 'reply_startdate': '2026-10-20', 'reply_enddate': '2026-10-20'})
    assert response.status_code == 302
    user = models.User.get(users[1].email)
    assert user.reply_body == 'Literal <text>\nSecond line' and user.reply_body_html is None
    assert user.reply_startdate == user.reply_enddate


def test_plaintext_clients_clear_stale_formatted_reply(app, users):
    user = users[1]
    user.reply_body_html = '<p>Rich <strong>message</strong></p>'
    assert user.reply_body_html and user.reply_body == 'Rich message'
    user.reply_body = 'Updated by an existing API client'
    assert user.reply_body_html is None and user.reply_mime is None


def test_reply_until_disabled_and_disable_without_dates(client, users):
    authenticate(client, users[1])
    response = client.post('/admin/user/reply', data={**REPLY, 'reply_schedule':'always', 'reply_startdate':'', 'reply_enddate':''})
    assert response.status_code == 302
    assert str(users[1].reply_startdate) == '1900-01-01' and str(users[1].reply_enddate) == '2999-12-31'
    assert users[1].reply_active
    response = client.post('/admin/user/reply', data={'reply_schedule':'dates', 'reply_body':''})
    assert response.status_code == 302 and not users[1].reply_enabled


def test_sieve_uses_mime_only_for_formatted_replies(client, users):
    user=users[1]
    user.reply_enabled=True
    user.reply_body_html='<p>Hello <strong>world</strong></p>'
    models.db.session.commit()
    response=client.get('/internal/dovecot/sieve/data/default/'+user.email)
    assert response.status_code == 200 and ':mime ' in response.get_json()
    user.reply_body='Legacy plain text'
    models.db.session.commit()
    response=client.get('/internal/dovecot/sieve/data/default/'+user.email)
    assert ':mime ' not in response.get_json() and 'Legacy plain text' in response.get_json()


def test_account_search_is_bounded_and_finds_names(client, users):
    authenticate(client,users[0])
    domain=users[0].domain
    for number in range(60):
        models.db.session.add(models.User(localpart='search'+str(number),domain=domain,password='!',displayed_name='Unique Person' if number==59 else ''))
    models.db.session.commit()
    response=client.get('/admin/users/options?purpose=admin')
    assert response.status_code==200 and len(response.json['options'])==50 and response.json['more']
    response=client.get('/admin/users/options',query_string={'purpose':'admin','q':'Unique Person'})
    assert len(response.json['options'])==1 and response.json['options'][0]['value']=='search59@ux.example'
    response=client.get('/admin/users/options',query_string={'purpose':'admin','q':'%'})
    assert response.json['options']==[]


def test_bulk_roles_and_existing_grants_are_idempotent(client,users):
    authenticate(client,users[0])
    email=users[1].email
    for path,field in [('/admin/domain/access/create/ux.example','user'),('/admin/manager/create/ux.example','manager'),('/admin/admin/create','admin')]:
        for _ in range(2):
            response=client.post(path,data={field:[email,users[0].email]})
            assert response.status_code==302
    assert models.DomainAccess.query.filter_by(domain_name='ux.example').count()==2
    assert users[0].domain.managers.count()==2
    assert models.User.get(email).global_admin


def test_picker_permissions_and_atomic_scope_validation(client,users):
    domain=users[0].domain
    manager=models.User(localpart='manager',domain=domain,password='!')
    other=models.Domain(name='outside.example')
    outsider=models.User(localpart='outsider',domain=other,password='!')
    domain.managers.append(manager)
    models.db.session.add_all([manager,other,outsider]);models.db.session.commit()
    authenticate(client,manager)
    assert client.get('/admin/users/options?purpose=admin').status_code==403
    assert client.get('/admin/users/options?purpose=manager&domain=outside.example').status_code==403
    response=client.get('/admin/users/options?purpose=manager&domain=ux.example')
    assert all(item['value'].endswith('@ux.example') for item in response.json['options'])
    response=client.post('/admin/domain/access/create/ux.example',data={'user':[users[1].email,outsider.email]})
    assert response.status_code==200
    assert b'outside your permissions' in response.data
    assert models.DomainAccess.query.count()==0


def test_formatted_reply_mime_is_stable(app, users):
    user = users[1]
    user.reply_body_html = '<p>Hello <strong>world</strong></p>'
    assert user.reply_mime == user.reply_mime
    plain = user.reply_body
    user.reply_body = plain
    assert user.reply_body_html


def test_reply_preview_is_sanitized_and_does_not_save(client, users):
    authenticate(client, users[1])
    response = client.post('/admin/user/reply/preview', data={'reply_body_html':'<p>Hello <strong>world</strong><script>alert(1)</script></p>'})
    assert response.status_code == 200
    assert response.json['html'] == '<p>Hello <strong>world</strong></p>'
    assert not users[1].reply_enabled and users[1].reply_body_html is None
    assert client.post('/admin/user/reply/'+users[0].email+'/preview', data={'reply_body':'Hello'}).status_code == 403


def test_disabling_reply_keeps_saved_message_and_dates(client, users):
    authenticate(client, users[1])
    client.post('/admin/user/reply', data={**REPLY, 'reply_formatted':'1', 'reply_body_html':'<p>Keep this message</p>'})
    response = client.post('/admin/user/reply', data={'reply_enabled':'', 'reply_body':'Unfinished draft', 'reply_schedule':'dates', 'reply_startdate':'2026-10-22','reply_enddate':'2026-10-20'})
    assert response.status_code == 302
    assert not users[1].reply_enabled
    assert users[1].reply_body == 'Keep this message' and users[1].reply_body_html == '<p>Keep this message</p>'
    assert str(users[1].reply_startdate) == '2026-10-20'
    response = client.get('/admin/user/reply')
    assert b'id="reply-configuration" hidden' in response.data


def test_reply_preview_requires_csrf(client, app, users):
    authenticate(client, users[1])
    app.config['WTF_CSRF_ENABLED'] = True
    assert client.post('/admin/user/reply/preview', data={'reply_body':'Hello'}).status_code == 400


def test_token_default_and_legacy_password_override(app, users):
    from mailu.configuration import DEFAULT_CONFIG
    from mailu.internal.nginx import check_credentials
    assert DEFAULT_CONFIG['AUTH_REQUIRE_TOKENS'] is True
    user = users[1]
    app.config['AUTH_REQUIRE_TOKENS'] = True
    assert not check_credentials(user, 'test-password', '127.0.0.1', protocol='imap')
    assert check_credentials(user, 'test-password', '127.0.0.1', protocol='sso')
    token = models.Token(user=user)
    secret = '0123456789abcdef0123456789abcdef'
    token.set_password(secret)
    models.db.session.add(token)
    models.db.session.commit()
    assert check_credentials(user, secret, '127.0.0.1', protocol='imap')
    app.config['AUTH_REQUIRE_TOKENS'] = False
    assert check_credentials(user, 'test-password', '127.0.0.1', protocol='imap')


def test_token_setup_guidance(client, app, users):
    user = users[1]
    authenticate(client, user)
    assert b'No authentication tokens are configured' in client.get('/admin/user/settings').data
    assert b'set once and forgotten' in client.get('/admin/token/list').data
    assert b'cannot be displayed again' in client.get('/admin/token/create').data
    for required in (True, False):
        app.config['AUTH_REQUIRE_TOKENS'] = required
        page = client.get('/admin/client').data
        assert b'Create a separate authentication token' in page
    token = models.Token(user=user)
    token.set_password('0123456789abcdef0123456789abcdef')
    models.db.session.add(token)
    models.db.session.commit()
    assert b'No authentication tokens are configured' not in client.get('/admin/user/settings').data


def test_settings_toggle_stays_outside_disabled_controls(client, users):
    authenticate(client, users[1])
    page = client.get('/admin/user/settings').data.decode()
    assert page.index('id="forward_enabled"') < page.index('data-toggle-field="forward_enabled"')
    assert re.search(r'<fieldset[^>]*data-toggle-field="forward_enabled"[^>]*disabled', page)
    assert re.search(r'<input[^>]*class="form-range"[^>]*id="spam_threshold"', page)


@pytest.mark.parametrize('route', ['user/settings', 'user/password', 'user/passkeys', 'user/reply', 'token/list', 'token/create', 'fetch/list', 'fetch/create'])
def test_account_subtitle_only_identifies_another_account(client, users, route):
    authenticate(client, users[0])
    own_page = client.get('/admin/' + route).data.decode()
    own_subtitle = re.search(r'<small>(.*?)</small>', own_page, re.S).group(1)
    assert users[0].email not in own_subtitle
    target_route = 'user/usersettings' if route == 'user/settings' else route
    target_page = client.get('/admin/' + target_route + '/' + users[1].email).data.decode()
    target_subtitle = re.search(r'<small>(.*?)</small>', target_page, re.S).group(1)
    assert users[1].email in target_subtitle


def test_user_list_does_not_link_own_account_address(client, users):
    authenticate(client, users[0])
    page = client.get('/admin/user/list/ux.example').data.decode()
    assert not re.search(r'href="[^"]*/user/edit/' + re.escape(users[0].email) + r'">' + re.escape(users[0].email) + r'</a>', page)
