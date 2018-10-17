bind_socket = "*:11334";
{% if RSPAMD_PASSWORD %}
password = "{{ RSPAMD_PASSWORD }}";
{% else %}
password = "mailu";
{% endif %}
secure_ip = "{{ FRONT_ADDRESS }}";
