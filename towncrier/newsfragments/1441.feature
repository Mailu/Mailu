Introduces postfix logging via rsyslog with these features:
- stdout logging still enabled
- internal test request log messages are filtered out by rsyslog
- optional logging to file via POSTFIX_LOG_FILE env variable
To use it configure in mailu.env
- ``POSTFIX_LOG_SYSLOG``: (default: ``disabled``) set to ``local`` to enable a local syslog server for postfix
- ``POSTFIX_LOG_FILE``: The file to log the mail log to
Only enabling POSTFIX_LOG_SYSLOG is recommended to get rid of internet test request logging messages.

