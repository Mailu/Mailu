"""Browser smoke tests against a running Mailu with a disposable mailbox.

Set MAILU_TEST_URL, MAILU_TEST_EMAIL and MAILU_TEST_PASSWORD. The account must
have permission to send to itself and use ManageSieve. These tests create mail
and filter scripts in that account.
"""
import os
import base64
import re
import time
import uuid
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree as ET

import pytest
from playwright.sync_api import sync_playwright, expect


@pytest.fixture
def page(request):
    required = ('MAILU_TEST_URL', 'MAILU_TEST_EMAIL', 'MAILU_TEST_PASSWORD')
    if any(not os.environ.get(name) for name in required):
        pytest.skip('Set MAILU_TEST_URL, MAILU_TEST_EMAIL and MAILU_TEST_PASSWORD')
    with sync_playwright() as playwright:
        options = {'headless': True}
        if os.environ.get('MAILU_TEST_CHROMIUM'):
            options['executable_path'] = os.environ['MAILU_TEST_CHROMIUM']
        browser = playwright.chromium.launch(**options)
        context = browser.new_context(ignore_https_errors=os.environ.get('MAILU_TEST_INSECURE') == '1')
        artifacts = os.environ.get('MAILU_TEST_ARTIFACTS')
        if artifacts:
            context.tracing.start(screenshots=True, snapshots=True, sources=True)
        page = context.new_page()
        try:
            page.goto(os.environ['MAILU_TEST_URL'].rstrip('/') + '/sso/login')
            page.locator('[name=email]').fill(os.environ['MAILU_TEST_EMAIL'])
            page.locator('[name=pw]').fill(os.environ['MAILU_TEST_PASSWORD'])
            page.locator('[name=submit]').click()
            expect(page).not_to_have_url(re.compile(r'/sso/login'))
            yield page
        finally:
            if artifacts:
                directory = Path(artifacts)
                directory.mkdir(parents=True, exist_ok=True)
                name = re.sub(r'[^\w.-]', '_', request.node.name)
                page.screenshot(path=str(directory / f'{name}.png'), full_page=True)
                context.tracing.stop(path=str(directory / f'{name}.zip'))
            browser.close()


def open_webmail(page, webmail):
    page.goto(os.environ['MAILU_TEST_URL'].rstrip('/') + '/' + webmail + '/')


@pytest.mark.parametrize('webmail', ['roundcube', 'snappymail'])
def test_sso_send_receive_and_sieve(page, webmail):
    email = os.environ['MAILU_TEST_EMAIL']
    marker = 'mailu-browser-' + uuid.uuid4().hex[:12]
    open_webmail(page, webmail)
    if webmail == 'roundcube':
        expect(page.get_by_text('Compose', exact=True).first).to_be_visible()
        page.goto(os.environ['MAILU_TEST_URL'].rstrip('/') + '/roundcube/?_task=mail&_action=compose')
        page.locator('#_to').fill(email)
        page.locator('#compose-subject').fill(marker)
        page.locator('#composebody').fill('Mailu browser test')
        page.get_by_text('Send', exact=True).first.click()
        expect(page.get_by_text(marker, exact=True).first).to_be_visible(timeout=30000)
        page.get_by_text('Settings', exact=True).first.click()
        page.get_by_text('Filters', exact=True).first.click()
        page.get_by_title('Add filter', exact=True).click()
        frame = page.frame_locator('iframe').first
        frame.locator('#_name').fill(marker)
        frame.locator('input[name="_rule_target[0][]"]').first.fill(marker)
        frame.locator('#action_type0').select_option(label='Keep message in Inbox')
        frame.get_by_text('Save', exact=True).click()
        expect(page.get_by_text(marker, exact=True).first).to_be_visible(timeout=15000)
        page.reload()
        expect(page.get_by_text(marker, exact=True).first).to_be_visible(timeout=15000)
    else:
        expect(page.get_by_text('New message', exact=False).first).to_be_visible()
        page.get_by_text('New message', exact=False).first.click()
        recipient = page.locator('input[list=emailaddresses-datalist]:visible').first
        recipient.fill(email)
        recipient.press('Enter')
        page.locator('input[name=subject]').fill(marker)
        page.locator('[contenteditable=true]').fill('Mailu browser test')
        page.get_by_text('Send', exact=True).last.click()
        # SnappyMail does not immediately refresh the inbox after sending.
        for _ in range(15):
            page.reload()
            if page.get_by_text(marker, exact=True).count():
                break
            time.sleep(2)
        expect(page.get_by_text(marker, exact=True).first).to_be_visible(timeout=15000)
        page.get_by_text(email, exact=False).first.click()
        page.get_by_text('Settings', exact=True).first.click()
        page.get_by_text('Filters', exact=True).first.click()
        page.get_by_text('Add a Script', exact=True).click()
        page.locator('input[placeholder=Name]:visible').fill(marker)
        page.locator('textarea:visible').fill('if header :contains "Subject" "' + marker + '" { keep; }')
        page.get_by_text('Save', exact=True).last.click()
        expect(page.locator('tr:visible').filter(has_text=marker).first).to_be_visible(timeout=15000)
        page.reload()
        expect(page.locator('tr:visible').filter(has_text=marker).first).to_be_visible(timeout=15000)


def test_webmail_preference(page):
    base = os.environ['MAILU_TEST_URL'].rstrip('/')
    for webmail in ('snappymail', 'roundcube'):
        page.goto(base + '/admin/user/settings')
        advanced = page.locator('details').filter(has_text='Advanced: OpenPGP')
        assert advanced.evaluate("element => !!element.nextElementSibling?.querySelector('input[name=submit]')")
        choice = page.locator('input[name=webmail_preference][value="' + webmail + '"]')
        page.locator('label[for="' + choice.get_attribute('id') + '"]').click()
        expect(choice).to_be_checked()
        page.locator('input[name=submit]').click()
        expect(page.get_by_text('Settings updated', exact=False)).to_be_visible()
        page.goto(base + '/webmail')
        expect(page).to_have_url(re.compile('/' + webmail + r'/'), timeout=15000)


@pytest.mark.parametrize('webmail', ['roundcube', 'snappymail'])
def test_sso_headers_are_not_forwarded_to_other_scripts(page, webmail):
    if os.environ.get('MAILU_TEST_HEADER_PROBE') != '1':
        pytest.skip('Install the disposable header probe as described in the README')
    base = os.environ['MAILU_TEST_URL'].rstrip('/')
    headers = {
        'X-Remote-User': 'spoofed-user',
        'X-Remote-User-Token': 'spoofed-token',
        'X-Remote-User-Aliases': 'spoofed-alias',
        'X-Remote-User-Aliases-Complete': 'true',
    }
    for script in ('mailu-header-probe.php', 'sso.php-probe.php'):
        response = page.request.get(f'{base}/{webmail}/{script}', headers=headers)
        assert response.ok
        assert response.json() == {}


def require_webdav():
    if os.environ.get('MAILU_TEST_WEBDAV') != '1':
        pytest.skip('Set MAILU_TEST_WEBDAV=1 on a deployment with Radicale enabled')


@pytest.fixture
def dav_contact(page):
    """Seed a contact through DAV, independently of either webmail's database."""
    require_webdav()
    base = os.environ['MAILU_TEST_URL'].rstrip('/')
    email = os.environ['MAILU_TEST_EMAIL']
    password = os.environ.get('MAILU_TEST_DAV_PASSWORD', os.environ['MAILU_TEST_PASSWORD'])
    authorization = 'Basic ' + base64.b64encode(f'{email}:{password}'.encode()).decode()
    headers = {'Authorization': authorization, 'Content-Type': 'application/xml', 'Depth': '0'}
    response = page.request.fetch(base + '/webdav/', method='PROPFIND', headers=headers, data='''
        <propfind xmlns="DAV:"><prop><current-user-principal/></prop></propfind>''')
    assert response.status == 207, response.text()
    principal = ET.fromstring(response.body()).findtext('.//{DAV:}current-user-principal/{DAV:}href')
    assert principal
    response = page.request.fetch(urljoin(base + '/', principal), method='PROPFIND',
        headers={**headers, 'Depth': '1'}, data='''
        <propfind xmlns="DAV:"><prop><resourcetype/><displayname/></prop></propfind>''')
    assert response.status == 207, response.text()
    books = [item for item in ET.fromstring(response.body()).findall('{DAV:}response')
             if item.find('.//{urn:ietf:params:xml:ns:carddav}addressbook') is not None]
    assert books, 'No address book was provisioned for the disposable mailbox'
    book = next((item for item in books if item.findtext('{DAV:}href').endswith('/contacts/')), books[0])
    collection = urljoin(base + '/', book.findtext('{DAV:}href'))
    assert urlsplit(collection).netloc == urlsplit(base).netloc
    marker = 'Mailu DAV ' + uuid.uuid4().hex[:12]
    # DAV resource names need not match vCard UIDs. Preserve both on edits.
    card_url = collection + uuid.uuid4().hex + '.vcf'
    uid = str(uuid.uuid4())
    card = '\r\n'.join(['BEGIN:VCARD', 'VERSION:3.0', f'UID:{uid}',
                        f'FN:{marker}', f'N:{marker};;;;',
                        f'EMAIL:{uuid.uuid4().hex}@example.net', 'END:VCARD', ''])
    response = page.request.put(card_url, headers={'Authorization': authorization,
        'Content-Type': 'text/vcard', 'If-None-Match': '*'}, data=card)
    assert response.status == 201, response.text()
    try:
        yield {'name': marker, 'uid': uid, 'book': book.findtext('.//{DAV:}displayname'),
               'read': lambda: page.request.get(card_url, headers={'Authorization': authorization})}
    finally:
        response = page.request.delete(card_url, headers={'Authorization': authorization})
        assert response.status in (200, 204, 404), response.text()


@pytest.mark.parametrize('webmail', ['roundcube', 'snappymail'])
def test_webmail_automatically_uses_radicale_contacts(page, dav_contact, webmail):
    """Read and edit a DAV contact without manually configuring either webmail."""
    base = os.environ['MAILU_TEST_URL'].rstrip('/')
    updated = dav_contact['name'] + ' updated'

    def snappymail_action(response, action):
        return ('/snappymail/' in response.url and response.request.method == 'POST'
                and (response.request.post_data_json or {}).get('Action') == action)
    if webmail == 'roundcube':
        open_webmail(page, webmail)
        page.goto(base + '/roundcube/?_task=addressbook')
        book = page.get_by_role('treeitem', name=re.compile(re.escape(dav_contact['book']) + '$')).get_by_role('link')
        expect(book).to_be_visible(timeout=30000)
        book.click()
        contact = page.get_by_role('option').filter(has_text=dav_contact['name'])
        # A reused mailbox may still have Roundcube's one-minute DAV cache.
        # Reload after waiting for the row, without changing DAV settings.
        for attempt in range(7):
            try:
                expect(contact).to_be_visible(timeout=10000)
                break
            except AssertionError:
                if attempt == 6:
                    raise
                page.reload()
        contact.click()
        details = page.frame_locator('iframe').first
        expect(details.get_by_text(dav_contact['name'], exact=True).first).to_be_visible()
        details.get_by_role('button', name=re.compile(r'Edit$')).click()
        details.locator('input[name=_surname]').fill(updated)
        details.get_by_role('button', name=re.compile(r'Save$')).click()
        expect(details.get_by_role('button', name=re.compile(r'Edit$'))).to_be_visible()
    else:
        # The initial automatic sync starts ten seconds after loading SnappyMail.
        # Waiting for it proves the browser initialized the configured plugin;
        # this test never fills or saves the synchronization settings.
        with page.expect_response(lambda response: 'ContactsSync' in response.url, timeout=45000) as sync:
            open_webmail(page, webmail)
        assert sync.value.ok, f'Automatic CardDAV sync returned HTTP {sync.value.status}'
        page.locator('.buttonContacts:visible').click()
        contact = page.locator('.e-contact-item').filter(has_text=dav_contact['name'])
        # Streaming headers arrive before the import finishes. Re-query via
        # the contact search if the popup initially fetched the old local list.
        for attempt in range(3):
            try:
                expect(contact).to_be_visible(timeout=5000)
                break
            except AssertionError:
                if attempt == 2:
                    raise
                search = page.get_by_role('dialog').get_by_role('searchbox')
                search.fill(dav_contact['name'] if attempt == 0 else '')
                search.press('Tab')
        page.get_by_text(dav_contact['name'], exact=True).click()
        page.locator('input[data-bind="textInput: surName"]:visible').fill(updated)
        with page.expect_response(lambda response: snappymail_action(response, 'ContactSave')) as saved:
            page.locator('.button-save-contact:visible').click()
        assert not saved.value.json().get('code'), saved.value.json()
        assert saved.value.json()['Result']['Result'] is True, saved.value.json()
        page.locator('#contacts-more-dropdown-id').click()
        # The normal UI reloads the contact list when the streamed sync ends.
        with page.expect_response(lambda response: snappymail_action(response, 'Contacts')) as refreshed:
            with page.expect_response(lambda response: 'ContactsSync' in response.url, timeout=15000) as sync:
                page.locator('a[data-bind="command: syncCommand"]:visible').click()
        assert sync.value.ok, f'CardDAV upload returned HTTP {sync.value.status}'
        assert not refreshed.value.json().get('code'), refreshed.value.json()
    response = dav_contact['read']()
    assert response.ok
    assert updated in response.text(), 'The edit did not reach Radicale'
    assert f"UID:{dav_contact['uid']}" in response.text(), 'The vCard UID changed during editing'


def test_radicale_browser_uses_mailu_login(page):
    require_webdav()
    base = os.environ['MAILU_TEST_URL'].rstrip('/')
    page.goto(base + '/webdav/.web/')
    expect(page).to_have_url(re.compile(r'/webdav/\.web/'))
    expect(page.get_by_text('Contacts', exact=True).first).to_be_visible(timeout=15000)
    # These Radicale UI assets have /api/ in their path. The front's top-level
    # /api proxy must not capture them and send them to the admin API.
    for asset in ('api/api.js', 'api/common.js', 'api/sharing.js'):
        response = page.request.get(base + '/webdav/.web/js/' + asset)
        assert response.ok, f'{asset} returned HTTP {response.status}'
    # A same-origin browser can make DAV requests using only its Mailu cookie.
    status = page.evaluate("""async () => (await fetch('/webdav/', {
        method: 'PROPFIND', headers: {'Depth': '0'}
    })).status""")
    assert status == 207
    # The client-supplied context header must not select private token auth.
    password = os.environ.get('MAILU_TEST_DAV_PASSWORD', os.environ['MAILU_TEST_PASSWORD'])
    authorization = 'Basic ' + base64.b64encode(
        f"{os.environ['MAILU_TEST_EMAIL']}:{password}".encode()).decode()
    response = page.request.fetch(base + '/webdav/', method='PROPFIND', headers={
        'Authorization': authorization, 'X-Mailu-Auth-Context': 'webmail', 'Depth': '0',
    })
    assert response.status == 207, response.text()


def test_public_dav_discovery(page):
    require_webdav()
    base = os.environ['MAILU_TEST_URL'].rstrip('/')
    for path in ('/.well-known/carddav', '/.well-known/caldav'):
        response = page.request.get(base + path, max_redirects=0)
        assert response.status == 308
        assert response.headers['location'] == '/webdav/'
    for path in ('/mail/config-v1.1.xml', '/.well-known/client-autoconfig.xml', '/apple.mobileconfig'):
        response = page.request.get(base + path)
        assert response.ok
        ET.fromstring(response.body())
        assert 'carddav' in response.text().lower()
        assert 'caldav' in response.text().lower()
        assert '/webdav/' in response.text()
    response = page.request.post(base + '/autodiscover/autodiscover.xml', data='''
        <Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/outlook/requestschema/2006">
        <Request><EMailAddress>user@example.org</EMailAddress>
        <AcceptableResponseSchema>http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a</AcceptableResponseSchema>
        </Request></Autodiscover>''', headers={'Content-Type': 'application/xml'})
    assert response.ok
    root = ET.fromstring(response.body())
    namespace = {'a': 'http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a'}
    assert any(item.findtext('a:Type', namespaces=namespace) == 'DAV'
               for item in root.findall('.//a:Protocol', namespace))
