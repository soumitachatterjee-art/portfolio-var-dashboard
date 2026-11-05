"""
Portfolio VAR Dashboard - Combined Flask App with Email Authentication
Serves both API and PWA frontend
Ready to deploy to Heroku
"""

from flask import Flask, jsonify, request, render_template_string, session, redirect, url_for, send_file
import pandas as pd
import numpy as np
import mysql.connector
from datetime import datetime, timedelta
import os
import logging
import secrets

app = Flask(__name__, static_folder='.', static_url_path='')
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))

# Enable CORS
from flask_cors import CORS
CORS(app, supports_credentials=True)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from environment or defaults
DB_HOST_STELLARRISK = os.getenv('DB_HOST_STELLARRISK', '')
DB_USER_STELLARRISK = os.getenv('DB_USER_STELLARRISK', '')
DB_PASS_STELLARRISK = os.getenv('DB_PASS_STELLARRISK', '')
DB_NAME_STELLARRISK = os.getenv('DB_NAME_STELLARRISK', '')

# Authentication
ALLOWED_EMAIL_DOMAIN = os.getenv('ALLOWED_EMAIL_DOMAIN', '@axxela.in')
SESSION_TIMEOUT = 86400  # 24 hours

EXCEL_FILE = os.path.join(os.path.dirname(__file__), 'FUT-01-41-VAR-CORREL.xlsx')
PRODUCT_NAME = 'CME 30DayFedFunds'
NUM_CONTRACTS = 35
CONFIDENCE_95 = 1.645
CONFIDENCE_99 = 2.326
STANDARD_MULTIPLIER = 4167.0

MONTH_MAP = {
    'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
    'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
}

# Cache for Excel metrics
_excel_cache = {'correl': None, 'std_devs': None, 'loaded_at': None}

# Authentication helpers
def is_valid_email(email):
    """Check if email is valid and from allowed domain"""
    if not email or '@' not in email:
        return False
    return email.lower().endswith(ALLOWED_EMAIL_DOMAIN.lower())

def login_required(f):
    """Decorator to check if user is logged in"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return jsonify({'error': 'Unauthorized', 'redirect': '/login'}), 401
        return f(*args, **kwargs)
    return decorated_function

def get_excel_metrics():
    """Load correlation and volatility metrics from Excel (cached)"""
    global _excel_cache
    
    try:
        correl_df = pd.read_excel(EXCEL_FILE, sheet_name='CORREL', header=0, index_col=0)
        ffc_labels = [f'FFc{i}' for i in range(1, NUM_CONTRACTS + 1)]
        correl_full = correl_df.loc[ffc_labels, ffc_labels]
        
        if not np.allclose(correl_full.values, correl_full.T.values, atol=1e-6):
            correl_full = (correl_full + correl_full.T) / 2
        
        var_df = pd.read_excel(EXCEL_FILE, sheet_name='VAR', skiprows=5, header=0, index_col=0)
        std_devs = var_df.loc[ffc_labels, 'Std.Dev']
        
        _excel_cache['correl'] = correl_full
        _excel_cache['std_devs'] = std_devs
        _excel_cache['loaded_at'] = datetime.now()
        
        return correl_full, std_devs
    except Exception as e:
        logger.error(f"Failed to load Excel metrics: {e}")
        return None, None

def parse_expiration_date(product_series):
    """Parse 'NOV26' -> (2026, 11)"""
    month_code = product_series[:3].upper()
    year_code = product_series[3:5]
    month = MONTH_MAP.get(month_code, 0)
    year = 2000 + int(year_code) if year_code else 0
    return (year, month)

def get_live_positions():
    """Query live positions from database"""
    try:
        conn = mysql.connector.connect(
            host=DB_HOST_STELLARRISK,
            user=DB_USER_STELLARRISK,
            password=DB_PASS_STELLARRISK,
            database=DB_NAME_STELLARRISK,
            connection_timeout=5
        )
        
        query = f"""
            SELECT product_series, SUM(open_position) as net_position, MAX(point_value) as point_value
            FROM positions_current
            WHERE product_name = '{PRODUCT_NAME}'
            GROUP BY product_series
        """
        
        df = pd.read_sql(query, con=conn)
        conn.close()
        return df
    except Exception as e:
        logger.error(f"Database error: {e}")
        return None

def get_c_slot_mapping(positions_df):
    """Get chronological C-slot mapping"""
    try:
        conn = mysql.connector.connect(
            host=DB_HOST_STELLARRISK,
            user=DB_USER_STELLARRISK,
            password=DB_PASS_STELLARRISK,
            database=DB_NAME_STELLARRISK,
            connection_timeout=5
        )
        cursor = conn.cursor(dictionary=True)
        
        query = f"SELECT DISTINCT product_series FROM positions_current WHERE product_name = '{PRODUCT_NAME}'"
        cursor.execute(query)
        series_list = [row['product_series'] for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        sorted_series = sorted(series_list, key=parse_expiration_date)
        
        partial_mapping = {}
        for i, series in enumerate(sorted_series, 1):
            partial_mapping[f'C{i}'] = series
        
        full_mapping = dict(partial_mapping)
        if sorted_series:
            last_series = sorted_series[-1]
            last_year, last_month = parse_expiration_date(last_series)
            
            current_slot = len(partial_mapping) + 1
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
        logger.error(f"Failed to get C-slot mapping: {e}")
        return {}

def build_dv01_vector(full_c_mapping, positions_df):
    """Build DV01 vector and details"""
    positions_dict = dict(zip(positions_df['product_series'], positions_df['net_position']))
    multiplier_dict = dict(zip(positions_df['product_series'], positions_df['point_value']))
    
    dv01_vector = []
    c_slot_details = []
    
    for i in range(1, NUM_CONTRACTS + 1):
        c_slot = f'C{i}'
        series = full_c_mapping[c_slot]
        position = positions_dict.get(series, 0)
        multiplier = multiplier_dict.get(series, STANDARD_MULTIPLIER)
        dv01 = position * multiplier
        
        dv01_vector.append(dv01)
        c_slot_details.append({
            'c_slot': c_slot,
            'series': series,
            'position': int(position) if position != 0 else 0,
            'multiplier': float(multiplier),
            'dv01': float(dv01)
        })
    
    return np.array(dv01_vector), c_slot_details

def build_covariance_matrix(correl_matrix, std_devs):
    """Build covariance matrix"""
    std_array = std_devs.values
    cov_matrix = correl_matrix.values * np.outer(std_array, std_array)
    return cov_matrix

def calculate_portfolio_var(dv01_vector, cov_matrix):
    """Calculate portfolio VAR"""
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

# Routes

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Email-only login (no password)"""
    if request.method == 'GET':
        # Check if already logged in
        if 'user_email' in session:
            return redirect(url_for('index'))
        # Serve login page
        with open('login.html', 'r') as f:
            return f.read()
    
    # POST: Handle login
    data = request.get_json() or request.form
    email = data.get('email', '').strip().lower()
    
    if not is_valid_email(email):
        return jsonify({'error': 'Invalid email. Must be @axxela.in domain.'}), 400
    
    # Set session
    session['user_email'] = email
    session['login_time'] = datetime.now().isoformat()
    
    return jsonify({'status': 'ok', 'redirect': '/'})

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    """Logout and clear session"""
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/user', methods=['GET'])
def get_user():
    """Get current logged-in user"""
    if 'user_email' not in session:
        return jsonify({'authenticated': False}), 401
    return jsonify({'authenticated': True, 'email': session.get('user_email')})

@app.route('/')
@login_required
def index():
    """Serve the PWA frontend (requires login)"""
    return send_file('index.html')

@app.route('/login.html')
def login_page():
    """Serve login page"""
    if 'user_email' in session:
        return redirect(url_for('index'))
    with open('login.html', 'r') as f:
        return f.read()

@app.route('/manifest.json')
def manifest():
    """Serve PWA manifest"""
    return send_file('manifest.json')

@app.route('/sw.js')
def service_worker():
    """Serve service worker"""
    return send_file('sw.js')

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})

@app.route('/api/var', methods=['GET'])
@login_required
def get_portfolio_var():
    """Calculate and return portfolio VAR"""
    try:
        correl_matrix, std_devs = get_excel_metrics()
        if correl_matrix is None:
            return jsonify({'error': 'Failed to load Excel metrics'}), 500
        
        positions_df = get_live_positions()
        if positions_df is None or positions_df.empty:
            return jsonify({'error': 'No positions or database error'}), 500
        
        full_c_mapping = get_c_slot_mapping(positions_df)
        dv01_vector, c_slot_details = build_dv01_vector(full_c_mapping, positions_df)
        cov_matrix = build_covariance_matrix(correl_matrix, std_devs)
        var_result = calculate_portfolio_var(dv01_vector, cov_matrix)
        
        if var_result is None:
            return jsonify({'error': 'Portfolio variance calculation failed'}), 500
        
        total_positions = float(positions_df['net_position'].sum())
        total_dv01 = float(dv01_vector.sum())
        traded_slots = len(positions_df)
        traded_details = [d for d in c_slot_details if d['position'] != 0]
        
        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'portfolio': {
                'variance': var_result['variance'],
                'volatility': var_result['volatility'],
                'var_95': var_result['var_95'],
                'var_99': var_result['var_99'],
                'total_positions': total_positions,
                'total_dv01': total_dv01,
                'traded_slots': traded_slots,
                'synthetic_slots': NUM_CONTRACTS - traded_slots
            },
            'positions': traded_details,
            'all_positions': c_slot_details
        })
    except Exception as e:
        logger.error(f"Error in /api/var: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/var/summary', methods=['GET'])
@login_required
def get_var_summary():
    """Get only summary metrics (lightweight)"""
    try:
        correl_matrix, std_devs = get_excel_metrics()
        if correl_matrix is None:
            return jsonify({'error': 'Failed to load Excel metrics'}), 500
        
        positions_df = get_live_positions()
        if positions_df is None or positions_df.empty:
            return jsonify({'error': 'No positions or database error'}), 500
        
        full_c_mapping = get_c_slot_mapping(positions_df)
        dv01_vector, _ = build_dv01_vector(full_c_mapping, positions_df)
        cov_matrix = build_covariance_matrix(correl_matrix, std_devs)
        var_result = calculate_portfolio_var(dv01_vector, cov_matrix)
        
        if var_result is None:
            return jsonify({'error': 'Portfolio variance calculation failed'}), 500
        
        total_positions = float(positions_df['net_position'].sum())
        total_dv01 = float(dv01_vector.sum())
        
        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'volatility': var_result['volatility'],
            'var_95': var_result['var_95'],
            'var_99': var_result['var_99'],
            'total_positions': total_positions,
            'total_dv01': total_dv01
        })
    except Exception as e:
        logger.error(f"Error in /api/var/summary: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV', 'production') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
