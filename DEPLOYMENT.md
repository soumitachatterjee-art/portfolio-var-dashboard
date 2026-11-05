# Portfolio VAR Dashboard - Deployment Guide

## Quick Deploy to Replit (No Configuration Needed)

### Step 1: Create a Replit Account
Go to [replit.com](https://replit.com) and sign up (free)

### Step 2: Import This Repository
1. Click "Create" → "Import from GitHub"
2. Paste: `https://github.com/YOUR_USERNAME/portfolio-var-dashboard`
3. Replit will automatically detect `requirements.txt` and `.replit`
4. Click "Import"

### Step 3: Connect Database
Replit will need your MySQL connection details. Set environment variables:

1. Click "Secrets" (lock icon) in the left sidebar
2. Add these secrets:
   ```
   DB_HOST_STELLARRISK=192.168.102.245
   DB_USER_STELLARRISK=risk_reader
   DB_PASS_STELLARRISK=risk_reader@123
   DB_NAME_STELLARRISK=stellarrisk
   ```

### Step 4: Upload Excel File
1. Click "Files" in the sidebar
2. Upload `FUT-01-41-VAR-CORREL.xlsx` to the root directory
3. Update the `EXCEL_FILE` path in `app.py` if needed

### Step 5: Run
Click the green "Run" button. Replit will:
1. Install dependencies from `requirements.txt`
2. Start the Flask app
3. Generate a public URL like `https://project-name.username.repl.co`

### Step 6: Share
Copy the public URL and share it with anyone. They just click the link!

---

## Alternative: Deploy to Heroku

### Step 1: Create Heroku Account
Go to [heroku.com](https://heroku.com) and sign up (free tier still available)

### Step 2: Create Procfile
Create a file named `Procfile` (no extension):
```
web: python app.py
```

### Step 3: Push to GitHub
```bash
git init
git add .
git commit -m "Portfolio VAR Dashboard"
git push origin main
```

### Step 4: Connect GitHub to Heroku
1. In Heroku dashboard, connect your GitHub repo
2. Set environment variables in "Config Vars"
3. Deploy

---

## Database Access from Cloud

**Important:** The MySQL database must be accessible from the cloud server.

### Option A: Keep Database Internal (Recommended)
If your database is behind a firewall:
1. Keep the backend running locally on your office network
2. Deploy only the frontend (HTML/CSS/JS) to the cloud
3. The frontend calls your local backend via a public API tunnel (ngrok)

### Option B: Expose Database (Less Secure)
Ask your IT team to allow MySQL connections from specific cloud IPs

### Option C: Use Ngrok (Simple Temporary Solution)
```bash
# On your local machine, run this to expose the backend:
ngrok http 5000

# You'll get a public URL like: https://abc123.ngrok.io
# Update the frontend to use this URL for API calls
```

---

## Production Considerations

### Security
- [ ] Don't commit database credentials to GitHub (use environment variables)
- [ ] Use HTTPS only (Replit/Heroku provide this automatically)
- [ ] Consider adding API rate limiting
- [ ] Monitor error logs for unauthorized access attempts

### Performance
- [ ] Cache Excel metrics (already implemented)
- [ ] Implement API caching (add Cache-Control headers)
- [ ] Monitor database query performance
- [ ] Set up alerts for API errors

### Monitoring
- [ ] Log all errors with timestamps
- [ ] Monitor database connection failures
- [ ] Track API response times
- [ ] Set up alerts for uptime

---

## Files Included

- `app.py` — Combined Flask backend + frontend server
- `index.html` — PWA frontend (dashboard UI)
- `manifest.json` — PWA app manifest
- `sw.js` — Service Worker (offline support)
- `requirements.txt` — Python dependencies
- `.replit` — Replit configuration
- `DEPLOYMENT.md` — This file

---

## Testing Before Deployment

### Local Testing
```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
python app.py

# Visit http://localhost:5000
```

### Cloud Testing (After Deployment)
1. Visit the public URL
2. Check that the dashboard loads
3. Verify data refreshes
4. Test on mobile device
5. Test "Install App" PWA feature

---

## Troubleshooting

### "Cannot connect to API"
- Check database is accessible from cloud server
- Verify environment variables are set correctly
- Check MySQL firewall rules

### "Excel file not found"
- Verify the Excel file is in the root directory
- Check file path in `app.py` matches the uploaded filename

### "Service Worker failed to load"
- This is OK - the app will work without offline support
- Check browser console for exact error

---

## Support

For issues:
1. Check the app logs (visible in Replit/Heroku dashboard)
2. Verify database connection with `curl http://localhost:5000/api/health`
3. Make sure all environment variables are set

---

**You're done! Share the public URL with anyone.** ✅
