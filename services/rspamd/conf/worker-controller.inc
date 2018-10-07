bind_socket = "*:11334";
password = "mailu";
secure_ip = "{% if POD_ADDRESS_RANGE %}{{ POD_ADDRESS_RANGE }}{% else %}{{ FRONT_ADDRESS }}{% endif %}";
