Add shared spam maps and show pending greylist messages in the main quarantine
table. Greylisted and rejected copies share a repository while keeping their
separate lifecycle: greylisted copies can be released early, clear when an
accepted retry arrives, and expire after seven days.
