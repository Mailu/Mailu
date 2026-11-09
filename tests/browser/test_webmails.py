"""Browser smoke tests against a running Mailu with a disposable mailbox.

Set MAILU_TEST_URL, MAILU_TEST_EMAIL and MAILU_TEST_PASSWORD. The account must
have permission to send to itself and use ManageSieve. These tests create mail
and filter scripts in that account.
"""
import os
import re
import time
import uuid

import pytest
from playwright.sync_api import sync_playwright, expect


@pytest.fixture
def page():
    required = ('MAILU_TEST_URL', 'MAILU_TEST_EMAIL', 'MAILU_TEST_PASSWORD')
    if any(not os.environ.get(name) for name in required):
        pytest.skip('Set MAILU_TEST_URL, MAILU_TEST_EMAIL and MAILU_TEST_PASSWORD')
    with sync_playwright() as playwright:
        options = {'headless': True}
        if os.environ.get('MAILU_TEST_CHROMIUM'):
            options['executable_path'] = os.environ['MAILU_TEST_CHROMIUM']
        browser = playwright.chromium.launch(**options)
        context = browser.new_context(ignore_https_errors=os.environ.get('MAILU_TEST_INSECURE') == '1')
        page = context.new_page()
        page.goto(os.environ['MAILU_TEST_URL'].rstrip('/') + '/sso/login')
        page.locator('[name=email]').fill(os.environ['MAILU_TEST_EMAIL'])
        page.locator('[name=pw]').fill(os.environ['MAILU_TEST_PASSWORD'])
        page.locator('[name=submit]').click()
        expect(page).not_to_have_url(re.compile(r'/sso/login'))
        yield page
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
