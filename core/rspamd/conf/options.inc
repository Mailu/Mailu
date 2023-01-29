{% if RELAYNETS %}
local_networks = [{{ RELAYNETS }},{{ SUBNET }}{% if SUBNET6 %}, {{ SUBNET6 }}{% endif %}];
{% endif %}
