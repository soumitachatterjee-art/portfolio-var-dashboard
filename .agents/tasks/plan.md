# Implementation Plan: Portfolio-Level VAR Calculation

## Project Overview
Create `portfolio_var.py` to calculate aggregate portfolio-level Value-at-Risk (VaR) for 14 Federal Funds Futures instruments using parametric (analytical) methodology.

The calculation will:
1. Read the 14 active series' positions from `stellarrisk` DB (host 192.168.102.245)
2. Extract the 14×14 correlation submatrix from the CORREL sheet of FUT-01-41-VAR-CORREL.xlsx
3. Extract the Std.Dev vector for the 14 instruments from the VAR sheet
4. Apply portfolio-level VAR formulas: V = d' × Σ × d, σₚ = √V, VaR = -Z × σₚ
5. Add two new sheets (PORTFOLIO and POSITIONS) to the Excel file
6. Verify output with final_submission_check.py

---

## Data Mapping & Configuration

### FFc to Product Series Mapping (Chronological Order)
```
FFc1  → APR27,    FFc8  → JUL27
FFc2  → AUG27,    FFc9  → JUN27
FFc3  → DEC26,    FFc10 → MAR27
FFc4  → FEB27,    FFc11 → MAY27
FFc5  → FEB28,    FFc12 → NOV26
FFc6  → JAN27,    FFc13 → NOV27
FFc7  → JAN28,    FFc14 → OCT27
```

### Key Constants
- **Multiplier**: $4,167 per basis point (dᵢ = net_positionᵢ × 4,167)
- **Z-scores**: 1.645 (95% confidence), 2.326 (99% confidence)
- **Mean daily log returns**: 0 (assumed for parametric VaR)
- **Target Excel file**: `FUT-01-41-VAR-CORREL.xlsx`
- **Positions DB**: Host 192.168.102.245, user risk_reader / <database-password>, db stellarrisk
- **Positions table**: `positions_current`

---

## Implementation Steps

### Step 1: Database Connection & Position Retrieval
**Task**: Query `stellarrisk` DB to fetch current net positions for the 14 instruments.

**SQL Query to Use**:
```sql
SELECT 
    product_series,
    SUM(open_position) as net_position
FROM positions_current
WHERE product_name = 'CME 30DayFedFunds'
GROUP BY product_series
ORDER BY product_series ASC
```

**Files to Create/Modify**: `portfolio_var.py` (new)

**Implementation Notes**:
- Use mysql.connector with credentials: host='192.168.102.245', user='risk_reader', password='<database-password>', database='stellarrisk'
- Map returned product_series to FFc1-FFc14 using the chronological order above
- Store as dict: `{product_series: net_position, ...}` and separately as ordered list aligned to FFc1-FFc14
- Validate all 14 series are present; fail gracefully if any are missing

**Verify**: 
- Python can import mysql.connector; connection established successfully
- Query returns exactly 14 rows with expected product series
- Net positions are numeric (integers or floats)

---

### Step 2: Excel Data Extraction – Correlation Matrix
**Task**: Read the 14×14 correlation submatrix from the CORREL sheet (FFc1-FFc14 only).

**Excel Sheet Layout (Confirmed)**:
- **Sheet name**: CORREL
- **Dimensions**: 36×36 (A1:AJ36) – contains all 35 FFc instruments
- **Row 1, Col 1**: Empty (top-left corner)
- **Row 1, Col 2-36**: Column headers (FFc1, FFc2, ..., FFc35)
- **Col 1, Row 2-36**: Row headers (FFc1, FFc2, ..., FFc35)
- **Data**: Correlation values in openpyxl cell (row+1, col+1) where row/col index the instruments
- **FFc14 location**: Column O (col 15), Row 15

**Extraction Strategy**:
1. Use `openpyxl` to load the workbook and access CORREL sheet
2. Read cells from openpyxl directly (more precise than pandas for subset extraction):
   - Rows 2-15 (for FFc1-FFc14), Columns B-O (Excel columns B through O, i.e., openpyxl columns 2-15)
   - This gives a 14×14 submatrix
3. Convert to numpy array for matrix operations
4. Validate: diagonal elements ≈ 1.0, all values ∈ [-1, 1], symmetric

**Files to Modify**: `portfolio_var.py`

**Implementation Notes**:
- Use `openpyxl.load_workbook(filename)` with data_only=False (we need formulas/values)
- Iterate: `for row in range(2, 16): for col in range(2, 16): value = ws[f'{col_letter}{row}'].value`
- Convert to numpy: `correl_matrix = np.array([[float(ws.cell(r, c).value) for c in range(2, 16)] for r in range(2, 16)])`
- Use pandas `.iloc[0:14, 0:14]` alternative after reading full matrix with pandas, then subset

**Verify**:
- 14×14 matrix extracted without NaN
- Diagonal all ≈ 1.0
- All off-diagonal ∈ [-1, 1]
- Matrix is symmetric (within floating-point tolerance)

---

### Step 3: Excel Data Extraction – Std.Dev Vector
**Task**: Read the Std.Dev column for FFc1-FFc14 from the VAR sheet.

**Excel Sheet Layout (Confirmed)**:
- **Sheet name**: VAR
- **Header row**: Row 6 (Instrument, Mean, Std.Dev, Variance, Skewness, Kurtosis, VaR_95%, VaR_99%)
- **Std.Dev column**: Column C (col 3)
- **Data rows**: Row 7 onwards (FFc1 at row 7, FFc2 at row 8, ..., FFc14 at row 20)
- **Metadata rows**: Rows 1-5 contain title, calculation date, data period, trading days

**Extraction Strategy**:
1. Use pandas: `df_var = pd.read_excel(file, sheet_name='VAR', skiprows=5, index_col=0)`
   - This reads headers from row 6 (after skiprows=5)
   - Index becomes instrument names (FFc1, FFc2, ...)
   - Column 'Std.Dev' is directly accessible
2. Extract subset for FFc1-FFc14:
   - `std_dev_vector = df_var.loc['FFc1':'FFc14', 'Std.Dev'].values`
   - Ensure order matches FFc1-FFc14 in chronological order from Step 1

**Files to Modify**: `portfolio_var.py`

**Implementation Notes**:
- Std.Dev in the VAR sheet is in daily log-return percentage units (%)
- Validation: all Std.Dev > 0, typically 0.05–0.5 range for Fed Funds

**Verify**:
- Vector has 14 elements
- All positive
- Values in reasonable range (0.01–1.0)
- Order matches FFc1-FFc14

---

### Step 4: Calculate Dollar Sensitivity Vector (d)
**Task**: Convert net positions to dollar sensitivities using the multiplier.

**Formula**: d_i = net_position_i × 4,167

**Files to Modify**: `portfolio_var.py`

**Implementation Notes**:
- Ensure positions are aligned to FFc1-FFc14 order (from Step 1)
- Handle zero positions gracefully (they contribute 0 to portfolio volatility)
- Result: numpy array of length 14, units = USD per 0.01% move (per basis point)

**Verify**:
- Vector has 14 elements
- All numeric (float or int)
- Order matches FFc1-FFc14

---

### Step 5: Construct Covariance Matrix (Σ)
**Task**: Build the 14×14 covariance matrix using the correlation matrix and Std.Dev vector.

**Formula**: Σ_ij = ρ_ij × σ_i × σ_j

**Files to Modify**: `portfolio_var.py`

**Implementation Notes**:
- Load correlation matrix from Step 2: ρ (14×14)
- Load Std.Dev vector from Step 3: σ (14,)
- Compute:
  ```python
  # Vectorized approach
  sigma_matrix = np.outer(std_dev_vector, std_dev_vector)
  covariance = correlation_matrix * sigma_matrix
  ```
- Validate: covariance is symmetric, positive semi-definite (eigenvalues ≥ 0)

**Verify**:
- Matrix shape: (14, 14)
- Symmetric (within machine precision)
- Diagonal elements = σ_i² (variance)
- Eigenvalues all ≥ 0 (positive semi-definite)

---

### Step 6: Calculate Portfolio Variance and Volatility
**Task**: Apply the portfolio variance formula V = d' × Σ × d and compute portfolio volatility.

**Formulas**:
- Portfolio variance: V = d^T × Σ × d (scalar, units: USD²)
- Portfolio volatility: σ_p = √V (units: USD)

**Files to Modify**: `portfolio_var.py`

**Implementation Notes**:
```python
d = dollar_sensitivity_vector  # shape (14,)
sigma = covariance_matrix      # shape (14, 14)
portfolio_variance = d @ sigma @ d  # matrix mult: d' × Σ × d
portfolio_volatility = np.sqrt(portfolio_variance)
```
- Result units: USD (the sensitivity is in USD/bp, std dev is in %, so product is USD)
- Portfolio volatility represents the 1-std-dev move in the portfolio value

**Verify**:
- Portfolio variance is positive
- Portfolio volatility = sqrt(variance)
- Both are numeric scalars

---

### Step 7: Calculate VaR Metrics (95% and 99%)
**Task**: Compute portfolio-level VaR at 95% and 99% confidence levels.

**Formulas**:
- VaR@95% = 0 − 1.645 × σ_p = −1.645 × σ_p (loss, negative value in USD)
- VaR@99% = 0 − 2.326 × σ_p = −2.326 × σ_p (loss, negative value in USD)

**Files to Modify**: `portfolio_var.py`

**Implementation Notes**:
- Assume mean daily returns = 0 (conservative for Fed Funds daily returns)
- Z-scores: 1.645 (95%), 2.326 (99%)
- Result: both are negative (representing maximum expected loss)
- Interpretation: "The portfolio has a 5% (1%) chance of losing more than |VaR@95%| (|VaR@99%|) USD in a single day"

**Verify**:
- VaR@95% and VaR@99% are both negative
- |VaR@99%| > |VaR@95%| (higher confidence → larger potential loss)
- Ratio |VaR@99%| / |VaR@95%| ≈ 2.326 / 1.645 ≈ 1.414

---

### Step 8: Create PORTFOLIO Summary Sheet in Excel
**Task**: Add a new PORTFOLIO sheet to FUT-01-41-VAR-CORREL.xlsx with portfolio-level summary.

**Sheet Layout**:
```
Row 1:  "PORTFOLIO ANALYSIS" (title)
Row 2:  "Calculation Date: [date]"
Row 3:  "Instruments: FFc1-FFc14 (14 active CME 30DayFedFunds contracts)"
Row 4:  ""
Row 5:  "Metric" | "Value" | "Unit"
Row 6:  "Total Dollar Exposure" | [sum of |d_i|] | "USD"
Row 7:  "Portfolio Variance" | [V] | "USD²"
Row 8:  "Portfolio Volatility" | [σ_p] | "USD"
Row 9:  ""
Row 10: "Value-at-Risk (Daily)"
Row 11: "VaR @ 95% Confidence" | [VaR@95%] | "USD"
Row 12: "VaR @ 99% Confidence" | [VaR@99%] | "USD"
Row 13: ""
Row 14: "Contribution to Portfolio Volatility"
Row 15: [Column headers: Instrument | Net Position | Dollar Sensitivity | Std.Dev | Contribution %]
Row 16+: [One row per FFc1-FFc14 with individual metrics]
```

**Files to Modify**: `portfolio_var.py`

**Implementation Notes**:
- Use openpyxl Workbook.create_sheet() or worksheet
- Add formatting: headers bold/blue, numeric values with 2-4 decimal places, currency format where appropriate
- Calculate contribution to volatility per instrument: `(d_i × σ_i) / σ_p × 100` or variance contribution
- Order: FFc1-FFc14 chronologically
- Do NOT overwrite existing sheets (CORREL, VAR, LOG_RETURNS remain unchanged)

**Verify**:
- PORTFOLIO sheet exists in the workbook
- All metrics are populated
- No #REF! or #DIV/0! errors
- Formatting is clean and readable

---

### Step 9: Create POSITIONS Sheet in Excel
**Task**: Add a new POSITIONS sheet documenting the current positions for each instrument.

**Sheet Layout**:
```
Row 1:  "POSITION SNAPSHOT" (title)
Row 2:  "As of: [today's date]"
Row 3:  "Data Source: stellarrisk DB, positions_current table"
Row 4:  ""
Row 5:  [Column headers: FFc Code | Product Series | Net Position | Dollar Sensitivity (per bp) | Comments]
Row 6+: [One row per FFc1-FFc14]
```

**Files to Modify**: `portfolio_var.py`

**Implementation Notes**:
- Use openpyxl to write
- FFc Code (FFc1–FFc14), Product Series (APR27–OCT27), Net Position (from DB query), Dollar Sensitivity (d_i)
- Comments: "Long" / "Short" / "Flat" based on sign of net position
- Include row totals: SUM(Net Position), SUM(Dollar Sensitivity)
- Formatting: number format for positions (0 decimal places), currency for sensitivities

**Verify**:
- POSITIONS sheet exists
- All 14 instruments listed
- Data matches DB query results
- SUM rows calculate correctly

---

### Step 10: Integration & Error Handling
**Task**: Build complete `portfolio_var.py` script with error handling and logging.

**Files to Modify**: `portfolio_var.py` (complete)

**Implementation Notes**:
- Wrap DB connection in try/except; graceful connection failure with error message
- Validate data at each step (presence, ranges, NaN checks)
- Log progress to console with visual indicators (✓ for success, ✗ for failure)
- Catch and report:
  - Missing instruments in positions (should have all 14)
  - Mismatched ordering between FFc and product_series
  - Negative variance (should never occur)
  - NaN or inf in calculations
  - File I/O errors (Excel read/write)
- Output to console: summary of calculations, portfolio VaR figures, file path written

**Verify**:
- Script runs without exceptions
- Output file created with both PORTFOLIO and POSITIONS sheets
- Console output shows all key metrics

---

### Step 11: Verify with final_submission_check.py
**Task**: Run the existing validation script to ensure no existing sheets were corrupted and new sheets are present.

**Files to Use**: `final_submission_check.py` (existing, no modification)

**Implementation Notes**:
- Before running this step, the coder's script must have written PORTFOLIO and POSITIONS sheets
- **Update**: final_submission_check.py currently checks only 3 base sheets (LOG_RETURNS, CORREL, VAR). After portfolio_var.py completes, PORTFOLIO and POSITIONS sheets will be new additions.
- The final_submission_check.py will still pass its current checks (base sheets intact)
- Add a manual post-run check: open the Excel file and verify PORTFOLIO and POSITIONS tabs exist and contain expected data

**Verify**:
- Run: `python final_submission_check.py`
- Expected output: "READY FOR SUBMISSION" or similar (base 3 sheets intact)
- Manual check: PORTFOLIO and POSITIONS sheets are present in the saved Excel file

---

### Step 12: Output & Documentation
**Task**: Summarize the calculation results and document the portfolio VaR output.

**Files to Modify**: `portfolio_var.py` (final output summary)

**Implementation Notes**:
- Print to console:
  ```
  ============================================================
  PORTFOLIO-LEVEL VAR CALCULATION COMPLETE
  ============================================================
  File: [path to FUT-01-41-VAR-CORREL.xlsx]
  
  Portfolio Metrics (Daily):
    • Volatility: $[X] USD
    • VaR @ 95%: $[Y] USD
    • VaR @ 99%: $[Z] USD
  
  Sheets Added:
    ✓ PORTFOLIO (summary + contribution analysis)
    ✓ POSITIONS (current position snapshot)
  
  Validation: PASSED ✓
  ============================================================
  ```
- Include timestamp and number of instruments processed

**Verify**:
- Output is informative and accurate
- File saved successfully
- User can see results at a glance

---

## Unit & Scaling Notes

### Critical Units Verification
1. **Net Position**: Contract count (typically integers, can be large: 100s-1000s)
2. **Multiplier (4,167)**: USD per basis point (0.01%) move per contract
3. **Dollar Sensitivity (d_i)**: net_position_i × 4,167 = USD per bp
   - Example: 100 contracts × 4,167 = 416,700 USD per bp
4. **Std.Dev from VAR sheet**: Daily log-return % (e.g., 0.15%)
5. **Covariance matrix**: % × % (daily log-return variance between instruments)
6. **Portfolio Variance**: (USD per bp) × (% correlation matrix) × (USD per bp) × (% squared) → works out to USD² when simplified
   - More precisely: d' × (σ_outer σ_outer) × d where σ are in % → result is USD²
7. **Portfolio Volatility**: √(USD²) = USD
8. **VaR**: Z-score (dimensionless) × Volatility (USD) = USD

### No Additional Scaling Needed
- The VAR sheet Std.Dev is already in daily %, matching correlation matrix scale
- Multiplier 4,167 converts position count → USD per bp
- Final VaR is in USD, directly interpretable as daily loss
- **Do NOT scale Std.Dev by 100** — it is already in %, correlation is dimensionless ratio

---

## Dependency Flow
```
Step 1: Query positions_current
  ↓
Step 2: Extract correlation matrix (14×14)
Step 3: Extract Std.Dev vector (14,)
Step 4: Calculate d = position × 4,167
  ↓
Step 5: Build covariance Σ = ρ ⊗ σσ'
  ↓
Step 6: Variance V = d' Σ d
Step 7: Volatility σ_p = √V
  ↓
Step 8: VaR@95% = −1.645 × σ_p
Step 9: VaR@99% = −2.326 × σ_p
  ↓
Step 10: Write PORTFOLIO sheet with results
Step 11: Write POSITIONS sheet with current holdings
  ↓
Step 12: Verify with final_submission_check.py
```

---

## Testing Strategy

1. **Unit Tests** (manual execution):
   - DB connection: verify 14 rows returned, all product_series present
   - Correlation matrix: verify 14×14, symmetric, diagonal ≈ 1
   - Std.Dev: verify 14 values, all positive
   - Covariance: verify symmetric, positive semi-definite
   - Portfolio VaR: verify sign (negative), magnitude reasonable (typically 10k–1M USD for Fed Funds)

2. **Integration Test**:
   - Run portfolio_var.py from workspace root
   - Verify no exceptions
   - Check Excel file opens and has both PORTFOLIO and POSITIONS sheets
   - Run final_submission_check.py and confirm "READY FOR SUBMISSION"

3. **Regression Test**:
   - Existing LOG_RETURNS, CORREL, VAR sheets unchanged (final_submission_check.py confirms)
   - No data corruption in base sheets after portfolio_var.py writes new sheets

---

## Files Summary

| File | Status | Purpose |
|------|--------|---------|
| `portfolio_var.py` | **NEW** | Main calculation script |
| `FUT-01-41-VAR-CORREL.xlsx` | MODIFY | Add PORTFOLIO and POSITIONS sheets; keep existing 3 sheets |
| `final_submission_check.py` | USE | Validation (no changes needed) |
| `map_ffc_to_series.py` | REFERENCE | Position query pattern; use as guide for DB connection |
| `calculate_var_correl.py` | REFERENCE | Excel writing pattern; use for openpyxl formatting |

---

## Key Success Criteria

- [ ] portfolio_var.py retrieves all 14 instrument positions from DB
- [ ] Correlation and Std.Dev extracted correctly from Excel
- [ ] Portfolio variance, volatility, and VaR calculated correctly (formulas verified)
- [ ] PORTFOLIO sheet created with summary metrics and contribution analysis
- [ ] POSITIONS sheet created with current position snapshot
- [ ] Excel file remains valid and uncorrupted (final_submission_check.py passes)
- [ ] No NaN, inf, or negative variance in calculations
- [ ] Script runs without exceptions and outputs clear summary

---

## Deliverable

**Output file**: `c:\Users\Axxela\Desktop\VAR\FUT-01-41-VAR-CORREL.xlsx`

**New sheets**:
1. **PORTFOLIO**: Portfolio-level VAR, volatility, variance, and per-instrument contribution metrics
2. **POSITIONS**: Current holdings and dollar sensitivities for each FFc1-FFc14

**Console output**: Summary of portfolio VaR@95%, VaR@99%, and validation status

**Verification**: Run `python final_submission_check.py` → expect "READY FOR SUBMISSION"
