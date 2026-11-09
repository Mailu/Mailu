Install `pytest` and `playwright`, then install a Chromium browser with
`playwright install chromium`. Set `MAILU_TEST_URL`, `MAILU_TEST_EMAIL`, and
`MAILU_TEST_PASSWORD` to a running deployment and a provisioned disposable mailbox, then
run `pytest --confcutdir=tests/browser tests/browser/test_webmails.py`. The suite
checks SSO, sending and receiving, and Sieve filter creation separately for
Roundcube and SnappyMail. It creates messages and filters in that mailbox. `MAILU_TEST_CHROMIUM` may specify an existing
Chromium binary; set `MAILU_TEST_INSECURE=1` only for a test server with an
untrusted certificate.

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
