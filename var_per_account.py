"""
Calculate Portfolio VAR per Account for CME 30-Day Fed Funds
Export results LIVE to Google Sheets
"""

from var_config import DB_HOST, DB_NAME, DB_PASS, DB_USER, GOOGLE_CREDENTIALS_FILE, GOOGLE_SHEET_ID, GOOGLE_SHEET_TAB
import mysql.connector
import pandas as pd
import numpy as np
from datetime import datetime
import os
import gspread
from google.oauth2.service_account import Credentials

# Configuration
PRODUCT_NAME = 'CME 30DayFedFunds'
EXCEL_FILE = 'FUT-01-41-VAR-CORREL.xlsx'
NUM_CONTRACTS = 35
CONFIDENCE_95 = 1.645
CONFIDENCE_99 = 2.326

# Google Sheets

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
        print(f"Error loading Excel: {e}")
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
        print(f"Error getting C-slot mapping: {e}")
        return {}

def build_dv01_vector(full_c_mapping, positions_dict):
    """Build DV01 vector from positions"""
    dv01_vector = []
    for i in range(1, NUM_CONTRACTS + 1):
        c_slot = f'C{i}'
        series = full_c_mapping.get(c_slot, '')
        position = float(positions_dict.get(series, 0))  # Convert to float
        dv01 = position * 41.67  # Standard multiplier
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

# Main execution
print("Loading Excel metrics...")
correl_matrix, std_devs = get_excel_metrics()
if correl_matrix is None:
    print("Failed to load Excel metrics. Exiting.")
    exit(1)

print("Getting C-slot mapping...")
c_mapping = get_c_slot_mapping()

print("Connecting to database...")
try:
    conn = mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, connection_timeout=5
    )
    cursor = conn.cursor(dictionary=True)

    # Get all accounts with Fed Funds positions
    query = f"""
        SELECT DISTINCT account_id, account_name
        FROM positions_current
        WHERE product_name = '{PRODUCT_NAME}' AND open_position != 0
        ORDER BY account_name
    """
    cursor.execute(query)
    accounts = cursor.fetchall()

    print(f"\nFound {len(accounts)} accounts with {PRODUCT_NAME} positions")

    # Calculate VAR for each account
    results = []
    for account in accounts:
        account_id = account['account_id']
        account_name = account['account_name']

        # Get positions for this account
        pos_query = f"""
            SELECT product_series, SUM(open_position) as net_position
            FROM positions_current
            WHERE product_name = '{PRODUCT_NAME}' AND account_id = '{account_id}'
            GROUP BY product_series
        """
        cursor.execute(pos_query)
        positions = cursor.fetchall()

        # Build positions dict
        positions_dict = {row['product_series']: row['net_position'] for row in positions}

        # Calculate DV01 and VAR
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

            print(f"  {account_name}: Volatility=${var_result['volatility']:,.0f}, VaR@95%=${var_result['var_95']:,.0f}")


    cursor.close()
    conn.close()

    # Export to CSV (local backup)
    df = pd.DataFrame(results)
    csv_file = 'var_by_account.csv'
    df.to_csv(csv_file, index=False)
    print(f"\n[SUCCESS] Exported to {csv_file}")

    # Export to Google Sheets (LIVE)
    print(f"\n[UPLOAD] Syncing to Google Sheets...")
    try:
        # Authenticate with Google Sheets API
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=scope)
        client = gspread.authorize(creds)

        # Open the sheet
        sheet = client.open_by_key(GOOGLE_SHEET_ID)

        # Populate static tabs (one-time setup)
        print("[INFO] Setting up reference tabs...")
        populate_static_tabs(sheet, correl_matrix, std_devs, c_mapping)

        # Get or create the worksheet
        try:
            worksheet = sheet.worksheet(GOOGLE_SHEET_TAB)
        except:
            # If tab doesn't exist, use the first sheet
            worksheet = sheet.worksheets()[0]
            print(f"[INFO] Using sheet: {worksheet.title}")

        # Clear ALL and rewrite with headers
        worksheet.clear()

        # Convert DataFrame to list of lists with headers
        data_to_insert = [df.columns.tolist()] + df.values.tolist()

        # Write data to sheet starting from A1
        worksheet.append_rows(data_to_insert, value_input_option='RAW')

        print(f"[SUCCESS] Google Sheets synced! {len(results)} accounts")

    except Exception as e:
        print(f"[WARNING] Google Sheets sync failed: {e}")

    print(f"\nTotal accounts processed: {len(results)}")

    # Display summary
    print("\n" + "="*80)
    print(df.to_string(index=False))
    print("="*80)

except Exception as e:
    print(f"Error: {e}")
finally:
    if conn:
        conn.close()
