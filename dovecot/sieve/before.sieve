require ["variables", "vacation", "vnd.dovecot.extdata"];

if string :is "${extdata.reply_enabled}" "1" {
  vacation :days 1 :subject "${extdata.reply_subject}" "${extdata.reply_body}";
}

if string :is "${extdata.forward_enabled}" "1" {
  redirect "${extdata.forward_destination}";
  keep;
}
