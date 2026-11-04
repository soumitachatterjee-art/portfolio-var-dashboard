# Portfolio VAR Dashboard - Team Quick Start

## What is This?

Real-time portfolio risk analysis for CME 30-Day Fed Funds Futures.  
**No login. No VPN. Works on phone & desktop.**

---

## How to Access

1. **Ask for the URL** (e.g., `https://portfolio-var-dashboard.replit.dev`)
2. **Click the link** — opens in browser
3. **Wait 3-5 seconds** for data to load
4. **You're in!** 📊

---

## What You're Looking At

### The 4 Key Metrics

| Metric | What It Means | Example |
|--------|--------------|---------|
| **Portfolio Volatility** | Daily profit/loss swing | ±$12.9M/day |
| **VaR @ 95%** | Loss limit on 95% of days | -$21.3M |
| **VaR @ 99%** | Loss limit on 99% of days | -$30.2M |
| **Net Positions** | Total contracts held | 6,784 |

### VaR in Plain English

- **VaR@95%**: On 95 out of 100 trading days, we won't lose more than **$21.3M**
- **VaR@99%**: On 99 out of 100 trading days, we won't lose more than **$30.2M**

(If we do lose more, it's rare—but possible during market stress.)

---

## Tabs Explained

### Summary Tab (Default)
- Main risk metrics
- Net portfolio position
- Plain English interpretation

### Positions Tab
- What contracts we hold
- Long (green) vs. Short (red)
- Sensitivity per contract (DV01)

### Info Tab
- How we calculate risk
- Data sources
- Technical parameters

---

## Live vs. Offline

### Live Data (🟢 Green)
- Dashboard just fetched latest data
- Positions are current
- Click **"Refresh Now"** for manual update

### Offline (🔴 Red)
- Dashboard can't reach database
- Showing cached data (may be stale)
- Check your internet connection

---

## Optional Features

### Auto-Refresh
- ☑ **"Auto-refresh every 30s"** checkbox
- Dashboard updates automatically
- Useful for monitoring during market hours

### Install as App
- **iPhone**: Tap Share → Add to Home Screen
- **Android**: Tap menu (3 dots) → Install app
- Works offline, faster load time
- Just a shortcut—not a separate app

---

## The Formula (If You're Curious)

```
Portfolio Risk = √(positions × correlation × volatility)
```

More precisely:
```
Portfolio Variance = d' × Σ × d
Portfolio Volatility = √Variance
VaR = mean - Z_score × σ
```

Where:
- **d** = position × sensitivity (in basis points)
- **Σ** = correlation & volatility matrix
- **Z_score** = 1.645 for 95%, 2.326 for 99%

---

## Troubleshooting

### "🔴 Disconnected" Badge
**Problem**: Can't reach the database  
**Fix**: 
- Check internet connection
- Refresh page (F5)
- Contact the admin

### Dashboard Won't Load
**Problem**: Blank screen or spinner stuck  
**Fix**:
- Hard refresh: `Ctrl+Shift+R` (Windows) or `Cmd+Shift+R` (Mac)
- Clear browser cache
- Try a different browser
- Try incognito/private mode

### Numbers Look Wrong
**Problem**: Metrics seem too big/small  
**Fix**:
- Positions may have changed overnight
- Data is 3-5 seconds old by the time you see it
- Refresh to get latest

### Can't Install App (Mobile)
**Problem**: Install prompt doesn't appear  
**Fix**:
- Use a modern browser (Chrome, Safari, Edge)
- Open dashboard at least once first
- Try again after 30 seconds

---

## FAQ

**Q: Will the app work if I lose internet?**  
A: Static assets (buttons, text) cache locally. API calls will fail gracefully with an error message.

**Q: Can I export the data?**  
A: Not directly from the dashboard. Contact admin for raw Excel exports.

**Q: How often is the data updated?**  
A: Every 30 seconds if auto-refresh is on. Click "Refresh Now" for immediate update.

**Q: Is my data private?**  
A: Yes. Data comes from your internal MySQL database. It's not shared externally.

**Q: Can I access this from home?**  
A: Yes! No VPN needed. Any browser, any internet connection.

**Q: What if I find a bug?**  
A: Contact your administrator with:
- What you were doing
- What went wrong
- Browser & device type
- Screenshot of error (if any)

---

## Contact

**Have questions?** Ask your administrator.

**Something broken?** Report it with:
- 📱 Your device (iPhone/Android/Windows/Mac)
- 🌐 Your browser (Chrome/Safari/Edge/Firefox)
- 🖼️ Screenshot of the error
- 🕐 What time it happened

---

## Key Numbers to Remember

- **Total Contracts**: 35 (C1-C35 futures curve)
- **Data Period**: 7 years (2020-2026)
- **Update Frequency**: Real-time (from MySQL)
- **Confidence Levels**: 95% & 99%
- **Multiplier**: $4,167 per basis point

---

## See Also

For technical details: Ask admin for `README.md` or `REPLIT_SETUP.md`

---

**Last Updated**: 2026-11-04  
**Dashboard Version**: 1.0  
**Status**: Production Live
