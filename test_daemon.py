#!/usr/bin/env python3
"""Quick test of daemon components"""

from var_config import DB_HOST, DB_NAME, DB_PASS, DB_USER
import mysql.connector
import pandas as pd
import hashlib
from datetime import datetime

PRODUCT_NAME = 'CME 30DayFedFunds'

print("[TEST 1] Database Connection")
try:
    conn = mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, connection_timeout=5
    )
    cursor = conn.cursor(dictionary=True)

    query = f"SELECT COUNT(*) as cnt FROM positions_current WHERE product_name = '{PRODUCT_NAME}' AND open_position != 0"
    cursor.execute(query)
    result = cursor.fetchone()
    print(f"✓ Database OK - Found {result['cnt']} positions")

    cursor.close()
    conn.close()
except Exception as e:
    print(f"✗ Database FAILED: {e}")
    exit(1)

print("\n[TEST 2] Position Hash")
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
        LIMIT 10
    """
    cursor.execute(query)
    positions = cursor.fetchall()

    pos_str = str(positions)
    pos_hash = hashlib.md5(pos_str.encode()).hexdigest()

    print(f"✓ Hash calculated: {pos_hash}")
    print(f"✓ Sample positions (first 5):")
    for i, pos in enumerate(positions[:5]):
        print(f"  {i+1}. Account {pos['account_id']}, {pos['product_series']}: {pos['net_position']} contracts")

    cursor.close()
    conn.close()
except Exception as e:
    print(f"✗ Hash FAILED: {e}")
    exit(1)

print("\n[TEST 3] Excel Loading")
try:
    EXCEL_FILE = 'FUT-01-41-VAR-CORREL.xlsx'
    NUM_CONTRACTS = 35

    correl_df = pd.read_excel(EXCEL_FILE, sheet_name='CORREL', header=0, index_col=0)
    ffc_labels = [f'FFc{i}' for i in range(1, NUM_CONTRACTS + 1)]
    correl_full = correl_df.loc[ffc_labels, ffc_labels]

    var_df = pd.read_excel(EXCEL_FILE, sheet_name='VAR', skiprows=5, header=0, index_col=0)
    std_devs = var_df.loc[ffc_labels, 'Std.Dev']

    print(f"✓ Excel loaded: {NUM_CONTRACTS}x{NUM_CONTRACTS} correlation matrix")
    print(f"✓ Volatilities loaded: {len(std_devs)} contracts")
    print(f"  Sample volatilities (first 3): {std_devs.head(3).tolist()}")

except Exception as e:
    print(f"✗ Excel FAILED: {e}")
    exit(1)

print("\n[TEST 4] Google Sheets Write")
try:
    import gspread
    from google.oauth2.service_account import Credentials

    GOOGLE_SHEET_ID = '1HnKU_xsL7GUNe2NBW7af0YHkL1PpZ9nwqcYt51Ev2iY'
    GOOGLE_CREDENTIALS_FILE = 'google-credentials.json'

    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=scope)
    client = gspread.authorize(creds)

    sheet = client.open_by_key(GOOGLE_SHEET_ID)
    worksheet = sheet.worksheet('Sheet1')

    test_data = [
        ['Account ID', 'Test', 'Timestamp'],
        ['TEST001', 'Connection OK', datetime.now().isoformat()]
    ]

    worksheet.batch_clear(['A:C'])
    worksheet.append_rows(test_data)

    print(f"✓ Google Sheets write OK")

except Exception as e:
    print(f"✗ Google Sheets FAILED: {e}")
    exit(1)

print("\n" + "="*50)
print("✓ ALL TESTS PASSED - Daemon should work!")
print("="*50)
