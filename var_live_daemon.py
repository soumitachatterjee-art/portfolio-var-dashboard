"""
Portfolio VAR Live Daemon
Continuously monitors positions and updates Google Sheets in real-time
Only writes to Google Sheets when positions change
"""

from var_config import DB_HOST, DB_NAME, DB_PASS, DB_USER, GOOGLE_CREDENTIALS_FILE, GOOGLE_SHEET_ID, GOOGLE_SHEET_TAB
import mysql.connector
import pandas as pd
import numpy as np
from datetime import datetime
import os
import gspread
import time
import hashlib
from google.oauth2.service_account import Credentials

# Configuration
PRODUCT_NAME = 'CME 30DayFedFunds'
EXCEL_FILE = 'FUT-01-41-VAR-CORREL.xlsx'
NUM_CONTRACTS = 35
CONFIDENCE_95 = 1.645
CONFIDENCE_99 = 2.326

# Google Sheets

# Check interval (seconds)
CHECK_INTERVAL = 30  # Check for changes every 30 seconds
UPDATE_INTERVAL = 60  # Update Sheets every 60 seconds regardless

MONTH_MAP = {
    'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
    'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
}

def parse_expiration_date(product_series):
    """Parse 'NOV26' -> (2026, 11)"""
    month_code = product_series[:3].upper()
    year_code = product_series[3:5]
    month = MONTH_MAP.get(month_code, 0)
    year = 2000 + int(year_code) if year_code else 0
    return (year, month)

def get_excel_metrics():
    """Load correlation and volatility metrics from Excel"""
    try:
        correl_df = pd.read_excel(EXCEL_FILE, sheet_name='CORREL', header=0, index_col=0)
        ffc_labels = [f'FFc{i}' for i in range(1, NUM_CONTRACTS + 1)]
        correl_full = correl_df.loc[ffc_labels, ffc_labels]

        if not np.allclose(correl_full.values, correl_full.T.values, atol=1e-6):
            correl_full = (correl_full + correl_full.T) / 2

        var_df = pd.read_excel(EXCEL_FILE, sheet_name='VAR', skiprows=5, header=0, index_col=0)
        std_devs = var_df.loc[ffc_labels, 'Std.Dev']

        return correl_full, std_devs
    except Exception as e:
        print(f"[ERROR] Loading Excel: {e}")
        return None, None

def get_c_slot_mapping():
    """Get chronological C-slot mapping"""
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, connection_timeout=5
        )
        cursor = conn.cursor(dictionary=True)

        query = f"SELECT DISTINCT product_series FROM positions_current WHERE product_name = '{PRODUCT_NAME}' AND open_position != 0"
        cursor.execute(query)
        series_list = [row['product_series'] for row in cursor.fetchall()]

        cursor.close()
        conn.close()

        sorted_series = sorted(series_list, key=parse_expiration_date)

        full_mapping = {}
        for i, series in enumerate(sorted_series, 1):
            full_mapping[f'C{i}'] = series

        # Add synthetic contracts
        if sorted_series:
            last_series = sorted_series[-1]
            last_year, last_month = parse_expiration_date(last_series)
            current_slot = len(full_mapping) + 1
            year = last_year
            month = last_month

            for i in range(current_slot, NUM_CONTRACTS + 1):
                month += 1
                if month > 12:
                    month = 1
                    year += 1

                reverse_month_map = {v: k for k, v in MONTH_MAP.items()}
                month_name = reverse_month_map.get(month, 'JAN')
                synthetic_series = f"{month_name}{year % 100:02d}"
                full_mapping[f"C{i}"] = synthetic_series

        return full_mapping
    except Exception as e:
        print(f"[ERROR] C-slot mapping: {e}")
        return {}

def build_dv01_vector(full_c_mapping, positions_dict):
    """Build DV01 vector from positions"""
    dv01_vector = []
    for i in range(1, NUM_CONTRACTS + 1):
        c_slot = f'C{i}'
        series = full_c_mapping.get(c_slot, '')
        position = float(positions_dict.get(series, 0))
        dv01 = position * 41.67
        dv01_vector.append(dv01)
    return np.array(dv01_vector)

def calculate_var(dv01_vector, correl_matrix, std_devs):
    """Calculate portfolio VAR"""
    std_array = std_devs.values
    cov_matrix = correl_matrix.values * np.outer(std_array, std_array)

    portfolio_variance = float(dv01_vector @ cov_matrix @ dv01_vector)
    if portfolio_variance < 0:
        return None

    portfolio_volatility = float(np.sqrt(portfolio_variance))
    var_95 = float(0 - CONFIDENCE_95 * portfolio_volatility)
    var_99 = float(0 - CONFIDENCE_99 * portfolio_volatility)

    return {
        'variance': portfolio_variance,
        'volatility': portfolio_volatility,
        'var_95': var_95,
        'var_99': var_99
    }

def get_positions_hash():
    """Get hash of current positions (to detect changes)"""
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, connection_timeout=5
        )
        cursor = conn.cursor(dictionary=True)

        query = f"""
            SELECT account_id, product_series, SUM(open_position) as net_position
            FROM positions_current
            WHERE product_name = '{PRODUCT_NAME}' AND open_position != 0
            GROUP BY account_id, product_series
            ORDER BY account_id, product_series
        """
        cursor.execute(query)
        positions = cursor.fetchall()

        cursor.close()
        conn.close()

        # Create hash of positions
        pos_str = str(positions)
        pos_hash = hashlib.md5(pos_str.encode()).hexdigest()

        return pos_hash, positions
    except Exception as e:
        print(f"[ERROR] Getting positions: {e}")
        return None, None

def calculate_all_accounts(c_mapping, correl_matrix, std_devs, positions_data):
    """Calculate VAR for all accounts"""
    results = []

    # Group positions by account
    accounts_dict = {}
    for row in positions_data:
        account_id = row['account_id']
        product_series = row['product_series']
        net_position = row['net_position']

        if account_id not in accounts_dict:
            accounts_dict[account_id] = {'account_id': account_id, 'positions': {}}

        accounts_dict[account_id]['positions'][product_series] = net_position

    # Get account names
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, connection_timeout=5
        )
        cursor = conn.cursor(dictionary=True)

        for account_id in accounts_dict.keys():
            cursor.execute(f"SELECT DISTINCT account_name FROM positions_current WHERE account_id = '{account_id}' LIMIT 1")
            row = cursor.fetchone()
            if row:
                accounts_dict[account_id]['account_name'] = row['account_name']

        cursor.close()
        conn.close()
    except:
        pass

    # Calculate VAR for each account
    for account_id, account_data in accounts_dict.items():
        positions_dict = account_data['positions']
        account_name = account_data.get('account_name', account_id)

        dv01_vector = build_dv01_vector(c_mapping, positions_dict)
        var_result = calculate_var(dv01_vector, correl_matrix, std_devs)

        if var_result:
            total_position = sum(positions_dict.values())
            total_dv01 = dv01_vector.sum()

            results.append({
                'Account ID': account_id,
                'Account Name': account_name,
                'Total Positions (contracts)': int(total_position),
                'Total DV01 ($/bp)': float(total_dv01),
                'Portfolio Volatility ($/day)': float(var_result['volatility']),
                'VaR @ 95%': float(var_result['var_95']),
                'VaR @ 99%': float(var_result['var_99']),
                'Timestamp': datetime.now().isoformat()
            })

    return results

def populate_static_tabs(sheet, correl_matrix, std_devs, c_mapping):
    """Populate static debug tabs (correlation, volatility, C-mapping)"""
    try:
        # === CORRELATION MATRIX TAB ===
        try:
            worksheet = sheet.worksheet('Correlation Matrix')
        except:
            worksheet = sheet.add_worksheet(title='Correlation Matrix', rows=40, cols=40)

        worksheet.clear()

        # Add correlation matrix
        ffc_labels = [f'FFc{i}' for i in range(1, NUM_CONTRACTS + 1)]
        data = [[' '] + ffc_labels]
        for i, label in enumerate(ffc_labels):
            row = [label] + [float(correl_matrix.iloc[i, j]) for j in range(NUM_CONTRACTS)]
            data.append(row)

        worksheet.append_rows(data)

        # === VOLATILITY TAB ===
        try:
            worksheet = sheet.worksheet('Volatility')
        except:
            worksheet = sheet.add_worksheet(title='Volatility', rows=40, cols=5)

        worksheet.clear()

        vol_data = [['Contract', 'Std Dev ($/day)']]
        for i, label in enumerate(ffc_labels):
            vol_data.append([label, float(std_devs.iloc[i])])

        worksheet.append_rows(vol_data)

        # === C-SLOT MAPPING TAB ===
        try:
            worksheet = sheet.worksheet('C-Slot Mapping')
        except:
            worksheet = sheet.add_worksheet(title='C-Slot Mapping', rows=40, cols=3)

        worksheet.clear()

        mapping_data = [['C-Slot', 'Product Series']]
        for c_slot in sorted(c_mapping.keys(), key=lambda x: int(x[1:])):
            mapping_data.append([c_slot, c_mapping[c_slot]])

        worksheet.append_rows(mapping_data)

        # === CALCULATION NOTES TAB ===
        try:
            worksheet = sheet.worksheet('Notes')
        except:
            worksheet = sheet.add_worksheet(title='Notes', rows=20, cols=2)

        worksheet.clear()

        notes_data = [
            ['Parameter', 'Value'],
            ['Product', PRODUCT_NAME],
            ['Total Contracts', NUM_CONTRACTS],
            ['Confidence Level 95%', CONFIDENCE_95],
            ['Confidence Level 99%', CONFIDENCE_99],
            ['DV01 per contract ($/bp)', 41.67],
            ['Check Interval (seconds)', CHECK_INTERVAL],
            ['Database Host', DB_HOST],
            ['', ''],
            ['Calculation', 'Formula'],
            ['DV01 Vector', 'position * 41.67'],
            ['Portfolio Variance', 'd^T * Σ * d'],
            ['Portfolio Volatility', 'sqrt(variance)'],
            ['VaR @ 95%', '-1.645 * volatility'],
            ['VaR @ 99%', '-2.326 * volatility']
        ]

        worksheet.append_rows(notes_data)

        print(f"[SUCCESS] Static tabs created: Correlation Matrix, Volatility, C-Slot Mapping, Notes")
        return True
    except Exception as e:
        print(f"[ERROR] Populating static tabs: {e}")
        return False

def update_google_sheets(results):
    """Update Sheet1 (VAR Results) with results"""
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=scope)
        client = gspread.authorize(creds)

        sheet = client.open_by_key(GOOGLE_SHEET_ID)

        # Get or create Sheet1
        try:
            worksheet = sheet.worksheet(GOOGLE_SHEET_TAB)
        except:
            worksheet = sheet.worksheets()[0]

        # Clear ALL data and rewrite with headers
        worksheet.clear()

        df = pd.DataFrame(results)
        # Create data with headers
        data_to_insert = [df.columns.tolist()] + df.values.tolist()

        # Write all data at once
        worksheet.append_rows(data_to_insert, value_input_option='RAW')

        return True
    except Exception as e:
        print(f"[ERROR] Google Sheets: {e}")
        return False

# Main daemon loop
print("[INFO] Starting VAR Live Daemon...")
print(f"[INFO] Check interval: {CHECK_INTERVAL} seconds")
print(f"[INFO] Loading Excel metrics...")

correl_matrix, std_devs = get_excel_metrics()
if correl_matrix is None:
    print("[ERROR] Failed to load Excel metrics. Exiting.")
    exit(1)

c_mapping = get_c_slot_mapping()

print("[INFO] Creating/updating Google Sheet tabs...")
try:
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(GOOGLE_SHEET_ID)
    populate_static_tabs(sheet, correl_matrix, std_devs, c_mapping)
except Exception as e:
    print(f"[WARNING] Could not populate static tabs: {e}")

last_hash = None
update_count = 0
first_run = True
last_update_time = 0

print("[INFO] Daemon running. Monitoring positions...")
print(f"[INFO] Time: {datetime.now().strftime('%H:%M:%S')}")
print(f"[INFO] Will update Sheets every {UPDATE_INTERVAL} seconds")

try:
    while True:
        import time as time_module
        current_time = time_module.time()

        # Get current positions hash
        current_hash, positions_data = get_positions_hash()

        if current_hash is None:
            print(f"[ERROR] Could not fetch positions. Retrying in {CHECK_INTERVAL}s...")
            time.sleep(CHECK_INTERVAL)
            continue

        # Determine if we should update: first run, positions changed, OR time elapsed
        time_since_update = current_time - last_update_time
        should_update = first_run or current_hash != last_hash or time_since_update >= UPDATE_INTERVAL

        if should_update:
            update_reason = "initial" if first_run else ("change detected" if current_hash != last_hash else "periodic update")
            print(f"\n[SYNC] {update_reason.upper()} at {datetime.now().strftime('%H:%M:%S')}")

            # Calculate VAR
            results = calculate_all_accounts(c_mapping, correl_matrix, std_devs, positions_data)
            print(f"[CALC] Calculated VAR for {len(results)} accounts")

            # Update Google Sheets
            if update_google_sheets(results):
                update_count += 1
                print(f"[SUCCESS] Google Sheets updated (#{update_count})")
                last_update_time = current_time

            last_hash = current_hash
            first_run = False
        else:
            elapsed = int(UPDATE_INTERVAL - time_since_update)
            print(f".", end="", flush=True)

        # Wait before next check
        time.sleep(CHECK_INTERVAL)

except KeyboardInterrupt:
    print(f"\n[INFO] Daemon stopped by user")
    print(f"[INFO] Total updates: {update_count}")
    exit(0)
except Exception as e:
    print(f"\n[FATAL] {e}")
    exit(1)
