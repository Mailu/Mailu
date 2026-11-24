---
name: mailu-dev-setup
description: Set up a local development or test environment from a Mailu checkout. Use for previewing the admin UI or docs, building images from source, or running admin and Compose tests. For production setup, use the deployment docs.
---

# Set up Mailu for development

Choose the smallest environment that exercises the requested change:

- **Admin UI, templates, or styling:** run the standalone admin preview.
- **Admin Python, models, views, or API:** run the headless admin tests. These use in-memory SQLite and do not need a running mail stack.
- **SMTP, IMAP, proxy, filtering, or other service interactions:** build the relevant images and use a Compose test stack.
- **Documentation:** build and preview the docs independently.

Work from the Mailu checkout root unless a command changes directories. Check that the container engine is reachable (`docker info`, or `podman info` for the standalone preview). Check `docker buildx version` for Bake and `docker compose version` for integration tests. Use a local engine for commands that bind-mount the checkout. If a prerequisite is unavailable, identify the missing tool or daemon access before attempting a build.

Use the [contributor environment guide](../../../docs/contributors/environment.rst) for context. When defaults differ, follow the scripts, Bake definitions, and Compose files in the current checkout.

## Standalone admin preview

```bash
(cd core/admin && ./run_dev.sh)
```

Run in a terminal: the [helper](../../../core/admin/run_dev.sh) prefers Podman when installed and keeps the container attached. Open `http://127.0.0.1:8080/sso/login/admin` and sign in with `admin@example.com` / `letmein`. Keep the debug server on loopback. If the port or container name is taken, set `DEV_LISTEN=127.0.0.1:8081` or `DEV_NAME` before running the helper.

The helper mounts the admin source and loose assets from the checkout. Rerun it when changing bundled assets or dependencies. It initializes an empty SQLite database by default; `DEV_DB` points to an existing file that the helper can migrate in place. Use a scratch copy for persistent test data. Stop the foreground process with Ctrl-C when finished.

## Local images and headless admin tests

Use [tests/build.hcl](../../../tests/build.hcl) rather than building individual Dockerfiles directly: Bake provides named build contexts such as `base` and `assets`. Preview targets and tags with `docker buildx bake -f tests/build.hcl --print admin`. Build only the targets needed and use `--load` to make the image available to `docker run` and Compose. The local Bake file defaults to `linux/amd64`; on another architecture, check builder support or select a supported native platform with `--set '*.platform=linux/arm64'` (example for ARM64).

The following uses the default local tags. If overriding `DOCKER_ORG`, `DOCKER_PREFIX`, or `MAILU_VERSION`, use the same image namespace and version when running the result. Bake also emits a `latest` tag; use a separate `DOCKER_ORG` for builds on a daemon where those tags are already in use.

```bash
docker buildx bake -f tests/build.hcl --load admin
docker run --rm \
  -v "$PWD/tests:/app/tests:ro" \
  -v "$PWD/core/nginx:/app/core/nginx:ro" \
  -v "$PWD/webmails:/app/webmails:ro" \
  -w /app -e PYTHONDONTWRITEBYTECODE=1 \
  mailu/admin:local \
  sh -c 'pip install --no-cache-dir pytest && python -m pytest -q -p no:cacheprovider tests/anonmail'
```

Narrow `tests/anonmail` to the relevant test file or node ID when iterating. Rebuild `admin` after changing its code: the runner mounts the tests and fixtures, while the app comes from the image. [CI](../../../.github/workflows/build_test_deploy.yml) uses the same setup so tests run against the Python version and dependencies shipped with Mailu. `tests/requirements.txt` is for the Compose runner.

## Compose integration

Use a disposable Linux VM or test host with a local Docker daemon. [The test runner](../../../tests/compose/test.py) uses `/var/run/docker.sock`. Health checks are scoped to the Compose project, but the test files share fixed host ports and subnets. Check for conflicts, run one suite at a time, and start each run with fresh test data.

For example, prepare the `core` stack from the checkout root. Its [Compose file](../../../tests/compose/core/docker-compose.yml) supports `MAILU_ROOT`, so you can keep its fixture certificates and state in a temporary directory:

```bash
docker buildx bake -f tests/build.hcl --load admin front imap smtp antispam oletools resolver
export MAILU_ROOT="$(mktemp -d)"
mkdir "$MAILU_ROOT/certs"
install -m 600 tests/certs/{cert,key}.pem "$MAILU_ROOT/certs/"
```

For an interactive stack, use `docker compose -f tests/compose/core/docker-compose.yml up -d` and check `ps` and service logs. For the automated suite, run the following in the same shell with the stack stopped and fresh state. The runner's health deadline assumes UTC.

```bash
python3 -m venv "$MAILU_ROOT/venv"
. "$MAILU_ROOT/venv/bin/activate"
python -m pip install -r tests/requirements.txt
TZ=UTC python tests/compose/test.py core 2
```

For other suites, check `docker compose -f tests/compose/<suite>/docker-compose.yml config --images` and map Mailu image names to Bake targets (`nginx` → `front`, `dovecot` → `imap`, `postfix` → `smtp`, `rspamd` → `antispam`, `unbound` → `resolver`, `radicale` → `webdav`). Check the suite's volume paths before running it: several hard-code `/mailu`, so `MAILU_ROOT` does not redirect their data. On a disposable host, stage `tests/certs` in the directory expected by the suite, as CI does. Use the timeout from the CI matrix.

The runner normally prints logs and tears down the stack. For a manual run or an interrupted suite, use `docker compose -f tests/compose/core/docker-compose.yml down` (adjust the file for your suite) with the same environment. Remove scratch data created for the run after the stack has stopped.

## Documentation preview

```bash
docker build -t mailu-docs-dev docs
docker run --rm -p 127.0.0.1:8081:80 mailu-docs-dev
```

Open `http://127.0.0.1:8081/master/`. The [docs Dockerfile](../../../docs/Dockerfile) generates the network diagram and runs Sphinx with warnings treated as errors. Rebuild and restart after editing the docs. For a native build, install [docs/requirements.txt](../../../docs/requirements.txt) in a virtual environment, generate `docs/contributors/mailu-network-diagram.svg` with `dot -Tsvg docs/mailu-network-diagram.dot -o docs/contributors/mailu-network-diagram.svg`, then run `sphinx-build -W docs docs/_build/html`.

Report the preview URL and whether it is still running, or the exact suite and result. If setup stops at a missing prerequisite or build error, name the blocker and any verification that did complete.
