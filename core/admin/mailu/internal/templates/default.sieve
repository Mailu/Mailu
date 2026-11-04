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

# Postfix adds X-Original-To for LMTP; Dovecot exposes it as envelope "to".
if envelope :matches "to" "*"
{
  deleteheader "Delivered-To";
  addheader "Delivered-To" "<${1}>";
}

{% if user.spam_enabled %}
if spamtest :percent :value "gt" :comparator "i;ascii-numeric" "{{ user.spam_threshold }}"
{
  {% if user.spam_mark_as_read %}
  setflag "\\seen";
  {% endif %}
  fileinto :create "Junk";
  stop;
}
{% endif %}

{% if user.reply_active %}
if not address :localpart :contains ["From","Reply-To"] ["noreply","no-reply"]{
  vacation :days 1 {% if user.displayed_name != "" %}:from "\"{{ user.displayed_name | sieve_string }}\" <{{ user.email | sieve_string }}>"{% endif %} :subject "{{ (user.reply_subject or '') | sieve_string }}" {% if user.reply_body_html %}:mime "{{ user.reply_mime | sieve_string }}"{% else %}"{{ (user.reply_body or '') | sieve_string }}"{% endif %};
}
{% endif %}
