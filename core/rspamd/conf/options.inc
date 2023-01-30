local_networks = [{{ SUBNET }}{% if SUBNET6 %}, {{ SUBNET6 }}{% endif %}{% if RELAYNETS %}, {{ RELAYNETS }}{% endif %}];
