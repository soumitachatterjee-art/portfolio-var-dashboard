# Heroku Deployment - 7 Steps (15 Minutes)

## TL;DR

```powershell
# 1. Install Heroku CLI
choco install heroku-cli

# 2. Create GitHub repo and push code
git remote add origin https://github.com/USERNAME/portfolio-var-dashboard.git
git branch -M main
git push -u origin main

# 3. Create Heroku app
heroku login
heroku create portfolio-var-dashboard-YOURNAME

# 4. Set database credentials
heroku config:set DB_HOST_STELLARRISK=192.168.102.245
heroku config:set DB_USER_STELLARRISK=risk_reader
heroku config:set DB_PASS_STELLARRISK=risk_reader@123
heroku config:set DB_NAME_STELLARRISK=stellarrisk
heroku config:set ALLOWED_EMAIL_DOMAIN=@axxela.in

# 5. Deploy
git push heroku main

# 6. Watch logs (to verify)
heroku logs --tail

# 7. Open dashboard
heroku open
```

**That's it!** Your URL is now permanent and public.

---

## What Your Team Sees

1. **Login page** (email only, no password)
2. **Dashboard** (real-time VAR metrics)
3. **Logout button** (top right)

---

## Share with Team

Send them:
```
URL: https://portfolio-var-dashboard-YOURNAME.herokuapp.com
Email: your-name@axxela.in (no password)
```

---

## If Something Goes Wrong

**Check logs:**
```powershell
heroku logs --tail
```

**Most common issue:** MySQL not accessible. Solution:
- Whitelist Heroku's IP in your database firewall
- Or: Ask your database admin to allow Heroku IPs

**Excel file not found:**
```powershell
git add FUT-01-41-VAR-CORREL.xlsx
git commit -m "Add Excel"
git push heroku main
```

**Free tier sleeps after 30 min:** Upgrade to Hobby ($7/month)
```powershell
heroku dyno:type hobby --app portfolio-var-dashboard-YOURNAME
```

---

## Full Details

See `HEROKU_DEPLOY.md` for step-by-step with explanations.

---

**Ready? Start with Step 1 above!**
