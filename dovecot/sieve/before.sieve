require "variables";
require "vacation";
require "fileinto";
require "envelope";
require "mailbox";
require "imap4flags";
require "regex";
require "relational";
require "comparator-i;ascii-numeric";
require "vnd.dovecot.extdata";

if allof (string :is "${extdata.spam_enabled}" "1",
          not header :matches "X-Spam-Status" "* score=-*",
          header :matches "X-Spam-Status" "* score=*")
{
  if string :value "ge" :comparator "i;ascii-numeric" "${2}" "${extdata.spam_threshold}" {
    setflag "\\seen";
    fileinto :create "Junk";
    stop;
  }
}

if string :is "${extdata.reply_enabled}" "1" {
  vacation :days 1 :subject "${extdata.reply_subject}" "${extdata.reply_body}";
}

if string :is "${extdata.forward_enabled}" "1" {
  redirect "${extdata.forward_destination}";
  keep;
}
