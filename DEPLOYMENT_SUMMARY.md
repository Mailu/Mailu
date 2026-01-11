# Production Deployment Configuration Summary

## ✅ Setup Complete for mail.lgucalapan.ph

### Production Server Details
- **Domain**: lgucalapan.ph
- **Mail Server**: mail.lgucalapan.ph
- **Server IP**: 72.60.43.21
- **Deployment Method**: Dokploy (GitHub auto-deployment)
- **Configuration Path**: `/prod/`

---

## 📋 Configuration Files Updated

### 1. **`prod/.env`** - Production Environment Variables
```
DOMAIN=lgucalapan.ph
HOSTNAMES=mail.lgucalapan.ph
SITENAME=Calapan City Mail
LOGO_URL=/static/mailu.png
LOGO_BACKGROUND=#0D47A1
COMPOSE_PROJECT_NAME=calapan-mailu
```

### 2. **`prod/docker-compose.yml`** - Docker Services
- Added custom logo mount to **admin** service
  - `../Calapan_City_Logo.png:/app/mailu/static/mailu.png:ro`
- Added auth API and logo mount to **webmail** service
  - Includes mailu.php plugin for password change feature
  - Includes custom logo configuration

### 3. **Services Enabled**
- ✅ Admin Panel (with Calapan City Logo)
- ✅ Webmail - SnappyMail (with Calapan City Logo)
- ✅ SMTP (Postfix)
- ✅ IMAP (Dovecot)
- ✅ Antispam (Rspamd)
- ✅ Antivirus (ClamAV)
- ✅ DNS Resolver (Unbound)
- ✅ Redis Cache

---

## 🚀 Deployment with Dokploy

### Step 1: Dokploy Configuration
1. Log into your Dokploy Dashboard
2. Create new application
3. Connect your GitHub repository
4. Select branch: `master`

### Step 2: Build Settings
- **Docker Compose Path**: `prod/docker-compose.yml`
- **Environment File**: Use values from `prod/.env`
- **Build Command**: `docker compose -f prod/docker-compose.yml build`
- **Start Command**: `docker compose -f prod/docker-compose.yml up -d`

### Step 3: Automatic Deployment
- When you push to `master` branch → Dokploy automatically:
  1. Pulls latest code from GitHub
  2. Builds Docker images
  3. Restarts services with new configuration
  4. Preserves `/mailu` volume (email data, configs, DKIM keys)

### Step 4: SSH Into Server
```bash
ssh root@72.60.43.21
cd /path/to/mailu  # or wherever Dokploy clones the repo
```

### Step 5: Create Admin User (First Time)
```bash
docker compose -f prod/docker-compose.yml exec admin flask mailu admin admin@lgucalapan.ph $(openssl rand -base64 32)
```

---

## 📍 Accessing Services

Once deployed to production:

| Service | URL | Port |
|---------|-----|------|
| Admin Panel | `https://mail.lgucalapan.ph/admin` | 443 |
| Webmail | `https://mail.lgucalapan.ph/webmail` | 443 |
| SMTP | mail.lgucalapan.ph | 25, 465, 587 |
| IMAP | mail.lgucalapan.ph | 143, 993 |
| POP3 | mail.lgucalapan.ph | 110, 995 |

---

## 🔐 Security Recommendations

⚠️ **Before Production Deployment:**

1. **Change SECRET_KEY** in `prod/.env`:
   ```bash
   openssl rand -base64 32
   ```

2. **Configure SSL Certificates**:
   - Place in `/mailu/certs/` directory
   - Or enable auto-renewal with Let's Encrypt

3. **Set Strong Database Password** (if using external DB):
   ```
   DB_PW=<VerySecurePassword>
   ```

4. **Enable 2FA** on admin accounts once deployed

5. **Configure DNS Records**:
   ```
   A       mail.lgucalapan.ph      72.60.43.21
   MX      lgucalapan.ph           mail.lgucalapan.ph (priority 10)
   SPF     lgucalapan.ph           v=spf1 mx ~all
   DMARC   _dmarc                  v=DMARC1; p=none;
   ```

---

## 📦 Features Included

### Custom Branding
- ✅ Calapan City Logo in Admin Panel
- ✅ Calapan City Logo in Webmail
- ✅ Custom site name: "Calapan City Mail"
- ✅ Custom website link: https://www.lgucalapan.ph

### Enhanced Functionality
- ✅ Password change inside webmail (without leaving to admin)
- ✅ Admin-only Mailu button visibility
- ✅ Cancel button on password change form
- ✅ Internal API endpoints for auth operations

---

## 🔄 Updating Production

### To Update Services:
1. Modify code/configuration locally
2. Push to GitHub `master` branch
3. Dokploy automatically triggers rebuild
4. Services restart with new configuration
5. Email data persists in `/mailu` volume

### To Update Mailu Version:
1. Update `VERSION=X.X.XX` in `prod/.env`
2. Push to GitHub
3. Dokploy rebuilds with new version

---

## 📋 GitHub Commits Made

```
commit 4f9e4dc2
Configure production environment for mail.lgucalapan.ph deployment with Dokploy

- Set production domain to lgucalapan.ph
- Configure mail server hostname as mail.lgucalapan.ph  
- Add Calapan City Logo to both admin panel and webmail
- Set production project name to calapan-mailu
- Update LOGO_URL for static file serving
- Add auth API endpoints to production services
- Include PRODUCTION_SETUP.md with Dokploy deployment guide
- Support GitHub auto-deployment workflow
```

---

## 📖 Documentation

For detailed setup instructions, see: **[PRODUCTION_SETUP.md](PRODUCTION_SETUP.md)**

---

## ✨ Production Checklist

- ✅ Configuration files created and committed
- ✅ Custom logo mounted in docker-compose
- ✅ Auth APIs included in production services
- ✅ GitHub push completed
- ✅ Ready for Dokploy deployment

### Next Steps:
1. Configure Dokploy project on 72.60.43.21
2. Set DNS records for lgucalapan.ph
3. Prepare SSL certificates
4. Deploy and create admin user
5. Test all services

---

**Status**: Ready for Production Deployment  
**Date**: January 11, 2026  
**Environment**: mail.lgucalapan.ph (72.60.43.21)
