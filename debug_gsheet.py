"""
Debug Google Sheets connection
"""

from var_config import GOOGLE_CREDENTIALS_FILE, GOOGLE_SHEET_ID
import gspread
from google.oauth2.service_account import Credentials


print("[1] Authenticating with Google Sheets...")
try:
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=scope)
    client = gspread.authorize(creds)
    print("[OK] Authenticated")
except Exception as e:
    print(f"[ERROR] Authentication failed: {e}")
    exit(1)

print(f"\n[2] Opening sheet: {GOOGLE_SHEET_ID}")
try:
    sheet = client.open_by_key(GOOGLE_SHEET_ID)
    print(f"[OK] Sheet opened: {sheet.title}")
except Exception as e:
    print(f"[ERROR] Could not open sheet: {e}")
    exit(1)

print("\n[3] Available worksheets:")
try:
    worksheets = sheet.worksheets()
    for i, ws in enumerate(worksheets):
        print(f"   [{i}] {ws.title}")
except Exception as e:
    print(f"[ERROR] Could not list worksheets: {e}")
    exit(1)

print("\n[4] Using first worksheet...")
try:
    worksheet = worksheets[0]
    print(f"[OK] Using: {worksheet.title}")
except Exception as e:
    print(f"[ERROR] Could not get worksheet: {e}")
    exit(1)

print("\n[5] Reading data from sheet...")
try:
    data = worksheet.get_all_values()
    print(f"[OK] Found {len(data)} rows")

    if len(data) > 0:
        print(f"\nFirst 3 rows:")
        for i, row in enumerate(data[:3]):
            print(f"   Row {i+1}: {row[:3]}...")  # Show first 3 columns
    else:
        print("[WARNING] Sheet is empty!")
except Exception as e:
    print(f"[ERROR] Could not read data: {e}")
    exit(1)

print("\n[6] Test write permission...")
try:
    worksheet.batch_clear(['A:H'])
    print("[OK] Can clear cells")

    # Write test data
    worksheet.append_rows([
        ['Account', 'Volatility', 'VaR@95%'],
        ['TEST', '$1,000,000', '-$1,645,000']
    ])
    print("[OK] Can write data")

    # Read back
    data = worksheet.get_all_values()
    print(f"[OK] After write: {len(data)} rows")

except Exception as e:
    print(f"[ERROR] Write test failed: {e}")
    exit(1)

print("\n[SUCCESS] All checks passed!")
