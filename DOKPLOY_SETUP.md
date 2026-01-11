# Dokploy Service Setup (Compose: Docker Compose)

This guide matches Dokploy’s current Service UI (Compose → Docker Compose) and maps each field to this repository.

## Prerequisites
- Dokploy running on 72.60.43.21
- GitHub access to repository: `bonitobonita24/mailserver-lgucalapanph`
- DNS records prepared for `lgucalapan.ph`

---

## Create Service (Compose → Docker Compose)

Inside your Project, click **Create Service** and choose:
- **Type**: Compose
- **Compose Type**: Docker Compose

### Provider section (as in the screenshot)
- **Source**: GitHub
- **GitHub Account**: Select your account
- **Repository**: `bonitobonita24/mailserver-lgucalapanph`
- **Branch**: `master`
- **Compose Path**: `./prod/docker-compose.yml`
- **Trigger Type**: `On Push`
- **Watch Paths** (optional): `prod/**`  
  Use this to trigger only when production files change.
- **Enable Submodules**: Off (unless you use them)
- **Autodeploy**: On
- Click **Save**

This uses the production compose file at [prod/docker-compose.yml](prod/docker-compose.yml).

---

## Environment tab

Our compose services reference an env file with `env_file: .env`. Because the **Compose Path** is `./prod/docker-compose.yml`, the `.env` it refers to is [prod/.env](prod/.env).

Important: Docker Compose variable interpolation (e.g. `${VERSION}` and `${ROOT}` in images and volumes) reads from the **Service Environment** in Dokploy, not from `env_file`. To avoid blank tags and missing mounts, set these in the **Environment** tab:

Required variables for Compose resolution:
- `VERSION=2024.06`
- `ROOT=/mailu`
- `SUBNET=192.168.203.0/24`

Application variables (used by containers at runtime):
- `SECRET_KEY` — set a secure random string
- `DOMAIN=lgucalapan.ph`
- `HOSTNAMES=mail.lgucalapan.ph`
- `SITENAME=Calapan City Mail`
- `LOGO_URL=/static/mailu.png`
- `LOGO_BACKGROUND=#0D47A1`
- `COMPOSE_PROJECT_NAME=calapan-mailu`
- (Optional) `POSTMASTER=admin`, `TLS_FLAVOR=cert`, `AUTH_RATELIMIT=5/minute`, `DISABLE_STATISTICS=False`, `ADMIN=true`, `WEBMAIL=roundcube`, `WEBDAV=none`, `ANTIVIRUS=none`, `SKIP_DNSSEC_CHECKS=true`

Tip: You may still keep [prod/.env](prod/.env) for reference, but Dokploy’s **Environment** tab should contain the values above so builds and mounts work.

Common error and fix:
- If logs show warnings like `The "VERSION" variable is not set` or `Detected: 0 mounts`, set `VERSION`, `ROOT`, and `SUBNET` in the Environment tab, then redeploy.

### Environment quick-paste (Dokploy → Service → Environment)
Copy these into the Environment tab so Compose interpolation and runtime config both work:

```env
VERSION=2024.06
ROOT=/mailu
SUBNET=192.168.203.0/24

SECRET_KEY=CHANGE_ME_TO_A_SECURE_RANDOM_VALUE
DOMAIN=lgucalapan.ph
HOSTNAMES=mail.lgucalapan.ph
SITENAME=Calapan City Mail
LOGO_URL=/static/mailu.png
LOGO_BACKGROUND=#0D47A1
COMPOSE_PROJECT_NAME=calapan-mailu

# Optional but recommended for parity with prod/.env
POSTMASTER=admin
TLS_FLAVOR=cert
AUTH_RATELIMIT=5/minute
DISABLE_STATISTICS=False
ADMIN=true
WEBMAIL=roundcube
WEBDAV=none
ANTIVIRUS=none
SKIP_DNSSEC_CHECKS=true
```

### Service UI field checklist
- Source: GitHub
- Repository: `bonitobonita24/mailserver-lgucalapanph`
- Branch: `master`
- Compose Path: `./prod/docker-compose.yml`
- Trigger Type: `On Push`
- Watch Paths: `prod/**` (optional)
- Autodeploy: `On`

---

## Deploy section
- Toggle **Autodeploy** ON
- Click **Deploy** to start the stack
- Use **Logs** to watch service output (admin, webmail, smtp, imap, antispam, antivirus, resolver, redis)

---

## DNS and TLS
- A: `mail.lgucalapan.ph` → `72.60.43.21`
- MX: `lgucalapan.ph` → `mail.lgucalapan.ph` (priority 10)
- SPF: `v=spf1 mx ~all`
- DMARC: `_dmarc` → `v=DMARC1; p=none;`
- Certificates: Place in `/mailu/certs/` or use Let’s Encrypt (TLS_FLAVOR=cert)

---

## First admin user
After the services are up, create the admin account:

```bash
ssh root@72.60.43.21
docker compose -f /path/to/prod/docker-compose.yml exec admin \
  flask mailu admin admin@lgucalapan.ph $(openssl rand -base64 32)
```

---

## Verify
- Admin Panel: `https://mail.lgucalapan.ph:8443/admin` (or `http://mail.lgucalapan.ph:8080/admin`)
- Webmail: `https://mail.lgucalapan.ph:8443/webmail`

Note: Currently using ports 8080 (HTTP) and 8443 (HTTPS) to avoid conflict with Dokploy's reverse proxy on ports 80/443. For production with proper domain routing through Dokploy's Traefik, see "Traefik Integration" section below.

Quick checks:
```bash
curl -I http://mail.lgucalapan.ph:8080/admin
curl -I http://mail.lgucalapan.ph:8080/webmail
nc -zv mail.lgucalapan.ph 25
```

---

## Notes
- The admin logo is mounted by compose: the file `Calapan_City_Logo.png` becomes `/static/mailu.png` via the admin container’s static path and `LOGO_URL=/static/mailu.png`.
- The compose file already maps the Roundcube/SnappyMail logo where applicable.
- Autodeploy with **Trigger Type: On Push** will rebuild/restart whenever you push to `master`. Limiting **Watch Paths** to `prod/**` reduces unnecessary deploys.

---

## Traefik Integration (Optional - For Production Domain Routing)

If you want to access the mail server via standard ports (80/443) through Dokploy's Traefik reverse proxy:

1. **Remove port bindings** for 80/443 from `docker-compose.yml`:
   ```yaml
   ports:
     # - "8080:80"   # Comment these out
     # - "8443:443"
     - "110:110"     # Keep mail ports
   ```

2. **Configure Dokploy Domains** in the Service settings:
   - Add domain: `mail.lgucalapan.ph`
   - Container: `front`
   - Container Port: `80`
   - SSL: Enable Let's Encrypt

3. Traefik will handle SSL termination and route traffic to the front container.

---

## Troubleshooting
```bash
# Show admin logs
docker compose -f prod/docker-compose.yml logs -f admin

# Restart a service
docker compose -f prod/docker-compose.yml restart admin

# Check running containers
docker ps | grep calapan
```

---

Generated: January 2026
