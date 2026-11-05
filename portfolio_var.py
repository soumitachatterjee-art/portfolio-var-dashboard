"""
Portfolio-Level VaR Calculation (C1-C35)
Calculates aggregate Value at Risk for CME 30-Day Fed Funds positions
using parametric methodology with live positions from MySQL and correlation/volatility metrics from Excel.

Approach:
1. Map current live contracts to historical FFc slots (FFc1-FFc35)
2. Extract full 35×35 correlation and volatility from Excel CORREL and VAR sheets
3. Build 35×35 covariance matrix
4. Query live positions from MySQL (14 contracts with positions, 21 with zero)
5. Calculate dollar sensitivity (DV01) per contract using DB multiplier
6. Calculate portfolio variance: V = d' * Σ * d
7. Calculate portfolio volatility and VaR at 95%/99%
8. Write results to Excel
"""

import mysql.connector
import pandas as pd
import numpy as np
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('portfolio_var.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
EXCEL_FILE = r'c:\Users\Axxela\Desktop\VAR\FUT-01-41-VAR-CORREL.xlsx'
DB_HOST_STELLARRISK = '192.168.102.245'
DB_USER_STELLARRISK = 'risk_reader'
DB_PASS_STELLARRISK = 'risk_reader@123'
DB_NAME_STELLARRISK = 'stellarrisk'

DB_HOST_GENERIC = '127.0.0.1'
DB_USER_GENERIC = 'root'
DB_PASS_GENERIC = 'Axxela@123'
DB_NAME_GENERIC = 'generic_contract_data'

PRODUCT_NAME = 'CME 30DayFedFunds'
NUM_CONTRACTS = 35  # FFc1-FFc35
CONFIDENCE_95 = 1.645
CONFIDENCE_99 = 2.326
STANDARD_MULTIPLIER = 4167.0  # USD per basis point

# Month mapping for contract chronology
MONTH_MAP = {
    'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
    'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
}

def parse_expiration_date(product_series):
    """Parse 'NOV26' -> (2026, 11) for sorting"""
    month_code = product_series[:3].upper()
    year_code = product_series[3:5]
    
    month = MONTH_MAP.get(month_code, 0)
    year = 2000 + int(year_code) if year_code else 0
    
    return (year, month)

def get_c_slot_mapping_extended():
    """Get chronological C-slot to contract series mapping (C1-C35)"""
    logger.info("Fetching C-slot mapping from positions_current...")
    
    conn = mysql.connector.connect(
        host=DB_HOST_STELLARRISK,
        user=DB_USER_STELLARRISK,
        password=DB_PASS_STELLARRISK,
        database=DB_NAME_STELLARRISK
    )
    cursor = conn.cursor(dictionary=True)
    
    # Get unique series
    query = f"SELECT DISTINCT product_series FROM positions_current WHERE product_name = '{PRODUCT_NAME}'"
    cursor.execute(query)
    series_list = [row['product_series'] for row in cursor.fetchall()]
    
    cursor.close()
    conn.close()
    
    # Sort chronologically
    sorted_series = sorted(series_list, key=parse_expiration_date)
    
    # Map to C-slots (only get actual series, rest will have zero positions)
    c_mapping = {}
    for i, series in enumerate(sorted_series, 1):
        c_slot = f'C{i}'
        c_mapping[c_slot] = series
    
    logger.info(f"Found {len(sorted_series)} contract series with traders")
    logger.info(f"Will extend to C1-C35 with zero positions for untraded months\n")
    
    return c_mapping, sorted_series

def get_live_positions(c_mapping):
    """Query live positions and multipliers from database"""
    logger.info("Querying live positions from positions_current...")
    
    conn = mysql.connector.connect(
        host=DB_HOST_STELLARRISK,
        user=DB_USER_STELLARRISK,
        password=DB_PASS_STELLARRISK,
        database=DB_NAME_STELLARRISK
    )
    
    # Query: aggregate positions by series, keep point_value
    query = f"""
        SELECT product_series, SUM(open_position) as net_position, MAX(point_value) as point_value
        FROM positions_current
        WHERE product_name = '{PRODUCT_NAME}'
        GROUP BY product_series
    """
    
    df = pd.read_sql(query, con=conn)
    conn.close()
    
    logger.info(f"Found {len(df)} unique contract series with positions\n")
    
    return df

def build_full_c_mapping(partial_mapping):
    """Extend partial mapping to full C1-C35 with synthetic future months"""
    logger.info("Extending C-slot mapping to C1-C35...")
    
    full_mapping = {}
    traded_series = set(partial_mapping.values())
    
    # First, add all traded series
    for c_slot, series in partial_mapping.items():
        full_mapping[c_slot] = series
    
    # For untraded slots, estimate future months
    # Assume monthly calendar starting from last traded month
    if traded_series:
        last_series = sorted(traded_series, key=parse_expiration_date)[-1]
        last_year, last_month = parse_expiration_date(last_series)
        
        # Generate synthetic contract names for forward slots
        current_slot = len(partial_mapping) + 1
        year = last_year
        month = last_month
        
        for i in range(current_slot, NUM_CONTRACTS + 1):
            # Next month
            month += 1
            if month > 12:
                month = 1
                year += 1
            
            # Reverse month map
            reverse_month_map = {v: k for k, v in MONTH_MAP.items()}
            month_name = reverse_month_map.get(month, 'JAN')
            synthetic_series = f"{month_name}{year % 100:02d}"
            
            c_slot = f"C{i}"
            full_mapping[c_slot] = synthetic_series
    
    logger.info(f"Extended mapping to {len(full_mapping)} C-slots (C1-C{len(full_mapping)})")
    return full_mapping

def build_dv01_vector(full_c_mapping, positions_df):
    """Build dollar sensitivity (DV01) vector for each C-slot (C1-C35)"""
    logger.info("\nBuilding DV01 vector (C1-C35)...")
    
    # Convert positions_df to dict for lookup
    positions_dict = dict(zip(positions_df['product_series'], positions_df['net_position']))
    multiplier_dict = dict(zip(positions_df['product_series'], positions_df['point_value']))
    
    dv01_vector = []
    c_slot_details = []
    
    for i in range(1, NUM_CONTRACTS + 1):
        c_slot = f'C{i}'
        series = full_c_mapping[c_slot]
        position = positions_dict.get(series, 0)
        multiplier = multiplier_dict.get(series, STANDARD_MULTIPLIER)
        
        # DV01 = position (contracts) × multiplier (USD/bp)
        dv01 = position * multiplier
        
        dv01_vector.append(dv01)
        c_slot_details.append({
            'C_Slot': c_slot,
            'Series': series,
            'Position_Contracts': int(position) if position != 0 else 0,
            'Multiplier_USD_bp': multiplier,
            'DV01_USD_bp': dv01
        })
        
        # Log only first 5, last 5, and non-zero positions
        if i <= 5 or i >= NUM_CONTRACTS - 4 or position != 0:
            status = f"TRADED" if position != 0 else "zero"
            logger.info(f"  {c_slot:>3} ({series:>7}): {position:>8.0f} contracts × ${multiplier:>7.2f}/bp = ${dv01:>12.2f}/bp  [{status}]")
    
    dv01_array = np.array(dv01_vector)
    return dv01_array, c_slot_details

def read_excel_metrics(c_count=35):
    """Read correlation matrix and std.dev from Excel (full 35x35)"""
    logger.info(f"\nReading Excel metrics (FFc1-FFc{c_count})...")
    
    # Read CORREL sheet (35x35, skip header if needed)
    try:
        correl_df = pd.read_excel(EXCEL_FILE, sheet_name='CORREL', header=0, index_col=0)
        logger.info(f"CORREL sheet loaded: {correl_df.shape}")
    except Exception as e:
        logger.error(f"Failed to load CORREL sheet: {e}")
        raise
    
    # Extract full 35x35 correlation matrix
    ffc_labels = [f'FFc{i}' for i in range(1, c_count + 1)]
    correl_full = correl_df.loc[ffc_labels, ffc_labels]
    
    # Validate symmetry
    if not np.allclose(correl_full.values, correl_full.T.values, atol=1e-6):
        logger.warning("Correlation matrix not symmetric. Symmetrizing...")
        correl_full = (correl_full + correl_full.T) / 2
    
    logger.info(f"Extracted {c_count}×{c_count} correlation matrix")
    
    # Read VAR sheet (skip header rows)
    try:
        var_df = pd.read_excel(EXCEL_FILE, sheet_name='VAR', skiprows=5, header=0, index_col=0)
        logger.info(f"VAR sheet loaded: {var_df.shape}")
    except Exception as e:
        logger.error(f"Failed to load VAR sheet: {e}")
        raise
    
    # Extract Std.Dev for FFc1-FFc35
    std_devs = var_df.loc[ffc_labels, 'Std.Dev']
    logger.info(f"Extracted Std.Dev for FFc1-FFc{c_count}")
    logger.info(f"  Min: {std_devs.min():.4f}, Max: {std_devs.max():.4f}, Mean: {std_devs.mean():.4f}")
    
    return correl_full, std_devs

def build_covariance_matrix(correl_matrix, std_devs):
    """Build covariance matrix from correlation and std.dev"""
    logger.info("\nBuilding covariance matrix...")
    
    # Σ_ij = ρ_ij × σ_i × σ_j
    std_array = std_devs.values
    cov_matrix = correl_matrix.values * np.outer(std_array, std_array)
    
    # Verify positive semi-definite
    eigenvalues = np.linalg.eigvalsh(cov_matrix)
    min_eig = eigenvalues.min()
    max_eig = eigenvalues.max()
    cond_number = max_eig / (abs(min_eig) + 1e-10)
    
    logger.info(f"Covariance matrix properties:")
    logger.info(f"  Shape: {cov_matrix.shape}")
    logger.info(f"  Min eigenvalue: {min_eig:.6e}")
    logger.info(f"  Max eigenvalue: {max_eig:.6e}")
    logger.info(f"  Condition number: {cond_number:.2e}")
    
    if min_eig < -1e-6:
        logger.error(f"Covariance matrix not positive semi-definite!")
        raise ValueError("Covariance matrix is not positive semi-definite")
    
    return cov_matrix

def calculate_portfolio_var(dv01_vector, cov_matrix):
    """Calculate portfolio variance, volatility, and VaR"""
    logger.info("\nCalculating portfolio VAR...")
    
    # Portfolio variance: V = d' * Σ * d
    portfolio_variance = dv01_vector @ cov_matrix @ dv01_vector
    
    if portfolio_variance < 0:
        logger.error(f"Portfolio variance is negative: {portfolio_variance}")
        raise ValueError("Portfolio variance calculation failed")
    
    portfolio_volatility = np.sqrt(portfolio_variance)
    
    logger.info(f"Portfolio Variance: ${portfolio_variance:,.2f}")
    logger.info(f"Portfolio Volatility (sigma_p): ${portfolio_volatility:,.2f}")
    
    # Calculate VaR at 95% and 99%
    var_95 = 0 - CONFIDENCE_95 * portfolio_volatility  # mean=0 for log returns
    var_99 = 0 - CONFIDENCE_99 * portfolio_volatility
    
    logger.info(f"\nPortfolio VaR (daily):")
    logger.info(f"  VaR@95%: ${var_95:,.2f}")
    logger.info(f"  VaR@99%: ${var_99:,.2f}")
    
    return portfolio_variance, portfolio_volatility, var_95, var_99

def write_results_to_excel(c_slot_details, portfolio_metrics):
    """Write portfolio VAR results to Excel"""
    logger.info(f"\nWriting results to Excel...")
    
    # Read existing workbook
    from openpyxl import load_workbook
    from openpyxl.utils.dataframe import dataframe_to_rows
    
    wb = load_workbook(EXCEL_FILE)
    
    # Remove existing PORTFOLIO and POSITIONS sheets if they exist
    if 'PORTFOLIO' in wb.sheetnames:
        del wb['PORTFOLIO']
    if 'POSITIONS' in wb.sheetnames:
        del wb['POSITIONS']
    
    # Create POSITIONS sheet
    logger.info("Creating POSITIONS sheet...")
    ws_pos = wb.create_sheet('POSITIONS', 0)
    
    pos_df = pd.DataFrame(c_slot_details)
    for r_idx, row in enumerate(dataframe_to_rows(pos_df, index=False, header=True), 1):
        for c_idx, value in enumerate(row, 1):
            ws_pos.cell(row=r_idx, column=c_idx, value=value)
    
    # Create PORTFOLIO sheet
    logger.info("Creating PORTFOLIO sheet...")
    ws_port = wb.create_sheet('PORTFOLIO', 1)
    
    # Portfolio summary
    ws_port['A1'] = 'Portfolio VaR Summary (C1-C35, FFc1-FFc35)'
    
    summary_data = [
        ['Metric', 'Value', 'Unit'],
        ['Portfolio Variance', portfolio_metrics['variance'], 'USD^2'],
        ['Portfolio Volatility', portfolio_metrics['volatility'], 'USD/day'],
        ['VaR @ 95% Confidence', portfolio_metrics['var_95'], 'USD'],
        ['VaR @ 99% Confidence', portfolio_metrics['var_99'], 'USD'],
        ['Calculation Date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ''],
        ['Total Positions (Traded)', portfolio_metrics['total_positions'], 'contracts'],
        ['Total DV01 (Traded)', portfolio_metrics['total_dv01'], 'USD/bp'],
        ['Contract Slots', '35', 'C1-C35'],
        ['Traded Slots', portfolio_metrics['traded_slots'], 'with positions'],
        ['Zero Positions', 35 - portfolio_metrics['traded_slots'], 'synthetic/future'],
    ]
    
    for r_idx, row in enumerate(summary_data, 3):
        for c_idx, value in enumerate(row, 1):
            ws_port.cell(row=r_idx, column=c_idx, value=value)
    
    # Save workbook
    wb.save(EXCEL_FILE)
    logger.info(f"Results written to {EXCEL_FILE}")

def main():
    """Main execution"""
    logger.info("="*70)
    logger.info("PORTFOLIO-LEVEL VAR CALCULATION (C1-C35)")
    logger.info("="*70)
    
    try:
        # Step 1: Get C-slot mapping (traded contracts only)
        partial_c_mapping, traded_series = get_c_slot_mapping_extended()
        
        # Step 2: Get live positions and multipliers
        positions_df = get_live_positions(partial_c_mapping)
        
        # Step 3: Extend mapping to full C1-C35
        full_c_mapping = build_full_c_mapping(partial_c_mapping)
        
        # Step 4: Build DV01 vector (C1-C35)
        dv01_vector, c_slot_details = build_dv01_vector(full_c_mapping, positions_df)
        
        # Step 5: Read Excel metrics (full FFc1-FFc35)
        correl_matrix, std_devs = read_excel_metrics(c_count=35)
        
        # Step 6: Build covariance matrix
        cov_matrix = build_covariance_matrix(correl_matrix, std_devs)
        
        # Step 7: Calculate portfolio VAR
        port_var, port_vol, var_95, var_99 = calculate_portfolio_var(dv01_vector, cov_matrix)
        
        # Step 8: Prepare metrics for output
        total_positions = positions_df['net_position'].sum()
        total_dv01 = dv01_vector.sum()
        traded_slots = len(partial_c_mapping)
        
        portfolio_metrics = {
            'variance': port_var,
            'volatility': port_vol,
            'var_95': var_95,
            'var_99': var_99,
            'total_positions': total_positions,
            'total_dv01': total_dv01,
            'traded_slots': traded_slots,
        }
        
        # Step 9: Write results to Excel
        write_results_to_excel(c_slot_details, portfolio_metrics)
        
        # Summary
        logger.info("\n" + "="*70)
        logger.info("PORTFOLIO VAR CALCULATION COMPLETE (C1-C35)")
        logger.info("="*70)
        logger.info(f"\nKey Results:")
        logger.info(f"  Portfolio Volatility: ${port_vol:,.2f}/day")
        logger.info(f"  Daily VaR@95%: ${var_95:,.2f}")
        logger.info(f"  Daily VaR@99%: ${var_99:,.2f}")
        logger.info(f"  Total Net Position (Traded): {total_positions:,} contracts")
        logger.info(f"  Total DV01 Sensitivity (Traded): ${total_dv01:,.2f}/bp")
        logger.info(f"  Traded Slots: {traded_slots} (C1-C{traded_slots})")
        logger.info(f"  Synthetic/Future Slots: {35 - traded_slots} (C{traded_slots+1}-C35)")
        logger.info("\n✓ Results written to Excel (POSITIONS and PORTFOLIO sheets)")
        logger.info(f"✓ Full correlation matrix (35x35) incorporated")
        
    except Exception as e:
        logger.error(f"ERROR: {e}", exc_info=True)
        raise

if __name__ == '__main__':
    main()
