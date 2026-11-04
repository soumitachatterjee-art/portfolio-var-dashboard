# Portfolio VAR Dashboard

Real-time portfolio Value at Risk analysis for CME 30-Day Fed Funds Futures (FUT-01-41).

## Features

- **Live Data**: Pulls positions from MySQL database in real-time
- **Parametric VAR**: Uses correlation matrix and volatility metrics (95% & 99% confidence)
- **C1-C35 Coverage**: Full 35-contract futures curve (14 traded + 21 synthetic)
- **PWA Support**: Install as app on mobile/desktop, works offline
- **Auto-Refresh**: Optional 30-second auto-refresh of portfolio metrics
- **Zero Setup**: No VPN or login required for end users

## Deployment to Replit

### Prerequisites
- GitHub account
- Replit account (free)
- Access to MySQL database (192.168.102.245)

### Step-by-Step

1. **Create GitHub Repo**
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/portfolio-var-dashboard.git
   git branch -M main
   git push -u origin main
   ```

2. **Go to Replit**
   - Visit replit.com
   - Click "Import from GitHub"
   - Paste: `https://github.com/YOUR_USERNAME/portfolio-var-dashboard.git`
   - Select Python as language

3. **Upload Excel File**
   - In Replit file explorer, upload `FUT-01-41-VAR-CORREL.xlsx`
   - Verify it's in the root directory

4. **Set Environment Variables**
   - Click the lock icon (Secrets) in Replit
   - Add these 4 variables:
     ```
     DB_HOST_STELLARRISK=192.168.102.245
     DB_USER_STELLARRISK=risk_reader
     DB_PASS_STELLARRISK=risk_reader@123
     DB_NAME_STELLARRISK=stellarrisk
     ```

5. **Click Run**
   - Replit auto-starts the Flask app on port 3000
   - Get public URL (e.g., `https://portfolio-var-dashboard.replit.dev`)
   - Share URL with team

## Local Development

### Requirements
- Python 3.8+
- MySQL connectivity to 192.168.102.245

### Install & Run

```bash
pip install -r requirements.txt
export DB_HOST_STELLARRISK=192.168.102.245
export DB_USER_STELLARRISK=risk_reader
export DB_PASS_STELLARRISK=risk_reader@123
export DB_NAME_STELLARRISK=stellarrisk
python app.py
```

Then visit: `http://localhost:5000`

## Architecture

### Backend (app.py)
- Flask server serving API + static frontend
- `/api/var` — Full portfolio details (positions + metrics)
- `/api/var/summary` — Quick metrics only (lighter)
- `/api/health` — Health check

### Frontend (index.html)
- Vue-free vanilla JS
- Progressive Web App (installable)
- Service worker for offline support
- Auto-refresh capability

### Data Sources
- **Positions**: MySQL `stellarrisk.positions_current` (live)
- **Metrics**: Excel `FUT-01-41-VAR-CORREL.xlsx` (historical 2020-2026)
  - `CORREL` sheet: 35×35 correlation matrix
  - `VAR` sheet: volatility & VaR metrics

## Portfolio Calculation

Parametric VAR using matrix methodology:

```
1. Load live positions from MySQL (14 traded contracts)
2. Build DV01 vector: d_i = position × $4,167/bp
3. Map to full 35-contract curve (C1-C35) with synthetics
4. Load correlation matrix (Σ) from Excel
5. Build covariance matrix: Σ_ij = ρ_ij × σ_i × σ_j
6. Calculate portfolio variance: V = d'Σd
7. Calculate portfolio volatility: σ_p = √V
8. Calculate VaR@95%: -1.645 × σ_p
9. Calculate VaR@99%: -2.326 × σ_p
```

## Output

**Summary Dashboard**
- Portfolio Volatility (daily P&L swing)
- VaR @ 95% Confidence (loss limit)
- VaR @ 99% Confidence (extreme loss limit)
- Net Positions (contracts)
- Total DV01 (basis point sensitivity)

**Position Details**
- Contract slot (C1-C35)
- Contract series (NOV26, DEC26, etc.)
- Net position (long/short)
- DV01 sensitivity

## Troubleshooting

**"API request failed"**
- Check network connectivity
- Verify database credentials in Replit secrets
- Check MySQL server is accessible from Replit IP

**"Excel file not found"**
- Verify Excel file is uploaded to Replit root directory
- File name must be exactly: `FUT-01-41-VAR-CORREL.xlsx`

**"No positions or database error"**
- Confirm database has positions for 'CME 30DayFedFunds'
- Check database credentials

## Files

- `app.py` — Flask backend + API
- `index.html` — PWA frontend
- `sw.js` — Service worker (offline support)
- `manifest.json` — PWA metadata
- `requirements.txt` — Python dependencies
- `.replit` — Replit configuration
- `FUT-01-41-VAR-CORREL.xlsx` — Historical metrics (not in repo, upload separately)

## Support

For questions about VAR methodology, refer to the VAR methodology section in the dashboard (Info tab).

---

**Last Updated**: 2026-11-04  
**Version**: 1.0  
**Status**: Ready for Production
