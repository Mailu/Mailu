Introduces postfix logging via rsyslog with these features:
- stdout logging still enabled
- internal test request log messages (healthcheck) are filtered out by rsyslog
- optional logging to file via POSTFIX_LOG_FILE env variable
To use it configure in mailu.env
- ``POSTFIX_LOG_SYSLOG``: (default: ``local``) set to ``local`` (Default) to enable a local syslog server for postfix. Set to ``disable``to disable.
- ``POSTFIX_LOG_FILE``: The file to log the mail log to
Not disabling POSTFIX_LOG_SYSLOG is recommended to get rid of internal healtcheck messages.

