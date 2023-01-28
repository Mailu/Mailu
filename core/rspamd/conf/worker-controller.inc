type = "controller";
bind_socket = "*:11334";
password = "mailu";
secure_ip = "{{ SUBNET }}";
{%- if SUBNET6 %}
secure_ip = "{{ SUBNET6 }}";
{%- endif %}
