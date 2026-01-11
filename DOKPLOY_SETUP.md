# Quick Dokploy Setup Guide

## 🚀 5-Minute Dokploy Configuration

### Prerequisites
- Dokploy installed and running on 72.60.43.21
- GitHub account with access to `bonitobonita24/mailserver-lgucalapanph`
- Domain `lgucalapan.ph` with DNS configured

---

## Step 1: Create New Application in Dokploy

1. Open Dokploy Dashboard
2. Click **"Create Application"** or **"New Project"**
3. Select **GitHub** as source
4. Click **"Authenticate with GitHub"** (if not already)

---

## Step 2: Configure Repository

- **Repository**: `bonitobonita24/mailserver-lgucalapanph`
- **Branch**: `master`
- **Root Directory**: Leave blank (or `.` for root)

---

## Step 3: Set Build Configuration

### Build Settings:
| Field | Value |
|-------|-------|
| **Build Command** | `docker compose -f prod/docker-compose.yml build` |
| **Start Command** | `docker compose -f prod/docker-compose.yml up -d` |
| **Stop Command** | `docker compose -f prod/docker-compose.yml down` |
| **Compose File** | `prod/docker-compose.yml` |

---

## Step 4: Environment Variables

Click **"Add Environment Variable"** and copy from `prod/.env`:

| Variable | Value |
|----------|-------|
| `ROOT` | `/mailu` |
| `VERSION` | `2024.06` |
| `SECRET_KEY` | `<generate-new-secure-key>` |
| `DOMAIN` | `lgucalapan.ph` |
| `HOSTNAMES` | `mail.lgucalapan.ph` |
| `SITENAME` | `Calapan City Mail` |
| `LOGO_URL` | `/static/mailu.png` |
| `LOGO_BACKGROUND` | `#0D47A1` |
| `COMPOSE_PROJECT_NAME` | `calapan-mailu` |

*See `prod/.env` for complete list of variables*

---

## Step 5: Configure Volumes

Click **"Add Volume"** and create:

| Volume Name | Mount Path | Purpose |
|------------|-----------|---------|
| `mailu-data` | `/mailu/data` | Database & configs |
| `mailu-mail` | `/mailu/mail` | Email storage |
| `mailu-certs` | `/mailu/certs` | SSL certificates |
| `mailu-dkim` | `/mailu/dkim` | DKIM keys |
| `mailu-filter` | `/mailu/filter` | Antispam data |
| `mailu-redis` | `/mailu/redis` | Redis cache |
| `mailu-webmail` | `/mailu/webmail` | Webmail data |

---

## Step 6: Configure Ports

Expose the following ports:

| Port | Protocol | Service |
|------|----------|---------|
| `25` | TCP | SMTP |
| `80` | TCP | HTTP (nginx) |
| `110` | TCP | POP3 |
| `143` | TCP | IMAP |
| `443` | TCP | HTTPS (nginx) |
| `465` | TCP | SMTPS |
| `587` | TCP | Submission |
| `993` | TCP | IMAPS |
| `995` | TCP | POP3S |

---

## Step 7: Advanced Settings

### Auto-restart:
- ✅ Enable **"Restart Policy"** → `unless-stopped`
- ✅ Enable **"Auto-restart on failure"**

### Logging:
- ✅ Enable **"JSON File Logging"**
- ✅ Set max size to `10m` to prevent disk bloat

### GitHub Webhook:
- ✅ Enable **"Auto-deploy on push"**
- ✅ Branch: `master`
- This makes deployments automatic when code is pushed!

---

## Step 8: Deploy

Click **"Deploy"** or **"Build & Deploy"**

Watch the logs:
```
Building images...
Starting services...
Initializing database...
✓ Deployment successful
```

---

## Step 9: SSH Into Server & Create Admin

After deployment succeeds:

```bash
# SSH to server
ssh root@72.60.43.21

# Create admin user (generates random password)
docker compose -f /path/to/prod/docker-compose.yml \
  exec admin \
  flask mailu admin admin@lgucalapan.ph $(openssl rand -base64 32)
```

---

## Step 10: Test Services

### Test Admin Panel:
```bash
curl -I https://mail.lgucalapan.ph/admin
# Should return: HTTP/2 302 (redirect to login)
```

### Test Webmail:
```bash
curl -I https://mail.lgucalapan.ph/webmail
# Should return: HTTP/2 200
```

### Test SMTP:
```bash
nc -zv mail.lgucalapan.ph 25
# Should return: Connection successful
```

---

## Troubleshooting

### Services won't start:
```bash
# SSH to server
ssh root@72.60.43.21

# Check logs
docker compose -f prod/docker-compose.yml logs -f admin

# Restart
docker compose -f prod/docker-compose.yml restart
```

### Logo not showing:
- ✅ Verify file exists: `../Calapan_City_Logo.png`
- ✅ Check docker-compose volume mounts
- ✅ Clear browser cache (Ctrl+Shift+Delete)

### Port already in use:
```bash
# Check what's using the port
lsof -i :25  # or other port
kill -9 <PID>
```

---

## Automatic Updates via GitHub

Now whenever you push to `master`:

1. GitHub webhook triggers Dokploy
2. Dokploy pulls latest code
3. Docker images rebuild
4. Services restart automatically
5. `/mailu` volume persists all data

**Example workflow:**
```bash
# Make changes locally
git add .
git commit -m "Update mail config"
git push origin master

# Dokploy automatically:
# → Rebuilds images
# → Restarts containers
# → No manual deployment needed!
```

---

## Monitoring

### View Logs in Dokploy:
1. Open application dashboard
2. Click **"Logs"** tab
3. Select service: `admin`, `webmail`, `smtp`, `imap`, etc.
4. Watch real-time logs

### Check Service Status:
```bash
ssh root@72.60.43.21
docker ps | grep calapan
```

---

## Backup & Maintenance

### Daily Backup Script:
```bash
cat > /etc/cron.daily/mailu-backup << 'EOF'
#!/bin/bash
BACKUP_DIR="/backups/mailu"
mkdir -p $BACKUP_DIR
tar -czf $BACKUP_DIR/mailu-$(date +%Y-%m-%d).tar.gz /mailu
find $BACKUP_DIR -type f -mtime +30 -delete  # Keep 30 days
EOF

chmod +x /etc/cron.daily/mailu-backup
```

### Update Mailu Version:
1. Edit `prod/.env` and change `VERSION`
2. Push to GitHub
3. Dokploy automatically rebuilds with new version

---

## Support Resources

- **Mailu Docs**: https://mailu.io/
- **Dokploy Docs**: https://dokploy.com/
- **GitHub Repo**: https://github.com/Mailu/Mailu
- **Issues**: https://github.com/Mailu/Mailu/issues

---

**✨ Your mail server is now production-ready!**

**Domain**: mail.lgucalapan.ph  
**IP**: 72.60.43.21  
**Auto-deployment**: Enabled via GitHub  
**Logo**: Calapan City Logo configured  

---

*Generated: January 2026*
