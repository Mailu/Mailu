type = "fuzzy";
bind_socket = "*:11335";
count = 1;
backend = "redis";
expire = 90d;
allow_update = ["127.0.0.1"];
