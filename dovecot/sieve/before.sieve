require ["variables", "vacation", "vnd.dovecot.extdata"];

if string :is "${extdata.reply_subject}" "" {

} else {
  vacation :days 1 :subject "${extdata.reply_subject}" "${extdata.reply_body}";
}

if string :is "${extdata.forward}" "" {

} else {
  redirect "${extdata.forward}";
  keep;
}
