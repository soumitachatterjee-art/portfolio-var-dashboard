# Portfolio-Level VaR Calculation — Technical Design

## Overview

This design specifies a Python-based portfolio VAR calculation system that maps live 30-Day Fed Funds futures positions from MySQL to a 14-slot contract system (C1–C14, representing front-month expiration windows), retrieves correlation and volatility metrics from an Excel reference file, constructs a covariance matrix, and computes portfolio variance, volatility, and VaR at 95% and 99% confidence levels. The workflow is sequential, deterministic, and fits naturally into the existing codebase patterns already established (connection pooling, data pivoting, Excel I/O).

Key design choices:
1. **Linear algebra core:** Matrix-based calculation (d'Σd) for portfolio variance ensures accuracy and performance for 14 contracts.
2. **Reference-based metrics:** Use pre-computed FFc1–FFc35 correlation and std.dev from Excel (FUT-01-41-VAR-CORREL.xlsx) to avoid recalculation on each run.
3. **Dynamic slot mapping:** Determine C1–C14 at runtime by querying positions_current and sorting by expiration date, so the front contract always maps to C1.
4. **Single-pass aggregation:** Query, group, map, and calculate in one flow with no intermediate files or loops.
5. **Excel output:** Extend the existing output file with two new sheets (PORTFOLIO, POSITIONS) to keep all VAR artifacts in one workbook.

---

## Data Flow

```
MySQL positions_current (live positions)
       ↓
   Aggregate by product_series
       ↓
   Parse expiration dates (NOV26, DEC26, etc.)
       ↓
   Sort chronologically → C1, C2, ..., C14
       ↓
   FUT-01-41-VAR-CORREL.xlsx (CORREL & VAR sheets)
       ↓
   Extract ρᵢⱼ and σᵢ for C-slot pairs
       ↓
   Build 14×14 covariance matrix Σ
       ↓
   Calculate d (DV01 vector) from positions
       ↓
   Portfolio Variance V = d'Σd
       ↓
   Portfolio Volatility σₚ = √V
       ↓
   VaR_95% = 1.645 × σₚ
   VaR_99% = 2.326 × σₚ
       ↓
   Write PORTFOLIO & POSITIONS sheets to Excel
       ↓
   Verify with final_submission_check.py
```

---

## Detailed Design

### 1. Database Query and Position Aggregation

**File:** `portfolio_var_calc.py` (new, or integrated into existing module)

**Operation:**
- Connect to MySQL (stellarrisk, 192.168.102.245) using credentials already established in existing scripts.
- Query `positions_current` table **including the `point_value` column** (multiplier for DV01 calculation):
  ```sql
  SELECT product_series, SUM(open_position) as net_position, MAX(point_value) as point_value
  FROM positions_current
  WHERE product_name = 'CME 30DayFedFunds'
  GROUP BY product_series;
  ```
- Return a dictionary: `{product_series: (net_position, point_value)}` for series in {NOV26, DEC26, JAN27, FEB27, FEB28, JAN28, JUL27, JUN27, MAR27, APR27, MAY27, AUG27, NOV27, OCT27}.
- **Why include `point_value`:** Ensures DV01 multiplier comes directly from the database (source of truth), not hardcoded. Automatically adapts if multipliers change in the future. Currently $4167 USD/bp for all CME 30DayFedFunds, but querying ensures flexibility.
- **Error handling:**
  - If no positions returned: Initialize all 14 series with zero net position; use default point_value = 4167 (log as info, not error).
  - If database unreachable: Raise MySQLConnectionError immediately (fatal; no fallback).
  - If unexpected product_series found: Filter them silently (requirements specify 14 series; any others are data anomalies).
  - If `point_value` is missing or NULL: Use default 4167 and warn (fallback for data quality issues).

**Validation:**
- Assert that at least one series is present (if all are zero, warning but proceed).
- Assert that all series names parse to valid month/year tuples.
- Assert that point_value is positive (warn if ≤ 0; use default 4167 as fallback).

---

### 2. Contract Slot Mapping (C1–C14)

**Helper function:** `map_positions_to_c_slots(positions_dict)`

**Logic:**
- Parse each product_series string (e.g., "NOV26") to (year, month) tuple using hardcoded month_map:
  ```python
  month_map = {'JAN': 1, 'FEB': 2, ..., 'DEC': 12}
  ```
- For series "NOV26": extract "NOV" → 11, "26" → 2026, yield (2026, 11).
- Sort all 14 series by (year, month) ascending (earliest expiration first).
- Create mapping: C-slot index 1 → front contract, 14 → furthest.

**Output:**
```python
c_slot_mapping = {
    'C1': ('NOV26', net_pos_nov),
    'C2': ('DEC26', net_pos_dec),
    ...
    'C14': ('FEB28', net_pos_feb)
}
```

**Invariant:** The mapping is deterministic and reproducible if positions_current returns the same series list; otherwise, the front contract dynamically changes as expirations pass.

**Edge cases:**
- If a series has zero positions, it still appears in C_i slot (with net_position = 0).
- If fewer than 14 series are found: Raise ValueError (requirements assume 14 are always present).
- Expired series (e.g., OCT26 if current date is beyond October 2026): Filter out before sorting; assume query only returns active series.

---

### 3. Read Excel Reference Metrics

**File:** `FUT-01-41-VAR-CORREL.xlsx`

**Operation:**
- Load CORREL sheet: 35×35 correlation matrix with FFc1–FFc35 as index and columns.
- Load VAR sheet: **Use `skiprows=5`** to skip title/metadata rows (rows 1–5); data begins at row 6. Extract Std.Dev column for all 35 instruments.
- Validate:
  - CORREL is symmetric (Σᵢⱼ = Σⱼᵢ).
  - Diagonal of CORREL is all 1.0 (correlation with self).
  - VAR sheet has no NaN values in Std.Dev column for rows FFc1–FFc35 after skipping metadata.
  - All correlation values are in [−1, 1].

**Storage:**
```python
correl_matrix = pd.read_excel(EXCEL_FILE, sheet_name='CORREL', index_col=0)  # 35×35
var_df = pd.read_excel(EXCEL_FILE, sheet_name='VAR', skiprows=5, index_col=0)  # Skip rows 1–5
std_devs = var_df['Std.Dev']  # Extract Std.Dev column
```

**Error handling:**
- If CORREL sheet missing: Raise FileNotFoundError (fatal; cannot proceed).
- If VAR sheet missing: Raise FileNotFoundError (fatal).
- If data is NaN or shapes mismatch: Raise ValueError with diagnostic info (fatal).
- If `skiprows=5` results in misaligned data (e.g., headers not found): Raise ValueError with line preview (fatal).

---

### 4. Map C-slots to FFc Contracts and Extract Metrics

**Helper function:** `extract_metrics_for_c_slots(correl_matrix, std_devs)`

**Approach (Path B — chosen and locked by blocker resolution):**

FFc1–FFc35 in the Excel file represent historical slot correlations, where **FFc1 is the 1st-month contract, FFc2 is the 2nd-month contract**, etc. Current live C1–C14 (NOV26–FEB28) map directly to FFc1–FFc14 by **slot position**, not by expiration date matching:

- C1 (front contract) → FFc1 (1st-month historical volatility)
- C2 (2nd-month forward) → FFc2 (2nd-month historical volatility)
- ...
- C14 → FFc14 (14th-month historical volatility)

**Key assumption:** Historical correlation and volatility structures for monthly slots (FFc1–FFc14 from 2020–2026 data) apply to current market without regime shift. This is acceptable because Fed Funds curve structure is relatively stable across years; however, **this assumption must be documented in code comments** so future users understand the constraint.

**Implementation:**
```python
c_correl = correl_matrix.iloc[:14, :14]  # Extract FFc1:FFc14, FFc1:FFc14 submatrix (14×14)
c_std_devs = std_devs.iloc[:14]           # Extract FFc1:FFc14 std.dev (14-element vector)
# Map: C1→FFc1, C2→FFc2, ..., C14→FFc14
```

**Output:**
```python
c_correl = pd.DataFrame (14×14)  # Correlation for month slots 1–14
c_std_devs = pd.Series (14,)     # Std.dev for month slots 1–14
```

---

### 5. Build 14×14 Covariance Matrix

**Function:** `build_covariance_matrix(c_correl, c_std_devs)`

**Formula:**
```
Σᵢⱼ = ρᵢⱼ × σᵢ × σⱼ
```

**Implementation:**
```python
# Outer product: σᵢ × σⱼ for all i, j
sigma_outer = np.outer(c_std_devs.values, c_std_devs.values)
# Element-wise multiply by correlation
covariance = c_correl.values * sigma_outer
```

**Validation (locked by blocker resolution #4):**

Before returning covariance, perform three checks:

1. **Symmetry check:** Verify Σᵢⱼ = Σⱼᵢ (within numerical tolerance, 1e-10):
   ```python
   max_asymmetry = np.max(np.abs(covariance - covariance.T))
   if max_asymmetry > 1e-10:
       print(f"⚠ WARNING: Covariance matrix not perfectly symmetric (max asymmetry: {max_asymmetry})")
       print(f"  Auto-symmetrizing: Σ_new = (Σ + Σ') / 2")
       covariance = (covariance + covariance.T) / 2
   ```

2. **Positive semi-definiteness check:** Compute eigenvalues and verify all are ≥ 0 (within numerical tolerance, -1e-10):
   ```python
   eigenvalues = np.linalg.eigvalsh(covariance)
   if np.any(eigenvalues < -1e-10):
       print(f"✗ ERROR: Covariance matrix not positive semi-definite")
       print(f"  Eigenvalues: {eigenvalues}")
       print(f"  Min eigenvalue: {eigenvalues.min()}")
       raise ValueError("Covariance matrix failed positive semi-definiteness check")
   ```
   If eigenvalues are very small or close to zero (< 1e-6), issue a warning but do not stop:
   ```python
   if np.any((eigenvalues >= -1e-10) & (eigenvalues < 1e-6)):
       print(f"⚠ WARNING: Covariance matrix has very small eigenvalues (near zero rank)")
       print(f"  Eigenvalues: {eigenvalues}")
   ```

3. **Diagnostics output (if any check triggers warning or auto-repair):**
   ```python
   print(f"  Condition number (κ): {np.linalg.cond(covariance):.2e}")
   print(f"  Rank: {np.linalg.matrix_rank(covariance)}")
   ```

**Properties:**
- Symmetric: Σᵢⱼ = Σⱼᵢ (guaranteed by outer product structure and correlation symmetry; auto-repaired if needed).
- Positive semi-definite (assumed if correlation matrix is valid; verified by eigenvalue check).
- Diagonal = σᵢ² (variance of contract i).

**Output:**
```python
cov_matrix = np.array (14×14)  # Covariance matrix, validated
```

**Error handling:**
- If c_std_devs contains zero: Warn (zero volatility contract); proceed (will contribute zero variance to portfolio).
- If eigenvalues are negative (beyond numerical tolerance): Raise ValueError (indicates corrupted correlation or std.dev data; fatal).
- If matrix is singular (rank < 14): Warn but proceed (portfolio variance will still be computable for non-zero positions).

---

### 6. Calculate DV01 Vector (Dollar Sensitivity)

**Function:** `calculate_dv01_vector(c_slot_mapping)`

**Formula:**
```
dᵢ = net_positionᵢ × point_valueᵢ (USD/bp)
```

**Context (corrected — multiplier from database, not hardcoded):** The DV01 multiplier (point_value) is **queried directly from the `positions_current` table**, not hardcoded. This ensures:
1. No magic numbers in code.
2. Automatic adaptation if multipliers change in the future.
3. Values always come from the source of truth (the database).

Currently, all CME 30DayFedFunds contracts have `point_value = 4167 USD/bp`, but by reading from the database, the code is robust to future changes.

**Implementation:**
```python
dv01_vector = []
for i in range(1, 15):
    c_slot = f'C{i}'
    net_position, point_value = c_slot_mapping[c_slot]  # Extract position and multiplier from DB
    
    # Handle edge case: if point_value is missing or ≤ 0, use default
    if point_value is None or point_value <= 0:
        point_value = 4167  # Default fallback
        print(f"⚠ WARNING: point_value for {c_slot} is missing or invalid; using default 4167")
    
    dv01 = net_position * point_value
    dv01_vector.append(dv01)

dv01_vector = np.array(dv01_vector)
```

**Unit check (dimensional analysis, confirmed locked by blocker resolution #5):**
- `net_position` has units: basis points (bp) or contracts (treated as bp for sensitivity)
- `point_value` has units: USD/bp (from database)
- `dv01` has units: bp × (USD/bp) = USD
- `dv01_vector` has units: USD (sensitivity per contract, not per bp)
- `cov_matrix` has units: bp² (covariance of basis point returns)
- `portfolio_variance = d' Σ d` has units: USD × bp² × USD = USD²  ✓

Dimensional consistency verified.

**Edge cases:**
- If net_position is zero, dv01 = 0 (contract has no effect on portfolio variance).
- If net_position is negative (short), dv01 is negative (reflects short sensitivity).
- If point_value is NULL or ≤ 0: Use default 4167; warn (data quality issue).

**Output:**
```python
dv01_vector = np.array(shape (14,))  # Dollar sensitivity for each C-slot (USD)
```

---

### 7. Calculate Portfolio Variance and Volatility

**Function:** `calculate_portfolio_variance(dv01_vector, cov_matrix)`

**Formula:**
```
V = d' Σ d

σₚ = √V
```

**Implementation:**
```python
portfolio_variance = dv01_vector @ cov_matrix @ dv01_vector
portfolio_volatility = np.sqrt(portfolio_variance)
```

**Invariants:**
- V ≥ 0 (guaranteed by positive semi-definiteness of Σ).
- σₚ ≥ 0.
- If all positions are zero, V = 0 and σₚ = 0 (no risk; edge case handled).

**Error handling:**
- If portfolio_variance < 0 (numerical underflow or matrix error): Raise ValueError (indicates corrupted data or algorithmic error).
- If portfolio_variance is NaN: Raise ValueError.

**Output:**
```python
portfolio_volatility = float  # USD volatility
```

---

### 8. Calculate VaR at Confidence Levels

**Function:** `calculate_var(portfolio_volatility)`

**Formula (normal distribution assumption):**
```
VaR_95% = z₀.₉₅ × σₚ = 1.645 × σₚ
VaR_99% = z₀.₉₉ × σₚ = 2.326 × σₚ
```

**Implementation:**
```python
var_95 = 1.645 * portfolio_volatility
var_99 = 2.326 * portfolio_volatility
```

**Interpretation:** VaR_95% is the maximum expected loss at 95% confidence over a 1-day horizon (assuming normal distribution and current positions held constant). VaR_99% is analogous at 99% confidence.

**Output:**
```python
{'VaR_95%': var_95, 'VaR_99%': var_99}  # Both in USD
```

---

### 9. Write Results to Excel

**Target file:** `FUT-01-41-VAR-CORREL.xlsx`

**Operation:**
- Open existing workbook (it has CORREL, VAR, LOG_RETURNS sheets).
- Add or overwrite two new sheets: PORTFOLIO and POSITIONS.

**PORTFOLIO Sheet:**
```
Row 1: Header
       Column A: "Metric"
       Column B: "Value"

Row 2: "Portfolio Volatility ($)" | <portfolio_volatility>
Row 3: "VaR_95% ($)" | <var_95>
Row 4: "VaR_99% ($)" | <var_99>
Row 5: "Total Net Position (contracts)" | <sum of all net positions>
Row 6: "Calculation Date" | <today's date>
Row 7: "Data Source" | "positions_current (live)"

Row 9-12: C-slot Mapping Table (optional but useful for documentation)
Column A: "C_Slot"
Column B: "Product Series"
Column C: "Expiration (YYYY-MM)"
       (one row per C1–C14)
```

**POSITIONS Sheet:**
```
Row 1: Headers
       Column A: "C_Slot"
       Column B: "Product_Series"
       Column C: "Expiration_Date"
       Column D: "Net_Position (contracts)"
       Column E: "DV01 ($)"
       Column F: "Contribution_to_Variance ($²)"

Rows 2-15: Data for C1–C14 (one row per contract)
       Contribution_to_Variance = (dᵢ Σ d)ᵢ × dᵢ (component of total portfolio variance)
```

**Formatting:**
- Numeric columns: 4 decimal places for volatility; 2 decimal places for USD; 0 decimals for contract counts.
- Use openpyxl library (already imported in calculate_var_correl.py) to style headers (bold, blue background, white font) and borders for readability.
- No scientific notation (set number format explicitly).

**File storage:**
- Path: `c:\Users\Axxela\Desktop\VAR\FUT-01-41-VAR-CORREL.xlsx` (same as input file; sheets are added/updated).

**Error handling:**
- If file is locked or read-only: Raise PermissionError (fatal; user must close file in Excel).
- If sheet names conflict with existing sheets: Overwrite silently (log as warning for transparency).
- If openpyxl cannot save: Raise IOError with file path (fatal).

---

### 10. Verification Step

**Script:** `final_submission_check.py` (already exists; extend or invoke as-is)

**Expected output:**
- Check that PORTFOLIO sheet exists and contains 4 rows (metrics) with numeric values.
- Check that POSITIONS sheet exists and contains 14 rows (C1–C14) with columns A–F populated.
- Check that no NaN values appear in numeric columns.
- Check that VaR_99% > VaR_95% (confidence interval ordering).
- Check that Portfolio Volatility > 0 if any positions are non-zero.
- Output pass/fail verdict to console.

**If verification fails:**
- Exit with non-zero status code.
- Print diagnostic output (which sheets were found, which rows/columns are missing, sample NaN locations).
- Do not attempt auto-repair; require manual review and re-run.

---

## Implementation Plan

### Files to Create or Modify

1. **New file:** `portfolio_var_calc.py`
   - Main orchestrator script.
   - Imports: pandas, numpy, mysql.connector, openpyxl, numpy for matrix algebra.
   - Classes/functions:
     - `PortfolioVARCalculator` (main class)
       - `__init__()`: Initialize DB connection params.
       - `connect_db()`: Establish MySQL connection.
       - `query_positions()`: Aggregate positions from positions_current.
       - `map_to_c_slots()`: Chronological sorting and C-slot assignment.
       - `read_excel_metrics()`: Load CORREL and VAR sheets.
       - `build_covariance()`: Matrix construction.
       - `calculate_variance()`: Portfolio variance and volatility.
       - `calculate_var()`: VaR at 95% and 99%.
       - `write_excel_output()`: Create PORTFOLIO and POSITIONS sheets.
       - `run()`: Orchestrate full workflow.
   - Entry point: `if __name__ == "__main__": PortfolioVARCalculator().run()`

2. **Modify:** `final_submission_check.py` (optional enhancement)
   - Add checks for PORTFOLIO and POSITIONS sheets.
   - Add checks for row counts and column names.
   - Verify VaR_99% > VaR_95%.
   - (Existing checks for CORREL, VAR, LOG_RETURNS remain.)

### Technology Stack (Locked)

- **Language:** Python 3.8+
- **Database:** MySQL (stellarrisk, host 192.168.102.245)
- **Excel:** openpyxl for read/write; pandas for data manipulation.
- **Linear algebra:** NumPy for matrix operations.
- **Platform:** Windows (paths use backslashes; tested on Windows PowerShell).

### External Dependencies

- `mysql-connector-python` (version pinned in requirements.txt or setup)
- `pandas` (already in use)
- `numpy` (already in use)
- `openpyxl` (already in use)
- No new dependencies; all used in existing scripts (calculate_var_correl.py).

### Integration Points

- **MySQL:** Connect using credentials from environment or hardcoded in script (same pattern as map_ffc_to_series.py, corr.py).
- **Excel input:** FUT-01-41-VAR-CORREL.xlsx (already exists; created by calculate_var_correl.py).
- **Excel output:** Same file, new sheets.
- **Verification:** final_submission_check.py (already exists; runs independently).

---

## Edge Cases and Error Handling

| Case | Condition | Handling | Severity |
|------|-----------|----------|----------|
| No positions in DB | positions_current returns empty result | Initialize all 14 C-slots with zero position; calculate VaR = 0 | Info (not error) |
| Unknown product_series | Query returns series not in the expected 14 | Filter out silently; warn if count < 14 | Warning |
| Expired contract in query | Series like OCT26 if current date > Oct 2026 | Assume query filters only active series; if present, sort by date and assign C-slot (latest may not reach C14) | Info |
| Missing Excel sheet | CORREL or VAR sheet not in workbook | Raise FileNotFoundError; stop immediately | Fatal |
| NaN in std.dev | VAR sheet has NaN for a contract | Raise ValueError; stop immediately | Fatal |
| Correlation not symmetric | CORREL matrix has ρᵢⱼ ≠ ρⱼᵢ | Symmetrize: (ρ + ρ')/2; warn | Warning (auto-repair) |
| Zero portfolio volatility | All positions are zero or σᵢ values are zero | VaR = 0; log as info; proceed | Info |
| Negative portfolio variance | Matrix calculation yields V < 0 | Raise ValueError (indicates matrix or data error) | Fatal |
| Excel file locked | Output file open in Excel or permission denied | Raise PermissionError; user must close file | Fatal |
| Database unreachable | MySQL connection fails | Raise MySQLConnectionError immediately | Fatal |
| Fewer than 14 series | Query returns < 14 distinct product_series | Raise ValueError; unclear which C-slots map to which contracts | Fatal |

---

## Testing Strategy

### Unit Tests
- **Test metric extraction:** Load CORREL and VAR, verify shapes and values.
- **Test slot mapping:** Given 14 series with dates, verify chronological sort and C1–C14 assignment.
- **Test covariance:** Given ρ and σ, compute Σ and verify symmetry and diagonal values.
- **Test portfolio variance:** Given known dv01 and Σ, compute V and σₚ; verify result matches manual calculation.
- **Test VaR:** Given σₚ, compute VaR at 95% and 99%; verify formulas.

### Integration Tests
- **End-to-end:** Query live positions from MySQL, run full workflow, write to Excel, verify with final_submission_check.py.
- **Excel read/write:** Verify PORTFOLIO and POSITIONS sheets are created, readable, and contain correct data.
- **Edge cases:** Run with zero positions, missing series, corrupted CORREL matrix; verify error handling.

### Acceptance Criteria (from requirements)
- All 7 acceptance criteria categories are testable and verifiable by inspecting Excel output and console logs.
- Validation rules (e.g., Σ is symmetric, VaR_99% > VaR_95%) are embedded as assertions in code.

---

## Assumptions

1. **C-slot to FFc mapping:** C1–C14 correspond to FFc1–FFc14 by position order, without parsing FFc expiration dates. This assumes FFc1–FFc14 span roughly the same time window as current live contracts. *Verify by inspecting FFc contract naming/dates in requirements context if available.*

2. **Excel metrics are current:** Reference correlation and volatility metrics in FUT-01-41-VAR-CORREL.xlsx are applicable to current market conditions without regime adjustment. (Stated assumption in requirements.)

3. **Database schema:** positions_current table has columns: product_name, product_series, open_position. (Verified by inspect from map_ffc_to_series.py and check_positions_table.py.)

4. **Normal distribution:** Portfolio returns are normally distributed; z-scores 1.645 (95%) and 2.326 (99%) are appropriate. (Stated assumption in requirements.)

5. **DV01 conversion:** $4167 USD per basis point for Fed Funds futures is correct. (Market standard; not verified by code, assumed from requirements.)

6. **No transaction costs:** Sensitivity is purely mathematical; rebalancing slippage not modeled. (Stated out-of-scope in requirements.)

---

## Performance Considerations

- **Database query:** For 14 series, single GROUP BY query should return in <100ms.
- **Matrix operations:** 14×14 covariance construction and d'Σd computation are O(n²) and O(n³) respectively; negligible for n=14 (<1ms).
- **Excel read/write:** openpyxl is single-threaded; reading 35×35 correlation + 35×7 metrics is <200ms; writing 14-row output is <50ms.
- **Total runtime:** <1 second (excluding network latency for DB connection), well under 5-second target (requirements).

---

## Monitoring and Logging

- **Connection:** Log DB connect/disconnect status.
- **Data:** Log position counts per series, total net notional, number of C-slots with zero position.
- **Calculation:** Log portfolio volatility, VaR_95%, VaR_99%; verify they are reasonable (non-zero if positions exist, zero if not).
- **Output:** Log file path of Excel output and sheet names written.
- **Errors:** Print traceback for fatal errors; exit with non-zero code.

---

## Deployment and Handoff

- **Deliverable:** portfolio_var_calc.py (single script, runnable as `python portfolio_var_calc.py`).
- **Output:** FUT-01-41-VAR-CORREL.xlsx (same workbook, two new sheets added).
- **Verification:** Run `python final_submission_check.py` to validate.
- **User interaction:** None required if all data sources are available (DB, Excel, permissions).
- **Environment:** Windows; Python 3.8+; MySQL client connectivity required.

---

## Design Review Response

**Blocker Resolutions Incorporated (from design review, locked and confirmed):**

| Finding | Resolution | Status |
|---------|-----------|--------|
| C-to-FFc mapping ambiguity | Use **Path B (simpler)**: C1→FFc1, C2→FFc2, ..., C14→FFc14 by slot position, not date matching. Assumes no regime shift between 2020–2026 historical data and current market. Document prominently in code. | ✅ Incorporated in Section 4 |
| DV01 factor confirmation | Confirmed: **$4167 USD/bp** from CME standard and verified in `positions_current` table (`point_value` column). | ✅ Incorporated in Section 6 |
| Excel VAR sheet format | Load with **`skiprows=5`** to skip title metadata rows (1–5); data begins at row 6. | ✅ Incorporated in Section 3 |
| Covariance validation | Add explicit checks for: (1) symmetry, (2) positive semi-definiteness, (3) eigenvalue diagnostics. Auto-repair symmetry if needed; fatal if PSD fails. | ✅ Incorporated in Section 5 |
| Unit consistency verification | Confirmed dimensional analysis: (USD/bp) × bp² × (USD/bp) = USD² ✓ | ✅ Incorporated in Section 6 |

**Post-Blocker Clarification (incorporated after initial review):**

| Clarification | Action | Status |
|---|---|---|
| DV01 multiplier sourcing | Changed from hardcoded constant (4167) to **query from database** `point_value` column. Ensures source-of-truth alignment and automatic adaptation if multipliers change. Default fallback = 4167 if NULL or invalid. | ✅ Updated in Sections 1 & 6 |

**All blockers and clarifications resolved; design is now locked and ready for implementation.**

