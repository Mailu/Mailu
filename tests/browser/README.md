Install `pytest` and `playwright`, then install a Chromium browser with
`playwright install chromium`. Set `MAILU_TEST_URL`, `MAILU_TEST_EMAIL`, and
`MAILU_TEST_PASSWORD` to a running deployment and a provisioned disposable mailbox, then
run `pytest --confcutdir=tests/browser tests/browser/test_webmails.py`. The suite
checks SSO, sending and receiving, and Sieve filter creation separately for
Roundcube and SnappyMail. It creates messages and filters in that mailbox. `MAILU_TEST_CHROMIUM` may specify an existing
Chromium binary; set `MAILU_TEST_INSECURE=1` only for a test server with an
untrusted certificate.
Set `MAILU_TEST_ARTIFACTS` to a directory to retain screenshots and Playwright
traces. Traces include session data; keep them with the disposable test environment.

To include the DAV integration tests, enable Radicale and set
`MAILU_TEST_WEBDAV=1`. These tests seed disposable vCards through DAV and verify
that both webmails display them without manual CardDAV configuration. They edit
the contacts in each webmail and verify the updates through DAV. The
SnappyMail test waits for its automatic browser synchronization. The suite also
checks Radicale browser SSO and the public discovery responses. Seeded vCards
are deleted after each test. Set `MAILU_TEST_DAV_PASSWORD` to a device token if
DAV requires different credentials from the browser login.

Run only these checks with:

```sh
pytest --confcutdir=tests/browser tests/browser/test_webmails.py -k 'radicale or dav'
```

To test SSO header isolation, install the following disposable PHP script as
`mailu-header-probe.php` and `sso.php-probe.php` in each webmail's public
directory, set `MAILU_TEST_HEADER_PROBE=1`, and run the same suite. Remove the
probe files after testing. Use a disposable deployment and account.

```php
<?php
header('Content-Type: application/json');
$headers = array_filter($_SERVER, fn($key) => str_starts_with($key, 'HTTP_X_REMOTE_USER'), ARRAY_FILTER_USE_KEY);
echo json_encode((object)$headers);
```
