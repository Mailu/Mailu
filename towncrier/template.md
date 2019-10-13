{% for section, _ in sections.items() %}
{% set underline = underlines[0] %}{% if section %}{{section}}
{{ underline * section|length }}{% set underline = underlines[1] %}

{% endif %}

{% if sections[section] %}
{% for category, val in definitions.items() if category in sections[section]%}
{% for text, values in sections[section][category].items() %}
- {{ definitions[category]['name'] }}: {{ text }} ({{ values|join(', ') }})
{% endfor %}
{% endfor %}

{% endif %}
{% endfor %}
