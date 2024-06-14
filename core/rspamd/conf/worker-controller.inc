type = "controller";
bind_socket = "*:11334";
password = "mailu";
{% for e in SUBNET.split(",") %}
secure_ip = "{{ e }}";
{% endfor %}
{%- if SUBNET6 %}
{% for e in SUBNET6.split(",") %}
secure_ip = "{{ e }}";
{% endfor %}
{%- endif %}
