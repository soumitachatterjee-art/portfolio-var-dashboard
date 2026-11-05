# Deploy to Railway (Free, Permanent URL)

## What You Get

✅ Permanent public URL (never changes)  
✅ Auto HTTPS + Let's Encrypt certificate  
✅ $5/month free credit (covers small apps)  
✅ GitHub auto-deploy (push = auto-deploy)  
✅ Email-only login (@axxela.in)  

---

## Step-by-Step (10 Minutes)

### Step 1: Create GitHub Repo

```powershell
cd c:\Users\Axxela\Desktop\VAR

# If not done yet:
git remote add origin https://github.com/USERNAME/portfolio-var-dashboard.git
git branch -M main
git push -u origin main
```

Replace `USERNAME` with your GitHub username.

---

### Step 2: Sign Up to Railway

1. Go to **railway.app**
2. Click **"Sign Up"**
3. Use GitHub account (OAuth)
4. Authorize Railway

---

### Step 3: Create New Project

1. In Railway dashboard, click **"New Project"**
2. Select **"Deploy from GitHub repo"**
3. Authorize Railway to access your GitHub
4. Select: `portfolio-var-dashboard` repo

---

### Step 4: Railway Auto-Detects Python

Railway sees `requirements.txt` and `app.py`, auto-configures:
- ✅ Python 3.10
- ✅ Install dependencies
- ✅ Start command: `gunicorn app:app`

Just wait for auto-deploy to start.

---

### Step 5: Set Environment Variables

In Railway dashboard, go to **"Variables"** tab, add:

```
DB_HOST_STELLARRISK=192.168.102.245
DB_USER_STELLARRISK=risk_reader
DB_PASS_STELLARRISK=risk_reader@123
DB_NAME_STELLARRISK=stellarrisk
ALLOWED_EMAIL_DOMAIN=@axxela.in
SECRET_KEY=your-secret-key-here
```

For SECRET_KEY, generate one:
```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

---

### Step 6: Upload Excel File

**Option A: Via Git (Recommended)**
```powershell
git add FUT-01-41-VAR-CORREL.xlsx
git commit -m "Add Excel metrics"
git push origin main
```

Railway auto-redeploys with the new file.

**Option B: Via Railway Files (Manual)**
1. In Railway, click **"Files"** tab
2. Upload `FUT-01-41-VAR-CORREL.xlsx`

---

### Step 7: Wait for Deploy

Railway shows deployment progress. Once done (green checkmark):

1. Click **"Deployments"** tab
2. Find your deployment
3. Click **"View Logs"** to verify no errors
4. Should see: `Running on http://0.0.0.0:8000`

---

### Step 8: Get Your Public URL

In Railway dashboard:
1. Click **"Domains"** or **"Settings"**
2. You'll see auto-generated URL like:
   ```
   https://portfolio-var-production-xxxx.up.railway.app
   ```

3. Copy this URL

---

## Share with Your Team

Send them:
```
Dashboard: https://portfolio-var-production-xxxx.up.railway.app
Email: your-name@axxela.in
Password: None (email-only login)
```

They just enter their @axxela.in email and click "Sign In".

---

## What They See

1. **Login page** (beautiful, modern)
2. **Email input** (must be @axxela.in)
3. **Dashboard** (real-time VAR metrics)
4. **Logout button** (top right)

---

## Monitoring & Logs

```powershell
# View live logs
# In Railway dashboard: Deployments → View Logs

# Check if app is running
# Click your deployment, scroll down to see status
```

---

## Update Code

After making changes locally:

```powershell
git add .
git commit -m "Your change"
git push origin main
```

Railway auto-detects push and redeploys automatically.

---

## Update Excel Metrics

1. Regenerate locally: `python portfolio_var.py`
2. Push to GitHub:
   ```powershell
   git add FUT-01-41-VAR-CORREL.xlsx
   git commit -m "Update Excel metrics"
   git push origin main
   ```
3. Railway auto-redeploys

---

## Troubleshooting

### "Build failed" or "Deployment failed"
Check logs in Railway dashboard:
1. Click **"Deployments"**
2. Find failed deployment
3. Click **"View Logs"**
4. Look for error messages

Common issues:
- Missing environment variable → Add to Variables tab
- Excel file not found → Upload via git or Railway Files
- Database not accessible → Check DB credentials

### "Cannot connect to database" (🔴 badge)
- Verify all 4 DB variables are set correctly
- Whitelist Railway's IP in your database firewall
- Test: `mysql -h 192.168.102.245 -u risk_reader -p...`

### "Login page shows but no dashboard"
- Check browser console (F12) for JavaScript errors
- Verify ALLOWED_EMAIL_DOMAIN is set to `@axxela.in`
- Try incognito/private window

---

## Costs

| Tier | Cost | Usage |
|------|------|-------|
| Free | $0 | $5/month credit |
| Paid | $5-200/month | More resources |

Your app will use ~$1-2/month, well within the free $5 credit.

---

## Success Checklist

- [ ] GitHub repo created and pushed
- [ ] Railway account created
- [ ] GitHub repo connected to Railway
- [ ] 6 environment variables set
- [ ] Excel file uploaded (via git or Railway Files)
- [ ] Deployment completed (green checkmark)
- [ ] No errors in logs
- [ ] Can access public URL
- [ ] Login works with @axxela.in email
- [ ] Dashboard shows data
- [ ] 🟢 Connected badge appears

---

## Next Steps

1. **Push code to GitHub** (if not done)
2. **Sign up to Railway** (railway.app)
3. **Connect GitHub repo**
4. **Set environment variables**
5. **Upload Excel file**
6. **Wait for deploy**
7. **Share URL with team**

---

**Estimated time: 10-15 minutes**  
**Cost: Free (within $5/month credit)**  
**Result: Permanent public URL, always on, auto-HTTPS**

Ready? Start with Step 1!
