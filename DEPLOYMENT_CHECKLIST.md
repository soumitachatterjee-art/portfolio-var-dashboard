# Deployment Checklist ✅

## Pre-Deployment Verification

### Code Quality
- [x] `app.py` compiles without syntax errors
- [x] All imports available locally
- [x] Flask routes defined (/api/var, /api/var/summary, /)
- [x] Static file serving configured
- [x] CORS enabled for cross-origin requests

### Configuration
- [x] Excel file path is relative (works on Replit)
- [x] Database credentials read from environment variables
- [x] Port configured to read from env (3000 for Replit, 5000 default)
- [x] `.replit` config specifies Python3 and run command
- [x] `requirements.txt` has all dependencies with pinned versions

### Frontend
- [x] `index.html` uses relative API URLs (window.location.origin)
- [x] Service worker (`sw.js`) caches static assets
- [x] PWA manifest (`manifest.json`) configured
- [x] Responsive design (works on mobile & desktop)
- [x] Error handling for offline/connection issues

### Data Files
- [x] `FUT-01-41-VAR-CORREL.xlsx` exists (must upload separately to Replit)
- [x] Excel sheets present: CORREL, VAR
- [x] 35 contracts (C1-C35) in correlation matrix

### Git Repository
- [x] Local git initialized
- [x] Core files staged and committed
- [x] Documentation added (README, REPLIT_SETUP)
- [x] Ready to push to GitHub

---

## Deployment Steps (In Order)

### Phase 1: GitHub Setup
1. [ ] Create repo on github.com: `portfolio-var-dashboard`
2. [ ] Get repo URL: `https://github.com/USERNAME/portfolio-var-dashboard.git`
3. [ ] Run from workspace root:
   ```powershell
   git remote add origin <repo-url>
   git branch -M main
   git push -u origin main
   ```
4. [ ] Verify all files appear on GitHub

### Phase 2: Replit Import
1. [ ] Go to replit.com
2. [ ] Click "Import from GitHub"
3. [ ] Paste GitHub repo URL
4. [ ] Click Import (Python auto-detected)
5. [ ] Wait for environment to load

### Phase 3: File Upload
1. [ ] In Replit, click Files (left sidebar)
2. [ ] Upload: `FUT-01-41-VAR-CORREL.xlsx`
3. [ ] Verify it appears in root directory
4. [ ] (note: other files auto-imported from GitHub)

### Phase 4: Environment Variables
1. [ ] Click Secrets (lock icon)
2. [ ] Add 4 secrets:
   - `DB_HOST_STELLARRISK` = `192.168.102.245`
   - `DB_USER_STELLARRISK` = `risk_reader`
   - `DB_PASS_STELLARRISK` = `risk_reader@123`
   - `DB_NAME_STELLARRISK` = `stellarrisk`
3. [ ] Verify all 4 appear in Secrets panel

### Phase 5: Launch
1. [ ] Click big "Run" button
2. [ ] Wait for output: `Running on http://0.0.0.0:3000`
3. [ ] Copy public URL from popup

### Phase 6: Testing
1. [ ] Open public URL in browser
2. [ ] Wait for data to load (~3-5 sec)
3. [ ] Verify connection status: 🟢 Connected
4. [ ] Check metrics display:
   - [ ] Portfolio Volatility (non-zero)
   - [ ] VaR @95% (negative value)
   - [ ] VaR @99% (negative value, larger magnitude)
   - [ ] Net Positions (non-zero)
5. [ ] Click Positions tab
6. [ ] Verify position grid shows traded contracts
7. [ ] Check Info tab displays methodology

### Phase 7: Sharing
1. [ ] Copy public URL
2. [ ] Share with team via Slack/Email
3. [ ] Test on different devices (phone, tablet, desktop)
4. [ ] (Optional) Install as PWA on mobile

---

## Expected Behavior

### On Page Load
- Spinner shows "Loading portfolio data..."
- After 3-5 seconds, metrics appear
- Connection status shows 🟢 Connected

### Metrics Display
- **Portfolio Volatility**: ~$12M/day (example from test run)
- **VaR @95%**: -$21.3M (example from test run)
- **VaR @99%**: -$30.2M (example from test run)
- **Net Positions**: ~6,784 contracts (example from test run)

### Auto-Refresh (if enabled)
- Dashboard refreshes every 30 seconds
- Timestamp updates
- New metrics fetched from `/api/var/summary`

### Offline Mode
- Static assets cached by service worker
- API calls fail gracefully (shows error)
- Previous data may be visible from cache

---

## Troubleshooting Checklist

If dashboard doesn't load or shows errors:

1. [ ] **Check Browser Console** (F12 → Console tab)
   - Look for network errors
   - Check for JavaScript errors

2. [ ] **Verify API Health**
   - Open: `https://your-replit-url.replit.dev/api/health`
   - Should see: `{"status":"ok","timestamp":"..."}`

3. [ ] **Check Database Connection**
   - Verify all 4 secrets are set correctly in Replit
   - Confirm 192.168.102.245 is accessible from Replit's IP
   - (May need to whitelist Replit's IP in database firewall)

4. [ ] **Verify Excel File**
   - Check file exists in Replit root: `FUT-01-41-VAR-CORREL.xlsx`
   - File size should be ~500KB
   - Open Replit console and check for file errors

5. [ ] **Check Replit Logs**
   - In Replit, open Logs (bottom right)
   - Look for Python errors or Flask startup issues
   - Check for import errors

6. [ ] **Try Fresh Reload**
   - Hard refresh browser: Ctrl+Shift+R (Windows) or Cmd+Shift+R (Mac)
   - Clear browser cache if needed
   - Try from incognito/private window

---

## Success Criteria

✅ **Deployment is successful when:**

1. Public URL is accessible without login or VPN
2. Dashboard loads within 5 seconds
3. Connection status shows 🟢 Connected
4. All 4 metrics display non-zero values
5. Positions tab shows live contract positions
6. Data refreshes when clicking "Refresh Now"
7. Auto-refresh works when enabled
8. Mobile view is responsive
9. PWA can be installed on mobile
10. URL can be shared with team members

---

## Post-Deployment

### Share URL Format
```
"Portfolio VAR Dashboard is now live!
Open here: https://portfolio-var-dashboard.replit.dev
- No login required
- No VPN needed  
- Auto-refreshes every 30 seconds (optional)
- Works on desktop & mobile
- Can be installed as app"
```

### Monitoring
- Check connection status indicator (green/red)
- Monitor API response times (should be <1 second)
- Watch for database connection errors
- Track auto-refresh frequency

### Updates
- To push code changes: `git push origin main` → Replit auto-syncs
- To update credentials: Edit Secrets in Replit
- To update Excel: Re-upload file to Replit

---

**Status**: Ready for deployment ✅  
**Last Updated**: 2026-11-04  
**Test Run Results**: Verified locally, all calculations correct
