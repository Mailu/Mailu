require ["variables", "fileinto", "envelope", "mailbox", "imap4flags", "regex", "relational", "comparator-i;ascii-numeric", "vnd.dovecot.extdata"];


if string :is "${extdata.spam_enabled}" "1" {
  if header :matches "X-Spam-Status" "* score=*" {
    if string :value "ge" :comparator "i;ascii-numeric" "${2}" "${extdata.spam_threshold}" {
      setflag "\\seen";
      fileinto :create "Junk";
      stop;
    }
  }
}
