require ["variables", "vacation", "fileinto", "envelope", "mailbox", "imap4flags", "regex", "relational", "comparator-i;ascii-numeric", "vnd.dovecot.extdata"];

if string :is "${extdata.spam_enabled}" "1" {
  if header :matches "X-Spam-Status" "* score=*" {
    if string :value "ge" :comparator "i;ascii-numeric" "${2}" "${extdata.spam_threshold}" {
      setflag "\\seen";
      fileinto :create "Junk";
      stop;
    }
  }
}

if string :is "${extdata.reply_enabled}" "1" {
  vacation :days 1 :subject "${extdata.reply_subject}" "${extdata.reply_body}";
}

if string :is "${extdata.forward_enabled}" "1" {
  redirect "${extdata.forward_destination}";
  keep;
}
