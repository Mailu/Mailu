require ["variables", "vacation", "vnd.dovecot.extdata"];

if ${extdata.reply_enabled} {
  vacation :days 1 :subject "${extdata.reply_subject}" "${extdata.reply_body}";
}

if ${extdata.forward_enabled} {
  redirect "${extdata.forward_destination}";
  keep;
}
