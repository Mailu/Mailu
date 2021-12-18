Introduces postfix logging via syslog with these features:
- stdout logging still enabled
- internal test request log messages (healthcheck) are filtered out by rsyslog
- optional logging to file via POSTFIX_LOG_FILE env variable
To use logging to file configure in mailu.env
- ``POSTFIX_LOG_FILE``: The file to log the mail log to
