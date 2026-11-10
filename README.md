# Portfolio VaR Dashboard and Account Reporting

Calculate parametric Value at Risk (VaR) for `CME 30DayFedFunds` using live MySQL positions and historical risk inputs from `FUT-01-41-VAR-CORREL.xlsx`.

The project currently has two independent workflows:

- **Per-account reporting to Google Sheets:** `var_live_daemon.py` monitors positions continuously; `var_per_account.py` produces a one-time CSV export and Sheets update.
- **Aggregate portfolio dashboard:** `app.py` serves a Flask API and a vanilla JavaScript PWA with email-domain login, position details, and optional 30-second refresh.

The dashboard queries MySQL directly. It does not read Google Sheets or `var_by_account.csv`, and starting Flask does not start the daemon.

## Data and calculation

Positions come from `stellarrisk.positions_current`, filtered by `product_name = 'CME 30DayFedFunds'`. Reporting scripts group positions by account and series; the dashboard nets positions across all accounts by series.

The workbook supplies:

- `CORREL`: the 35-by-35 correlation matrix labelled `FFc1` through `FFc35` on both axes.
- `VAR`: the `Std.Dev` column for the same labels, loaded with `skiprows=5`.

The main calculation paths symmetrize the correlation matrix when needed and use:

```text
d[i]           = net_position[i] * multiplier[i]
covariance[i,j] = correlation[i,j] * std_dev[i] * std_dev[j]
variance       = d.T @ covariance @ d
volatility     = sqrt(variance)
VaR 95%        = -1.645 * volatility
VaR 99%        = -2.326 * volatility
```

VaR is returned as a negative loss amount. The code reads existing workbook metrics; it does not refresh historical prices or recalculate historical inputs.

### Contract mapping and implementation differences

Series such as `NOV26` are sorted by expiration and assigned sequentially to `C1`, `C2`, etc., aligned with `FFc1`, `FFc2`, etc. Remaining slots through `C35` are filled with monthly series after the last observed expiration and carry zero positions. Gaps between observed expirations are not filled. The number of observed contracts is data-dependent, rather than fixed at 14.

| Path | Mapping source | Sensitivity multiplier |
| --- | --- | --- |
| `var_live_daemon.py`, `var_per_account.py` | Series with nonzero source positions across accounts | Fixed `41.67` |
| `app.py` | All product series in the table, including zero-position rows | `MAX(point_value)` per series; `4167.0` fallback where a series has no position data |
| `run_daemon_once.py` | Series with nonzero source positions | Fixed `4167.0` |
| `calc_lgbgg210.py` | Nonzero series across accounts | Fixed `41.67` |

These paths are not numerically interchangeable. The fixed multipliers differ by a factor of 100; confirm workbook volatility units and database point values before comparing results. `audit_steps.py` contains older multiplier commentary and does not reconcile the current implementations.

## Local setup

Run commands from the project directory so relative workbook, HTML, and credentials paths resolve correctly. Python 3.10 is a practical environment for the pinned dependencies; the repository does not pin a Python runtime.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\Activate.ps1
```

Alternatively, use `.\.venv\Scripts\python.exe` instead of `python` in subsequent commands without activating the environment.

Required inputs and access:

- `FUT-01-41-VAR-CORREL.xlsx` in the project directory. It is currently tracked in Git.
- Network access to the configured MySQL server. Reporting scripts currently target a private LAN address, so the machine running them needs LAN/VPN connectivity.
- For Sheets reporting, a Google service-account key saved as `google-credentials.json`, Sheets and Drive API access, and Editor sharing of the target spreadsheet with that service account.

Dependencies include Flask, Flask-CORS, Flask-Session, pandas, NumPy, MySQL Connector, openpyxl, Gunicorn, gspread, and google-auth. Flask currently uses built-in signed-cookie sessions; Flask-Session is listed but not initialized.

## Per-account Google Sheets reporting

### Configuration

Reporting scripts import settings from `var_config.py`. On a fresh checkout, copy the example and enter your local credentials and spreadsheet ID:

```powershell
Copy-Item var_config.example.json var_config.local.json
```

`var_config.local.json` is ignored by Git. Environment variables override its values: `DB_HOST_STELLARRISK`, `DB_USER_STELLARRISK`, `DB_PASS_STELLARRISK`, `DB_NAME_STELLARRISK`, `GOOGLE_SHEET_ID`, `GOOGLE_SHEET_TAB`, and `GOOGLE_CREDENTIALS_FILE`. Defaults are `stellarrisk`, `Sheet1`, and `google-credentials.json` for the database name, tab, and key filename; host, user, password, and spreadsheet ID must be configured.

This local configuration applies to reporting scripts. Flask continues to read environment variables directly. Workbook/product constants remain in the individual scripts. Service-account keys and generated `var_by_account.csv` are also ignored by Git.

### Continuous monitoring

```powershell
python var_live_daemon.py
```

The daemon:

1. Loads workbook metrics and the global C-slot mapping once at startup.
2. Creates or rewrites reference tabs: `Correlation Matrix`, `Volatility`, `C-Slot Mapping`, and `Notes`.
3. Polls grouped account/series positions every **30 seconds**, hashing them to detect changes.
4. Recalculates per-account VaR and replaces the results tab on the first run, on position changes, or when **60 seconds** have elapsed since the last successful update. Timing depends on polling and processing time.
5. Retries failed position reads after the polling interval. Stop a foreground run with `Ctrl+C`.

`START_VAR_DAEMON.bat` changes to the project directory and launches `python var_live_daemon.py` in a separate process using Python on PATH. Stop that Python process or use `Ctrl+C` in its console; closing the launcher does not reliably stop it. The batch file does not install a Windows service or automatic restart.

Restart the daemon after workbook changes or when new series require a new mapping. Neither is reloaded during the loop. The daemon writes Google Sheets only; it does not update the CSV backup.

### One-time export

```powershell
python var_per_account.py
```

This calculates accounts with nonzero source positions, overwrites `var_by_account.csv`, rewrites reference tabs, and replaces the results tab. The CSV is saved before the Sheets sync, so it can remain available if the upload fails.

Both main reporting scripts target `Sheet1`, falling back to the first worksheet if it is missing. Results updates **clear the entire selected worksheet** and rewrite headers and data. Reference tabs are also cleared and rewritten.

### Result columns

| Column | Meaning |
| --- | --- |
| Account ID / Account Name | Account identifiers from MySQL |
| Total Positions (contracts) | Signed net sum of contracts, not gross exposure |
| Total DV01 ($/bp) | Signed sum of the sensitivity vector |
| Portfolio Volatility ($/day) | Square root of portfolio variance |
| VaR @ 95% / VaR @ 99% | Negative VaR values |
| Timestamp | Calculation time on the machine running Python, without a timezone offset |

Accounts are calculated separately. Summing account VaRs does not reproduce the netted aggregate portfolio VaR.

## Flask dashboard

### Configuration and startup

`app.py` reads these environment variables. It does not load `.env` files automatically.

| Variable | Default / purpose |
| --- | --- |
| `DB_HOST_STELLARRISK` | Empty; set the reachable MySQL host |
| `DB_USER_STELLARRISK` | Empty; set the database user |
| `DB_PASS_STELLARRISK` | Empty; set the database password |
| `DB_NAME_STELLARRISK` | Empty; normally `stellarrisk` |
| `ALLOWED_EMAIL_DOMAIN` | `@axxela.in` |
| `SECRET_KEY` | Random at process startup; set a stable secret across restarts/workers |
| `PORT` | `5000` |
| `FLASK_ENV` | `production`; `development` enables Flask debug mode |

```powershell
$env:DB_HOST_STELLARRISK = '<database-host>'
$env:DB_USER_STELLARRISK = '<database-user>'
$env:DB_PASS_STELLARRISK = '<database-password>'
$env:DB_NAME_STELLARRISK = 'stellarrisk'
$env:ALLOWED_EMAIL_DOMAIN = '@axxela.in'
$env:SECRET_KEY = '<stable-random-secret>'
python app.py
```

Open `http://localhost:5000/login` and enter an email ending in the configured domain. Login checks the suffix only: there is no password, verification email, or mailbox-ownership check. The `SESSION_TIMEOUT` constant is unused; a 24-hour session expiry is not configured.

The dashboard displays volatility, 95%/99% VaR, net positions, total sensitivity, and position details. Auto-refresh is optional. The service worker caches static assets, but fresh risk calculations require backend and database connectivity; offline live VaR is not supported.

### Routes

| Route | Behavior |
| --- | --- |
| `GET /` | Dashboard; requires a session |
| `GET/POST /login` | Login page / establish an email session |
| `GET /login.html` | Login page |
| `GET/POST /logout` | Clear session and redirect to login |
| `GET /api/user` | Authentication status; 401 without a session |
| `GET /api/health` | Process status and timestamp; does not check MySQL or Excel |
| `GET /api/var` | Authenticated aggregate metrics, nonzero position details, and all 35 slots |
| `GET /api/var/summary` | Authenticated aggregate metrics only; still performs the full calculation |
| `GET /manifest.json`, `GET /sw.js` | PWA assets |

Workbook metrics are re-read on every VaR request despite the `_excel_cache` variable. Each request also queries live positions and mapping data.

### Deployment

`Procfile` defines the web process for a Unix-like host:

```text
web: gunicorn app:app --bind 0.0.0.0:$PORT
```

This starts only Flask. Run the reporting daemon separately on a machine with database connectivity. Public hosting needs an explicit network route to the private MySQL server.

`RAILWAY_DEPLOY.md` and `RAILWAY_QUICK_START.txt` contain earlier deployment instructions. Hosting prices, availability, and any claimed live deployment are not verified here. There is no `.replit` configuration in the current repository.

The current `static_folder='.'` setting serves the project root, potentially exposing source, workbook, credential, and generated files. Address this configuration before public deployment. Email suffix checking alone does not verify organizational identity.

## Diagnostics and supporting files

These are manual scripts, not an isolated automated test suite. Several execute database queries or Sheets writes immediately when run or imported.

| File | Purpose and side effects |
| --- | --- |
| `test_daemon.py` | Checks MySQL, hashing, workbook loading, and Sheets writes; **clears A:C in Sheet1 and writes test rows** |
| `run_daemon_once.py` | One-shot calculation and Sheets write using older `4167.0` multiplier; clears A2:H and appends results, with different header handling from the daemon |
| `debug_gsheet.py` | Diagnoses Sheets access; **clears A:H in the first worksheet and writes sample data** |
| `check_sheet.py` | Reads and prints the first five rows of Sheet1 |
| `check_schema.py` | Reads database schema, products, and row counts |
| `audit_steps.py` | Reads workbook inputs and prints methodology checks; includes older multiplier commentary |
| `calc_lgbgg210.py` | Queries account `10030` and replaces `LGBGG210 Breakdown` worksheet |
| `var_config.py`, `var_config.example.json` | Shared reporting configuration and a credential-free setup example |
| `index.html`, `login.html` | Dashboard and email-login frontend |
| `manifest.json`, `sw.js` | PWA metadata and static caching |
| `positions_current.sql` | Local database dump; runtime paths query MySQL rather than loading this file |
| `.agents/` | Earlier planning/design notes, including workflows and files absent from the current implementation |

## Troubleshooting

- **Database failure:** check LAN/VPN connectivity and configuration for the specific entry point. Check environment overrides and `var_config.local.json`; Flask reads environment variables directly.
- **Workbook failure:** check filename, working directory, `CORREL` labels, and the `VAR` sheet's `Std.Dev` column and header offset.
- **Sheets errors:** check the local service-account key, API access, spreadsheet ID, and Editor sharing. Confirm the target worksheet before running a writer.
- **Stale mapping or metrics:** restart the daemon to rebuild the mapping and reload the workbook. Empty mappings and more than 35 observed series are not robustly handled.
- **Dashboard 401:** sign in through `/login`; VaR APIs require a session cookie.
- **Dashboard/Sheets discrepancies:** compare multipliers, volatility units, included series, and mapping rules above.

Documentation updated: **2026-11-10**. Describes the local implementation; live database connectivity, Sheets synchronization, and deployment status require separate runtime verification.
