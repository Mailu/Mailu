require "variables";
require "vacation";
require "fileinto";
require "envelope";
require "mailbox";
require "imap4flags";
require "regex";
require "relational";
require "date";
require "comparator-i;ascii-numeric";
require "vnd.dovecot.extdata";
require "vnd.dovecot.execute";
require "spamtestplus";
require "editheader";
require "index";

if header :index 2 :matches "Received" "from * by * for <*>; *"
{
  deleteheader "Delivered-To";
  addheader "Delivered-To" "<${3}>";
}

if allof (string :is "${extdata.spam_enabled}" "1",
          spamtest :percent :value "gt" :comparator "i;ascii-numeric"  "${extdata.spam_threshold}")
{
  setflag "\\seen";
  fileinto :create "Junk";
  stop;
}

if exists "X-Virus" {
  discard;
  stop;
}

if allof (string :is "${extdata.reply_enabled}" "1",
          currentdate :value "le" "date" "${extdata.reply_enddate}")
{
  vacation :days 1 :subject "${extdata.reply_subject}" "${extdata.reply_body}";
}
