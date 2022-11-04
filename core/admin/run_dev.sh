#!/usr/bin/env bash

set -euxo pipefail

### CONFIG

DEV_PORT="${DEV_PORT:-8080}"
DEV_NAME="${DEV_NAME:-mailu-dev}"
DEV_PROFILE="${DEV_PROFILE:-false}"


### MAIN

docker="$(command -v podman || command -v docker || echo false)"
[[ "${docker}" == "false" ]] && {
	echo "Sorry, you'll need podman or docker to run this."
	exit 1
}

here="$(realpath "$(pwd)/${0%/*}")"
cd "${here}"

# TODO: use /tmp/... folder
[[ -d dev ]] && rm -rf dev
mkdir -p dev/data || exit 1

# base
cp ../base/requirements-* dev/
cp -r ../base/libs dev/
sed -E '/^#/d;s:^FROM system$:FROM system AS base:' ../base/Dockerfile > dev/Dockerfile

# assets
cp -r assets/content dev/
sed -E '/^#/d;s:^(FROM [^ ]+$):\1 AS assets:' assets/Dockerfile >> dev/Dockerfile

cat >> dev/Dockerfile <<EOF
RUN set -euxo pipefail \
  ; rm -f /work/static/*.gz
EOF

# admin
sed -E '/^#/d;/^(COPY|EXPOSE|HEALTHCHECK|VOLUME|CMD) /d; s:^(.* )[^ ]*pybabel[^\\]*(.*):\1true \2:' Dockerfile >> dev/Dockerfile

DEV_URI="http://"
[[ "${DEV_PORT}" == *:* ]] || DEV_URI="${DEV_URI}localhost:"
DEV_URI="${DEV_URI}${DEV_PORT}/admin/ui/"

MSG="\\n======================================================================\\nUI is found here: ${DEV_URI}\\nLog in with: admin@example.com and password admin if this is a new DB.\\n======================================================================\\n"

cat >> dev/Dockerfile <<EOF
COPY --from=assets /work/static/ ./static/

RUN set -euxo pipefail \
  ; ln -s /app/audit.py / \
  ; ln -s /app/start.py /

ENV FLASK_ENV=development
ENV MEMORY_SESSIONS=true
ENV SESSION_COOKIE_SECURE=false

ENV DEBUG=true
ENV DEBUG_PROFILE=${DEV_PROFILE}
ENV DEBUG_ASSETS=/app/static
ENV DEBUG_TB_ENABLED=true

ENV IMAP_ADDRESS="127.0.0.1"
ENV POP3_ADDRESS="127.0.0.1"
ENV AUTHSMTP_ADDRESS="127.0.0.1"
ENV SMTP_ADDRESS="127.0.0.1"
ENV REDIS_ADDRESS="127.0.0.1"
ENV WEBMAIL_ADDRESS="127.0.0.1"

CMD ["/bin/bash", "-c", "flask db upgrade &>/dev/null && flask mailu admin admin example.com admin --mode ifmissing >/dev/null && echo -e '${MSG}' 1>&2 && flask run --host=0.0.0.0 --port=8080"]
EOF

# TODO: re-compile assets on change?
# TODO: re-run babel on change?

# build
chmod -R u+rwX,go+rX dev/
"${docker}" build --tag "${DEV_NAME}:latest" dev/

# run
args=( --rm -it --name "${DEV_NAME}" --publish "${DEV_PORT}:8080" --volume "${here}/dev/data/:/data/" )
for vol in audit.py start.py mailu/ migrations/; do
	args+=( --volume "${here}/${vol}:/app/${vol}" )
done

for file in "${here}"/assets/content/assets/*; do
	[[ "${file}" == */vendor.js ]] && continue
	args+=( --volume "${file}:/app/static/${file/*\//}" )
done

"${docker}" run "${args[@]}" "${DEV_NAME}"

# TODO: remove dev folder?
