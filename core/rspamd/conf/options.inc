local_networks = [{{ SUBNET | replace(",", ", ") }}{% if SUBNET6 %}, {{ SUBNET6 | replace(",", ", ") }}{% endif %}{% if RELAYNETS %}, {{ RELAYNETS }}{% endif %}];
