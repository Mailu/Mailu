type = "controller";
bind_socket = "*:11334";
password = "mailu";
secure_ip = "{{ POD_ADDRESS_RANGE or SUBNET }}{% if SUBNET6 %},{{ SUBNET6 }}{% endif %}";
