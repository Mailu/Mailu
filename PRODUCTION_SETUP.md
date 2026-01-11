# Production Deployment Guide - Calapan City Mail Server

## Overview
This document provides instructions for deploying the Mailu mail server to production using **Dokploy** Docker manager.

## Server Details
- **Domain**: mail.lgucalapan.ph
- **Server IP**: 72.60.43.21
- **Environment**: Production
- **Configuration Path**: `/prod/`

## Pre-Deployment Requirements

### 1. DNS Records
Ensure the following DNS records are configured for `lgucalapan.ph`:

```
Type     Host                  Value                      Priority
A        mail.lgucalapan.ph    72.60.43.21                -
MX       lgucalapan.ph         mail.lgucalapan.ph         10
CNAME    autodiscover          mail.lgucalapan.ph         -
CNAME    autoconfig            mail.lgucalapan.ph         -
TXT      _dmarc                v=DMARC1; p=none;          -
SPF      lgucalapan.ph         v=spf1 mx ~all             -
```

### 2. Server Requirements
- Docker & Docker Compose installed
- Dokploy configured and running
- Sufficient disk space for mail storage (/mailu directory)
- Open ports: 25, 80, 110, 143, 443, 465, 587, 993, 995

### 3. SSL/TLS Certificates
- Place certificates in `/mailu/certs/` on the server
- Or configure automatic Let's Encrypt renewal

## Deployment Steps with Dokploy

### Step 1: Push to GitHub
Ensure all changes are committed and pushed to your GitHub repository:

```bash
git add -A
git commit -m "Configure production environment for mail.lgucalapan.ph"
git push origin master
```

### Step 2: Configure Dokploy Project

1. **Login to Dokploy Dashboard** (accessible on your server)
2. **Create New Application**:
   - Select: GitHub repository
   - Choose: Your Mailu repository
   - Branch: `master`

3. **Configure Build Settings**:
   - Docker Compose Path: `/prod/docker-compose.yml`
   - Environment File: `/prod/.env`
   - Build Command: `docker compose -f prod/docker-compose.yml build`
   - Start Command: `docker compose -f prod/docker-compose.yml up -d`

4. **Mount Volumes**:
   - Ensure `/mailu` persistent volume is created
   - Configure auto-restart on failure

5. **Set Environment Variables** (if not using .env file):
   - Copy values from `/prod/.env`

### Step 3: Automatic Deployment

Once configured in Dokploy, the application will:
1. **Automatically trigger** when you push to GitHub
2. **Pull latest code** from the repository
3. **Build and restart** services with the new configuration
4. **Preserve data** in `/mailu` volume (mail, configurations, etc.)

### Step 4: Initial Admin User Setup

After first deployment, create the admin user:

```bash
# SSH into the production server
ssh root@72.60.43.21

# Navigate to mailu directory
cd /path/to/mailu

# Create admin user
docker compose -f /path/to/prod/docker-compose.yml exec admin flask mailu admin admin@lgucalapan.ph $(openssl rand -base64 32)
```

## Production Configuration Details

### Current Settings (`prod/.env`):
- **Domain**: `lgucalapan.ph`
- **Hostname**: `mail.lgucalapan.ph`
- **Sitename**: `Calapan City Mail`
- **Webmail**: SnappyMail (lightweight, fast)
- **Antivirus**: ClamAV enabled
- **Message Size**: 50MB
- **Logo**: Custom Calapan City Logo

### Services Enabled:
- ✅ Admin Panel (with custom logo)
- ✅ Webmail (with custom logo)
- ✅ SMTP (Postfix)
- ✅ IMAP (Dovecot)
- ✅ Antispam (Rspamd)
- ✅ Antivirus (ClamAV)
- ✅ DNS Resolver (Unbound)
- ✅ Redis cache

## Accessing Services

After deployment:

- **Admin Panel**: http://mail.lgucalapan.ph/admin
  - Login with admin@lgucalapan.ph
  
- **Webmail**: http://mail.lgucalapan.ph/webmail
  - Users can access their email
  
- **SMTP/IMAP**: mail.lgucalapan.ph (ports: 25, 110, 143, 465, 587, 993, 995)

## Monitoring & Logs

### View Logs in Dokploy:
1. Navigate to your application
2. Click "Logs" tab
3. Select the service (admin, webmail, smtp, etc.)

### Manual Log Access via SSH:
```bash
# View all service logs
docker compose -f /path/to/prod/docker-compose.yml logs -f

# View specific service
docker compose -f /path/to/prod/docker-compose.yml logs -f admin
```

## Backup Strategy

### Daily Backups (Recommended):
```bash
# Create backup script
cat > /etc/cron.daily/mailu-backup << 'EOF'
#!/bin/bash
BACKUP_DIR="/backups/mailu"
mkdir -p $BACKUP_DIR
tar -czf $BACKUP_DIR/mailu-$(date +%Y-%m-%d).tar.gz /mailu
# Keep only last 30 days
find $BACKUP_DIR -type f -mtime +30 -delete
EOF

chmod +x /etc/cron.daily/mailu-backup
```

### Backup Items:
- `/mailu/data/` - Database and user data
- `/mailu/dkim/` - DKIM keys (critical!)
- `/mailu/mail/` - Email storage
- Certificates in `/mailu/certs/`

## Maintenance

### Updates via Dokploy:
1. New version available → Update `VERSION` in `prod/.env`
2. Push changes to GitHub
3. Dokploy automatically triggers rebuild and deployment
4. No downtime required (containers restart gracefully)

### Database Maintenance:
```bash
# Run database optimization
docker compose -f /path/to/prod/docker-compose.yml exec admin flask mailu db upgrade
```

## Troubleshooting

### Services won't start:
```bash
# Check logs
docker compose -f prod/docker-compose.yml logs admin

# Restart specific service
docker compose -f prod/docker-compose.yml restart admin
```

### Logo not displaying:
- Verify: `/Calapan_City_Logo.png` exists in repository root
- Check: LOGO_URL=/static/mailu.png in `.env`
- Clear browser cache

### Mail not receiving:
- Check DNS MX records point to mail.lgucalapan.ph
- Verify DNSSEC validation is disabled (SKIP_DNSSEC_CHECKS=False in prod)
- Check firewall allows port 25

### SSL Certificate issues:
- Ensure TLS_FLAVOR=cert in `.env`
- Place certificates in `/mailu/certs/`
- Certificate files should be: `cert.pem` and `key.pem`

## Security Notes

⚠️ **IMPORTANT**: 
- Change `SECRET_KEY` in `prod/.env` to a secure random string
- Never commit `.env` with real secrets to public repositories
- Use strong passwords for admin accounts
- Enable 2FA on admin accounts
- Regularly update `VERSION` for security patches
- Monitor mail logs for suspicious activity

## Support

For Mailu documentation: https://mailu.io/
For issues: https://github.com/Mailu/Mailu/issues

---

**Last Updated**: January 2026
**Deployment Method**: Dokploy (GitHub auto-deployment)
**Server**: 72.60.43.21
