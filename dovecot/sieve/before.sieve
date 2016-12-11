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
require "vnd.dovecot.execute";
require "spamtestplus";

if allof (string :is "${extdata.spam_enabled}" "1",
          spamtest :percent :value "gt" :comparator "i;ascii-numeric"  "${extdata.spam_threshold}")
{
  setflag "\\seen";
  fileinto :create "Junk";
  stop;
}

if string :is "${extdata.reply_enabled}" "1" {
  vacation :days 1 :subject "${extdata.reply_subject}" "${extdata.reply_body}";
}

if string :is "${extdata.forward_enabled}" "1" {
  execute :pipe "forward" "${extdata.forward_destination}";
  keep;
}
