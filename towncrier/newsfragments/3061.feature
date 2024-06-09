Introduce new settings for configuring proxying and TLS. Disable POP3, IMAP and SUBMISSION by default, see https://nostarttls.secvuln.info/
- Drop TLS_FLAVOR=mail-*
- Change the meaning of PROXY_PROTOCOL, introduce PORTS
- Disable POP3, IMAP and SUBMISSION ports by default, to re-enable ensure PORTS include 110, 143 and 587

MANAGESIEVE with implicit TLS is not a thing clients support... so 4190 is enabled by default.
