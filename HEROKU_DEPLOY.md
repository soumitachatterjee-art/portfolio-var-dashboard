# Deploy to Heroku (Permanent Public URL)

## What You Get
- ✅ Public URL (permanent, always on)
- ✅ Email-only login (@axxela.in)
- ✅ PWA (installable, offline support)
- ✅ Real-time portfolio VAR data
- ✅ $7/month hobby tier (or free if eligible)

---

## Prerequisites

1. **Heroku Account** (free) — https://www.heroku.com
2. **GitHub Account** (free) — https://github.com
3. **Heroku CLI** — https://devcenter.heroku.com/articles/heroku-cli

---

## Step 1: Install Heroku CLI

**Windows:**
```powershell
# Download and run installer from:
# https://devcenter.heroku.com/articles/heroku-cli

# Or use Chocolatey:
choco install heroku-cli
```

Verify:
```powershell
heroku --version
```

---

## Step 2: Push Code to GitHub

```powershell
cd c:\Users\Axxela\Desktop\VAR

# Initialize git (if not done already)
git init
git add .
git commit -m "Add email authentication and Heroku deployment"

# Create repo on github.com: portfolio-var-dashboard
# Then:
git remote add origin https://github.com/USERNAME/portfolio-var-dashboard.git
git branch -M main
git push -u origin main
```

---

## Step 3: Create Heroku App

```powershell
# Login to Heroku
heroku login

# Create app
heroku create portfolio-var-dashboard-YOURNAME

# Set environment variables
heroku config:set DB_HOST_STELLARRISK=192.168.102.245
heroku config:set DB_USER_STELLARRISK=risk_reader
heroku config:set DB_PASS_STELLARRISK=risk_reader@123
heroku config:set DB_NAME_STELLARRISK=stellarrisk
heroku config:set ALLOWED_EMAIL_DOMAIN=@axxela.in
heroku config:set SECRET_KEY=$(openssl rand -hex 32)
```

Verify:
```powershell
heroku config
```

---

## Step 4: Upload Excel File

**Option A: Using git (simpler)**

1. In your local folder, add the Excel file:
   ```powershell
   cp "c:\Users\Axxela\Desktop\VAR\FUT-01-41-VAR-CORREL.xlsx" .
   git add FUT-01-41-VAR-CORREL.xlsx
   git commit -m "Add Excel metrics"
   git push
   ```

2. Deploy to Heroku:
   ```powershell
   git push heroku main
   ```

**Option B: Manual upload (if file is large)**

Not recommended for Heroku (file persists are limited). Use Option A.

---

## Step 5: Deploy

**If using git push (recommended):**
```powershell
git push heroku main
```

Heroku will:
1. Detect Python app
2. Install dependencies from `requirements.txt`
3. Start `Procfile` (gunicorn app:app)
4. Assign public URL

**Watch the logs:**
```powershell
heroku logs --tail
```

---

## Step 6: Get Your URL

```powershell
heroku open
```

Or check:
```powershell
heroku apps:info
```

Your URL will be something like:
```
https://portfolio-var-dashboard-yourname.herokuapp.com
```

---

## Step 7: Share with Team

Send them:
```
Dashboard: https://portfolio-var-dashboard-yourname.herokuapp.com
Email: your-name@axxela.in
Password: None (email-only login)
```

Also share: `TEAM_GUIDE.md` (in repo)

---

## Usage

### Login Page
Users see a simple email login:
1. Open the URL
2. Enter email (must be @axxela.in)
3. Click "Sign In"
4. Dashboard loads

### Dashboard
- Real-time portfolio VAR
- Position breakdown
- Auto-refresh (optional)
- Mobile-friendly
- Can install as PWA app

### Logout
Click "Logout" in top right (under timestamp)

---

## Troubleshooting

### "Application error"
Check logs:
```powershell
heroku logs --tail
```

Most common: MySQL not accessible from Heroku IP. Solutions:
1. Whitelist Heroku IP in database firewall
2. Or: Migrate MySQL to cloud (AWS RDS, Azure DB, etc.)

### "Excel file not found"
Make sure file is committed to git:
```powershell
git add FUT-01-41-VAR-CORREL.xlsx
git commit -m "Add Excel"
git push heroku main
```

### "Database connection failed"
Verify environment variables:
```powershell
heroku config
```

Re-set if needed:
```powershell
heroku config:set DB_HOST_STELLARRISK=192.168.102.245
```

### App is slow or times out
Heroku free tier sleeps after 30 minutes. Upgrade to hobby tier:
```powershell
heroku dyno:type hobby --app portfolio-var-dashboard-yourname
```

Cost: $7/month (but always on).

---

## Viewing Logs

Real-time:
```powershell
heroku logs --tail
```

Recent 100 lines:
```powershell
heroku logs --num 100
```

---

## Updating Code

After making changes locally:
```powershell
git add .
git commit -m "Your change description"
git push heroku main
```

Heroku auto-deploys and restarts app.

---

## Updating Excel Metrics

1. Regenerate locally: `python portfolio_var.py`
2. Commit & push:
   ```powershell
   git add FUT-01-41-VAR-CORREL.xlsx
   git commit -m "Update Excel metrics"
   git push heroku main
   ```

---

## Costs

| Tier | Price | Uptime | Best For |
|------|-------|--------|----------|
| Free | $0 | ~18 hours/month (sleeps) | Testing |
| Hobby | $7/month | 24/7 | Production |
| Standard | $50/month | 24/7 + more resources | High traffic |

For a team dashboard, **Hobby tier ($7/month)** is recommended for 24/7 uptime.

---

## Alternative: Keep Running Locally

If you prefer not to deploy to Heroku, you can:

1. **Run locally with ngrok** (free but URL changes every 2 hours)
   ```powershell
   python app.py
   # In another terminal:
   ngrok http 5000
   ```

2. **Run on your own server** (this machine)
   - Use ngrok Pro ($10/month) for permanent URL
   - Or: Whitelist your IP with team & use `http://YOUR_IP:5000`

3. **Wait for Replit** (next month)
   - Replit free tier resets monthly
   - Can deploy then with zero configuration

---

## Success Checklist

- [ ] Heroku CLI installed
- [ ] Code pushed to GitHub
- [ ] Heroku app created
- [ ] 6 environment variables set
- [ ] Excel file uploaded (via git)
- [ ] Deploy completed (`git push heroku main`)
- [ ] No errors in logs (`heroku logs --tail`)
- [ ] Can access public URL
- [ ] Login works with @axxela.in email
- [ ] Dashboard loads with data
- [ ] MySQL connection successful (🟢 Connected badge)

---

**Status**: Ready to deploy to Heroku  
**Estimated time**: 15 minutes  
**Cost**: Free tier or $7/month hobby tier

**Next step**: Follow the 7 steps above!
