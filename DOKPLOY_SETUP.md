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

You can choose one of the following:
- Recommended: Copy variables from [prod/.env](prod/.env) into Dokploy’s **Environment** tab (safer for secrets), or
- Quick start: Keep [prod/.env](prod/.env) in the repo (already present), and update values via commits.

Critical values to review in production:
- `SECRET_KEY` — replace with a secure random string
- `DOMAIN=lgucalapan.ph`
- `HOSTNAMES=mail.lgucalapan.ph`
- `SITENAME=Calapan City Mail`
- `LOGO_URL=/static/mailu.png`
- `COMPOSE_PROJECT_NAME=calapan-mailu`

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
- Admin Panel: `https://mail.lgucalapan.ph/admin`
- Webmail: `https://mail.lgucalapan.ph/webmail`

Quick checks:
```bash
curl -I https://mail.lgucalapan.ph/admin
curl -I https://mail.lgucalapan.ph/webmail
nc -zv mail.lgucalapan.ph 25
```

---

## Notes
- The admin logo is mounted by compose: the file `Calapan_City_Logo.png` becomes `/static/mailu.png` via the admin container’s static path and `LOGO_URL=/static/mailu.png`.
- The compose file already maps the Roundcube/SnappyMail logo where applicable.
- Autodeploy with **Trigger Type: On Push** will rebuild/restart whenever you push to `master`. Limiting **Watch Paths** to `prod/**` reduces unnecessary deploys.

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
