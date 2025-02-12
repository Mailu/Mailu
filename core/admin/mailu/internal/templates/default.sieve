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

if header :index 3 :matches "Received" "from * by * for <*>; *"
{
  deleteheader "Delivered-To";
  addheader "Delivered-To" "<${3}>";
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
  vacation :days 1 {% if user.displayed_name != "" %}:from "{{ user.displayed_name | replace("\"", "\\\"") }} <{{ user.email | replace("\"", "\\\"") }}>"{% endif %} :subject "{{ user.reply_subject | replace("\"", "\\\"") }}" "{{ user.reply_body | replace("\"", "\\\"") }}";
}
{% endif %}
