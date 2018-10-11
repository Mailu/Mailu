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
require "spamtestplus";
require "editheader";
require "index";

if header :index 2 :matches "Received" "from * by * for <*>; *"
{
  deleteheader "Delivered-To";
  addheader "Delivered-To" "<${3}>";
}

{% if user.spam_enabled %}
if spamtest :percent :value "gt" :comparator "i;ascii-numeric"  "{{ user.spam_threshold }}"
{
  setflag "\\seen";
  fileinto :create "Junk";
  stop;
}
{% endif %}

if exists "X-Virus" {
  discard;
  stop;
}

{% if user.reply_enabled %}
if currentdate :value "le" "date" "{{ user.reply_enddate }}"
{
 vacation :days 1 :subject "{{ user.reply_subject }}" "{{ user.reply_body }}";
}
{% endif %}
