# Replit Deployment Checklist

Follow these steps **exactly** to deploy to Replit.

## 1. GitHub Upload (Do Once)

```powershell
cd c:\Users\Axxela\Desktop\VAR

# If not already done:
git remote add origin https://github.com/YOUR_USERNAME/portfolio-var-dashboard.git
git branch -M main
git push -u origin main
```

Replace `YOUR_USERNAME` with your GitHub username.

## 2. Create Replit Project

1. Go to **replit.com**
2. Click **"+ Create"** or **"Import from GitHub"**
3. Paste this URL:
   ```
   https://github.com/YOUR_USERNAME/portfolio-var-dashboard.git
   ```
4. Click "Import" — Replit auto-detects Python

## 3. Upload Excel File

1. In Replit, click the **Files** icon (left sidebar)
2. Click **"Upload file"**
3. Select: `C:\Users\Axxela\Desktop\VAR\FUT-01-41-VAR-CORREL.xlsx`
4. Verify it appears in the root directory alongside `app.py`

## 4. Set Database Credentials

1. In Replit, click the **Secrets** icon (lock icon, left sidebar)
2. Add these 4 environment variables (click "**Add new secret**" for each):

   | Name | Value |
   |------|-------|
   | `DB_HOST_STELLARRISK` | `192.168.102.245` |
   | `DB_USER_STELLARRISK` | `risk_reader` |
   | `DB_PASS_STELLARRISK` | `risk_reader@123` |
   | `DB_NAME_STELLARRISK` | `stellarrisk` |

3. Verify all 4 appear in the Secrets panel

## 5. Click Run

1. Click the big **"Run"** button (top)
2. Replit installs dependencies (`requirements.txt`)
3. Flask starts on port 3000
4. Wait for message: `Running on http://0.0.0.0:3000`

## 6. Get Public URL

Once running:
1. You'll see a popup with a public URL like:
   ```
   https://portfolio-var-dashboard.replit.dev
   ```
2. Or click the **"Open in new tab"** icon (top right)

## 7. Share with Team

Send the public URL to your team:
- **No login required**
- **No VPN needed**
- Works on **desktop & mobile**
- Install as app (iOS: Add to Home Screen, Android: Install app prompt)

## 8. Verify It Works

1. Open the URL in your browser
2. Wait for data to load (3-5 seconds)
3. You should see:
   - Green "🟢 Connected" badge
   - Portfolio Volatility metric
   - VaR @95% and VaR @99%
   - Position grid with live contracts

## 9. (Optional) Enable Auto-Refresh

Users can check the **"Auto-refresh every 30s"** checkbox to see live updates.

---

## Troubleshooting

### "🔴 Disconnected" Error
- Check that all 4 database secrets are set correctly
- Verify `192.168.102.245` is accessible from Replit (may need network whitelist)
- Check Excel file was uploaded

### Port Mismatch Error
- Replit uses **port 3000** (not 5000)
- `.replit` config is already set to 3000, no changes needed

### "Excel file not found"
- Verify file is named exactly: `FUT-01-41-VAR-CORREL.xlsx`
- File must be in Replit root directory (alongside `app.py`)

### Slow to Load
- First load caches Excel metrics (~2-3 seconds)
- Subsequent refreshes are faster
- Check network in browser dev tools (F12)

---

## What Happens on Run

1. `.replit` tells Replit to run: `python app.py`
2. Flask starts and loads Excel metrics into cache
3. Web server listens on 0.0.0.0:3000
4. Frontend connects to `/api/var` on same origin
5. MySQL queries execute each time you refresh
6. Results displayed in dashboard

## File Structure on Replit

```
/
├── app.py
├── index.html
├── sw.js
├── manifest.json
├── requirements.txt
├── .replit
├── FUT-01-41-VAR-CORREL.xlsx  (uploaded separately)
└── ...other files (ignored)
```

---

**You're Done!** 🎉

Your team now has a live, shareable portfolio risk dashboard.

Questions? Check README.md for architecture details.
