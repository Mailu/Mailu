#!/bin/bash

# get id of running admin container
admin="$(docker compose ps admin --format=json | jq -r '.[].ID')"
if [[ -z "${admin}" ]]; then
	echo "Sorry, can't find running mailu admin container."
	echo "You need to start this in the path containing your docker-compose.yml."
	exit 1
fi

# get storage path
storage="$(
	docker inspect "${admin}" \
	| jq -r '.[].Mounts[] | select(.Destination == "/data") | .Source'
)/.."
storage="$(realpath "${storage}")"
if [[ ! -d "${storage}" ]]; then
	echo "Sorry, can't find mailu storage path."
	exit 2
fi

# fetch list of users from admin
declare -A users=()
while read line; do
	users[${line#* }]="${line/ *}"
done < <(
	docker compose exec -T admin \
		flask mailu config-export -j user.email user.enabled \
	2>/dev/null | jq -r '.user[] | "\(.enabled) \(.email)"'
)
if [[ ${#users[@]} -eq 0 ]]; then
	echo "mailu config-export returned no users. Aborted."
	exit 3
fi

# diff list of users <> storage
unknown=false
disabled=false
for maildir in "${storage}"/mail/*; do
	[[ -d "${maildir}" ]] || continue
	email="${maildir/*\/}"
	enabled="${users[${email}]:-}"
	if [[ -z "${enabled}" ]]; then
		unknown=true
		users[${email}]="unknown"
	elif ${enabled}; then
		unset users[${email}]
	else
		disabled=true
		users[${email}]="disabled"
	fi
done

if [[ ${#users[@]} -eq 0 ]]; then
	echo "Nothing to clean up."
	exit 0
fi

# is roundcube webmail in use?
webmail=false
docker compose exec webmail test -e /data/roundcube.db 2>/dev/null && webmail=true

# output actions
if ${unknown}; then
	echo "# To delete maildirs unknown to mailu, run:"
	for email in "${!users[@]}"; do
		[[ "${users[${email}]}" == "unknown" ]] || continue
		echo -n "rm -rf '${storage}/mail/${email}'"
		${webmail} && \
			echo -n " && docker compose exec -T webmail su mailu -c \"/var/www/roundcube/bin/deluser.sh --host=front '${email}'\""
		echo
	done
	echo
fi
if ${disabled}; then
	echo "# To purge disabled users, run:"
	for email in "${!users[@]}"; do
		[[ "${users[${email}]}" == "disabled" ]] || continue
		echo -n "docker compose exec -T admin flask mailu user-delete -r '${email}' && rm -rf '${storage}/mail/${email}'"
		${webmail} && \
			echo -n " && docker compose exec -T webmail su mailu -c \"/var/www/roundcube/bin/deluser.sh --host=front '${email}'\""
		echo
	done
	echo
fi
