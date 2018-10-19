type = "controller";
bind_socket = "*:11334";
{% if RSPAMD_PASSWORD %}
password = "{{ RSPAMD_PASSWORD }}";
{% else %}
password = "mailu";
{% endif %}
secure_ip = "{% if POD_ADDRESS_RANGE %}{{ POD_ADDRESS_RANGE }}{% else %}{{ FRONT_ADDRESS }}{% endif %}";
