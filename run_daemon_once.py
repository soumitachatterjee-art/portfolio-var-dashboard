#!/usr/bin/env python3
"""Run daemon for a single iteration to debug"""

from var_config import DB_HOST, DB_NAME, DB_PASS, DB_USER, GOOGLE_CREDENTIALS_FILE, GOOGLE_SHEET_ID, GOOGLE_SHEET_TAB
import sys
sys.path.insert(0, '.')

# Run just the first part of var_live_daemon.py
import mysql.connector
import pandas as pd
import numpy as np
from datetime import datetime
import os
import gspread
import hashlib
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
    month_code = product_series[:3].upper()
    year_code = product_series[3:5]
    month = MONTH_MAP.get(month_code, 0)
    year = 2000 + int(year_code) if year_code else 0
    return (year, month)

def get_excel_metrics():
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
    dv01_vector = []
    for i in range(1, NUM_CONTRACTS + 1):
        c_slot = f'C{i}'
        series = full_c_mapping.get(c_slot, '')
        position = float(positions_dict.get(series, 0))
        dv01 = position * 4167.0
        dv01_vector.append(dv01)
    return np.array(dv01_vector)

def calculate_var(dv01_vector, correl_matrix, std_devs):
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

        pos_str = str(positions)
        pos_hash = hashlib.md5(pos_str.encode()).hexdigest()

        return pos_hash, positions
    except Exception as e:
        print(f"[ERROR] Getting positions: {e}")
        return None, None

def calculate_all_accounts(c_mapping, correl_matrix, std_devs, positions_data):
    results = []

    accounts_dict = {}
    for row in positions_data:
        account_id = row['account_id']
        product_series = row['product_series']
        net_position = row['net_position']

        if account_id not in accounts_dict:
            accounts_dict[account_id] = {'account_id': account_id, 'positions': {}}

        accounts_dict[account_id]['positions'][product_series] = net_position

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

def update_google_sheets(results):
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=scope)
        client = gspread.authorize(creds)

        sheet = client.open_by_key(GOOGLE_SHEET_ID)

        try:
            worksheet = sheet.worksheet(GOOGLE_SHEET_TAB)
        except:
            worksheet = sheet.worksheets()[0]

        worksheet.batch_clear([f'A2:H{worksheet.row_count}'])

        df = pd.DataFrame(results)
        header = [df.columns.tolist()]
        data_rows = df.values.tolist()

        if worksheet.row_count < 2:
            worksheet.append_rows(header + data_rows)
        else:
            worksheet.append_rows(data_rows, value_input_option='RAW')

        return True
    except Exception as e:
        print(f"[ERROR] Google Sheets: {e}")
        return False

# RUN TEST
print("[INFO] Starting test run...")
print(f"[INFO] Loading Excel metrics...")

correl_matrix, std_devs = get_excel_metrics()
if correl_matrix is None:
    print("[ERROR] Failed to load Excel metrics.")
    exit(1)

print("[INFO] Getting C-slot mapping...")
c_mapping = get_c_slot_mapping()
print(f"[INFO] C-mapping has {len(c_mapping)} slots")

print("[INFO] Getting positions hash...")
current_hash, positions_data = get_positions_hash()
print(f"[INFO] Hash: {current_hash}")
print(f"[INFO] Found {len(positions_data)} position rows")

print("[INFO] Calculating VAR for all accounts...")
results = calculate_all_accounts(c_mapping, correl_matrix, std_devs, positions_data)
print(f"[INFO] Calculated {len(results)} accounts")

if results:
    print(f"[INFO] Sample result: {results[0]}")
    print(f"[INFO] Updating Google Sheets...")
    if update_google_sheets(results):
        print("[SUCCESS] Google Sheets updated!")
    else:
        print("[FAILED] Google Sheets update failed!")
else:
    print("[ERROR] No results calculated!")
