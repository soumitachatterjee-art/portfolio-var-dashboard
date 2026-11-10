from var_config import DB_HOST, DB_NAME, DB_PASS, DB_USER, GOOGLE_CREDENTIALS_FILE, GOOGLE_SHEET_ID
import mysql.connector
import pandas as pd
import numpy as np

PRODUCT_NAME = 'CME 30DayFedFunds'
EXCEL_FILE = 'FUT-01-41-VAR-CORREL.xlsx'
NUM_CONTRACTS = 35

MONTH_MAP = {
    'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
    'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
}

def parse_expiration_date(product_series):
    month_code = product_series[:3].upper()
    year_code = product_series[3:5]
    month = MONTH_MAP.get(month_code, 0)
    year = 2000 + int(year_code) if year_code else 0
    return (year, month)

# Get positions for account 10030 (LGBGG210)
conn = mysql.connector.connect(
    host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, connection_timeout=5
)
cursor = conn.cursor(dictionary=True)

cursor.execute(f"""
    SELECT product_series, SUM(open_position) as net_position
    FROM positions_current
    WHERE product_name = '{PRODUCT_NAME}' AND account_id = '10030'
    GROUP BY product_series
""")
positions_data = cursor.fetchall()

# Get account name separately
cursor.execute(f"SELECT account_name FROM positions_current WHERE account_id = '10030' LIMIT 1")
account_info = cursor.fetchone()
account_name = account_info['account_name'] if account_info else 'LGBGG210'

print("ACCOUNT 10030 (LGBGG210) - DETAILED VAR CALCULATION")
print("="*80)
print(f"\nPositions in account:")
for pos in positions_data:
    print(f"  {pos['product_series']}: {pos['net_position']} contracts")

if not positions_data:
    print("\nNo positions found!")
    cursor.close()
    conn.close()
    exit(1)

# Load Excel data
correl_df = pd.read_excel(EXCEL_FILE, sheet_name='CORREL', header=0, index_col=0)
var_df = pd.read_excel(EXCEL_FILE, sheet_name='VAR', skiprows=5, header=0, index_col=0)

ffc_labels = [f'FFc{i}' for i in range(1, NUM_CONTRACTS + 1)]
correl_full = correl_df.loc[ffc_labels, ffc_labels]
std_devs = var_df.loc[ffc_labels, 'Std.Dev']

# Get C-slot mapping
cursor.execute(f"SELECT DISTINCT product_series FROM positions_current WHERE product_name = '{PRODUCT_NAME}' AND open_position != 0")
series_list = [row['product_series'] for row in cursor.fetchall()]
sorted_series = sorted(series_list, key=parse_expiration_date)

full_mapping = {}
for i, series in enumerate(sorted_series, 1):
    full_mapping[f'C{i}'] = series

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

cursor.close()
conn.close()

# Build positions dict
positions_dict = {row['product_series']: row['net_position'] for row in positions_data}

# STEP 7: Build DV01 vector
print("\n" + "="*80)
print("STEP 7: Convert positions to DV01 vector (dᵢ = qᵢ × $41.67 per bp)")
print("="*80)

dv01_vector = []
dv01_details = []

for i in range(1, NUM_CONTRACTS + 1):
    c_slot = f'C{i}'
    series = full_mapping.get(c_slot, '')
    position = float(positions_dict.get(series, 0))
    dv01 = position * 41.67
    dv01_vector.append(dv01)

    if position != 0:
        dv01_details.append({
            'C-Slot': c_slot,
            'Product Series': series,
            'Position (contracts)': int(position),
            'DV01 ($/bp)': dv01
        })

dv01_vector = np.array(dv01_vector)

print(f"\nDV01 Vector (non-zero entries only):")
for detail in dv01_details:
    print(f"  {detail['C-Slot']} ({detail['Product Series']}): {detail['Position (contracts)']} × 41.67 = ${detail['DV01 ($/bp)']:,.0f}")

total_dv01 = dv01_vector.sum()
print(f"\nTotal DV01: ${total_dv01:,.2f}")

# STEP 5: Build covariance matrix
print("\n" + "="*80)
print("STEP 5: Build covariance matrix Σᵢⱼ = ρᵢⱼ σᵢ σⱼ")
print("="*80)

std_array = std_devs.values
cov_matrix = correl_full.values * np.outer(std_array, std_array)

print(f"\nCovariance matrix constructed: {cov_matrix.shape[0]} × {cov_matrix.shape[1]}")
print(f"Diagonal entries (σᵢ²) for non-zero positions:")
for i, detail in enumerate(dv01_details):
    c_idx = int(detail['C-Slot'][1:]) - 1
    sigma_sq = cov_matrix[c_idx, c_idx]
    print(f"  Σ[{c_idx},{c_idx}] (FFc{c_idx+1}): {sigma_sq:.8f}")

# STEP 8: Calculate portfolio variance
print("\n" + "="*80)
print("STEP 8: Calculate portfolio variance: V = d^T Σ d")
print("="*80)

portfolio_variance = float(dv01_vector @ cov_matrix @ dv01_vector)
print(f"\nPortfolio Variance = d^T Σ d = {portfolio_variance:,.2f}")

# STEP 9: Calculate portfolio volatility
print("\n" + "="*80)
print("STEP 9: Calculate portfolio daily volatility: σₚ = √V")
print("="*80)

portfolio_volatility = float(np.sqrt(portfolio_variance))
print(f"\nPortfolio Volatility = √{portfolio_variance:,.2f} = ${portfolio_volatility:,.2f}/day")

# STEP 10: Calculate VaR
print("\n" + "="*80)
print("STEP 10: Calculate VaR: VaR = Z × σₚ")
print("="*80)

CONFIDENCE_95 = 1.645
CONFIDENCE_99 = 2.326

var_95 = -1.645 * portfolio_volatility
var_99 = -2.326 * portfolio_volatility

print(f"\nZ-score for 95% confidence: 1.645")
print(f"Z-score for 99% confidence: 2.326")
print(f"\nVaR @ 95% = -1.645 × ${portfolio_volatility:,.2f} = ${var_95:,.2f}")
print(f"VaR @ 99% = -2.326 × ${portfolio_volatility:,.2f} = ${var_99:,.2f}")

print("\n" + "="*80)
print("FINAL RESULT FOR LGBGG210")
print("="*80)
print(f"Total DV01: ${total_dv01:,.2f}")
print(f"Portfolio Volatility: ${portfolio_volatility:,.2f}/day")
print(f"VaR @ 95%: ${var_95:,.2f}")
print(f"VaR @ 99%: ${var_99:,.2f}")
print("="*80)

# Now create detailed breakdown for Google Sheets
print("\n" + "="*80)
print("CREATING DETAILED BREAKDOWN TAB FOR GOOGLE SHEETS...")
print("="*80)

import gspread
from google.oauth2.service_account import Credentials


scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=scope)
client = gspread.authorize(creds)

sheet = client.open_by_key(GOOGLE_SHEET_ID)

# Create or get the breakdown tab
try:
    worksheet = sheet.worksheet('LGBGG210 Breakdown')
except:
    worksheet = sheet.add_worksheet(title='LGBGG210 Breakdown', rows=100, cols=10)

worksheet.clear()

# Add title and header
data = [
    ['ACCOUNT LGBGG210 - DETAILED VAR CALCULATION BREAKDOWN'],
    [],
    ['STEP 1: POSITIONS'],
    ['Product Series', 'Contracts', 'C-Slot', 'DV01 ($/bp)', 'Multiplier'],
]

# Add position details
for detail in dv01_details:
    data.append([
        detail['Product Series'],
        detail['Position (contracts)'],
        detail['C-Slot'],
        f"={detail['Position (contracts)']} * 41.67",
        41.67
    ])

# Add blank and summary
data.append([])
data.append(['SUMMARY METRICS', 'Value', 'Formula/Notes'])
data.append(['Total DV01 ($/bp)', total_dv01, 'Sum of all DV01'])
data.append(['Portfolio Variance', portfolio_variance, 'd^T Σ d'])
data.append(['Portfolio Volatility ($/day)', portfolio_volatility, '√Variance'])
data.append(['Z-Score @ 95%', 1.645, 'Normal distribution'])
data.append(['Z-Score @ 99%', 2.326, 'Normal distribution'])
data.append(['VaR @ 95%', var_95, '-1.645 × Volatility'])
data.append(['VaR @ 99%', var_99, '-2.326 × Volatility'])
data.append([''])
data.append(['INTERPRETATION:'])
data.append(['At 95% confidence:', f'Won\'t lose more than $' + f'{abs(var_95):,.0f}' + ' in 1 day (95% of days)'])
data.append(['At 99% confidence:', f'Won\'t lose more than $' + f'{abs(var_99):,.0f}' + ' in 1 day (99% of days)'])

worksheet.append_rows(data)

print("\n✓ Created 'LGBGG210 Breakdown' tab in Google Sheets")
print(f"✓ Account has {len(dv01_details)} position(s)")
print(f"✓ VaR @ 95%: ${var_95:,.2f}")
print(f"✓ VaR @ 99%: ${var_99:,.2f}")
