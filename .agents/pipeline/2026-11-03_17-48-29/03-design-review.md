# Design Review: Portfolio-Level VaR Calculation

**Status:** CHANGES_REQUESTED  
**Review Date:** 2026-11-03  
**Reviewer:** Design Review Subagent  

---

## Summary

The design for portfolio-level VaR calculation is **structurally sound** but contains **critical ambiguities and unverified assumptions** that must be resolved before implementation. The core approach (matrix-based d'Σd portfolio variance) is correct, the database schema is verified, and the Excel infrastructure exists. However, the design makes a fundamental assumption about C-to-FFc mapping that contradicts the conversational context and requires explicit clarification and validation before coding proceeds.

**Key blocker:** The design assumes C1–C14 maps to FFc1–FFc14 "by position order" without date matching, but the user's conversation history (messages 4–7) clearly distinguishes generic contracts (C1–C14, rolling) from monthly contracts (historical FFc1–FFc35, fixed). This mapping choice was deferred in the conversation as uncertain ("what i am a bit lost", "but it has data from 2020-2026"). A wrong mapping invalidates all portfolio VAR outputs.

---

## Findings

### HIGH SEVERITY

**1. C-to-FFc Contract Mapping is Unresolved**

**Location:** Section 4 (Map C-slots to FFc Contracts), Assumptions Section (Assumption 1), Data Flow diagram

**Problem:**  
The design states:
> "Assume FFc1–FFc14 correspond to C1–C14 by position order, and that FFc1 is the oldest front contract in the historical data, while FFc14 is 13 months forward, etc."

And then admits:
> "This would be more robust but requires additional metadata not present in the Excel file... Given that the existing scripts use FFc1–FFc35 as a fixed historical baseline and the requirements explicitly state 'directly applicable,' the simpler mapping minimizes assumptions."

This reasoning is flawed. FFc1–FFc35 are **fixed, named historical contracts** from a back-test (2020–2026 data). C1–C14 are **dynamic, rolling live contracts** that change as expirations pass. The user's conversation (message 4) is explicit:
> "c1 would be the first month contract c like now c1=nov 26 and c2=dec 26 and so on and when nov 26 expires we will have c1=dec26 and c2=jan27"

The design conflates these two contract systems. Mapping C1 directly to FFc1 assumes FFc1 happens to be the front contract when the code runs — a **coincidence, not a design**. If the data in Excel is from Jan 2020, FFc1 may have expired in Jan 2020; it has no relationship to NOV26 (current C1).

**Concrete fix:**  
Choose one of two paths before implementation:

- **Path A (Recommended):** Map C-slots to FFc contracts by **expiration date matching**. Parse FFc contract expiration from Excel metadata (if available) or infer it from the historical data period (e.g., if data spans Jan 2020–Oct 2026 and FFc1–FFc35 are monthly, map FFc1→Jan2020, FFc2→Feb2020, ..., then find which FFc(i) has expiration closest to each C1–C14 expiration). If metadata is missing, document this as a known limitation and proceed with Path B.

- **Path B (Simpler but Less Robust):** Use the **first 14 instruments** in the CORREL/VAR sheets (FFc1–FFc14) as reference metrics, **explicitly noting** that this assumes no regime shift between the historical period and today. Document this assumption prominently in code comments and output. Verify in testing that results are plausible.

**Action:** User must choose Path A or Path B. If Path A, design must specify metadata source for FFc expiration dates. If Path B, design must confirm user accepts the regime-shift risk and note it in output documentation.

---

**2. Excel VAR Sheet Structure Does Not Match Design Description**

**Location:** Section 3 (Read Excel Reference Metrics), Code snippet in Section 3, Verified Assumptions

**Problem:**  
The design states:
> "Load VAR sheet: Std.Dev column (or 'Std.Dev' header) for all 35 instruments."

And describes the output as:
> "std_devs = correl_matrix.index.to_series().map(lambda x: var_df.loc[x, 'Std.Dev'])"

**Verified fact:**  
The VAR sheet has **header metadata in rows 1–5** (title, calculation date, data period, row count). The actual data begins at **row 6** with column headers ("Instrument", "Mean", "Std.Dev", ...). The Std.Dev column exists and contains numeric values, but the sheet layout requires `skiprows=5` to access it correctly.

The design does **not document this offset** or mention the header rows. A direct `pd.read_excel(..., sheet_name='VAR')` without skiprows will load the title rows and misalign column indices.

**Concrete fix:**  
Update Section 3 to specify:
```python
# Load VAR sheet (skip title and metadata rows)
var_df = pd.read_excel('FUT-01-41-VAR-CORREL.xlsx', sheet_name='VAR', skiprows=5, index_col=0)
# Extract Std.Dev column for instruments FFc1–FFc35
std_devs = var_df['Std.Dev']
```

Document that rows 1–5 contain metadata and should be skipped.

---

**3. Correlation Matrix Symmetry Check Missing; Auto-Repair Defined but Not Enforced**

**Location:** Section 5 (Build 14×14 Covariance Matrix), Error Handling subsection

**Problem:**  
The design states:
> "If covariance matrix is not symmetric (numerical precision): Symmetrize: `Σ = (Σ + Σ')/2`."

This is listed as an error-handling fallback but **not enforced in normal operation**. If the correlation matrix loaded from Excel is not symmetric (due to data entry errors or corruption), the covariance matrix will inherit this asymmetry. The design should **validate symmetry before constructing covariance**, not after.

**Concrete fix:**  
Add a validation step after loading CORREL:
```python
# Validate CORREL symmetry
if not np.allclose(c_correl.values, c_correl.T.values, atol=1e-6):
    print("WARNING: Correlation matrix not symmetric. Symmetrizing...")
    c_correl = (c_correl + c_correl.T) / 2
assert np.allclose(c_correl.values, c_correl.T.values, atol=1e-6), "Correlation matrix cannot be symmetrized"
```

---

**4. Portfolio Variance Can Be Negative Due to Numerical Underflow or Singular Covariance; Recovery Plan Missing**

**Location:** Section 7 (Calculate Portfolio Variance and Volatility), Error Handling

**Problem:**  
The design states:
> "If portfolio_variance < 0 (numerical underflow or matrix error): Raise ValueError (indicates corrupted data or algorithmic error)."

However, **no recovery mechanism or diagnostic output** is provided. If this error occurs in production (e.g., due to a singular covariance matrix or numerical precision loss), the user is left with a cryptic fatal error and no guidance on what went wrong or how to fix it.

Additionally, the design assumes the covariance matrix is **positive semi-definite** but does **not check this** before matrix operations.

**Concrete fix:**  
Add eigenvalue diagnostics before portfolio variance calculation:
```python
# Verify covariance matrix is positive semi-definite
eigenvalues = np.linalg.eigvalsh(cov_matrix)
min_eigenvalue = eigenvalues.min()
if min_eigenvalue < -1e-6:  # Allow small numerical negative due to precision
    print(f"ERROR: Covariance matrix not positive semi-definite. Min eigenvalue: {min_eigenvalue}")
    print(f"Condition number: {eigenvalues.max() / (eigenvalues.min() + 1e-10):.2e}")
    raise ValueError("Covariance matrix is not valid (not positive semi-definite)")

# Calculate portfolio variance
portfolio_variance = dv01_vector @ cov_matrix @ dv01_vector
if portfolio_variance < 0:
    print(f"ERROR: Portfolio variance is negative: {portfolio_variance}")
    print(f"This indicates a numerical or data error. Check covariance matrix eigenvalues.")
    raise ValueError("Portfolio variance calculation failed")
```

---

### MEDIUM SEVERITY

**5. DV01 Conversion Factor Not Verified; Market Standard Assumption Unvalidated**

**Location:** Section 6 (Calculate DV01 Vector), Formula comment

**Problem:**  
The design states:
> "Each Fed Funds futures contract has a $1M notional (30-day accrual). One basis point = $1M × 0.0001 / 30 = $3.33, but market convention rounds to $4167 per basis point (or equivalently, $4,166.67 exact)."

This is justified as "market standard" but is **not verified** against the actual contract specifications or the existing codebase. The calculation $1M × 0.0001 / 30 ≈ $3.33 does not match the stated $4167. The jump from $3.33 to $4167 is unexplained; it suggests a different notional or day-count convention.

**Verified fact:**  
The existing scripts (map_ffc_to_series.py, calculate_var_correl.py, etc.) do **not use or reference** DV01 conversion. They work with contract counts and log returns. No existing code validates the $4167 factor.

**Concrete fix:**  
**Before implementation**, confirm the DV01 factor with one of:
1. CME official Fed Funds futures contract specification (published on CME website).
2. Internal trading systems documentation.
3. Compare against P&L calculations: if position × 4167 × daily price move should ≈ daily P&L, verify this empirically with a sample trade.

Add a comment documenting the source and date of the factor:
```python
# DV01 conversion: $4167 USD per basis point
# Source: [CME FED FUNDS FUTURES SPEC v1.2, effective 2026-01-01]
# Calculation: $1M notional × [basis point conversion factor for 30-day accrual]
# Verified: [date and method]
dv01_vector = net_position * 4167
```

If validation is not feasible before implementation, add this as a **MUST-VERIFY** item in testing and document it as a risk in the code.

---

**6. "Directly Applicable" Assumption for Excel Metrics is Stated But Never Validated**

**Location:** Requirements Section (Assumption 2), Design Section 4 (Challenge paragraph)

**Problem:**  
Assumption 2 states:
> "Correlation and standard deviation values in the Excel file (FFc1–FFc35 historical contracts) are directly applicable to the current live contracts (C1–C14) without adjustment for market regime changes."

The design acknowledges this assumption (Section 4) but provides **no test or validation** to check it. If market volatility in Nov 2026 is 5× higher than in the Jan 2020–Oct 2026 historical period, using historical std.dev values will underestimate VaR by a factor of 5.

**Concrete fix:**  
Add a validation step post-calculation:
```python
# VALIDATION: Compare calculated volatility to recent realized volatility
# If the ratio is > 2 or < 0.5, warn the user that the historical metrics may not be applicable
recent_volatility = calculate_recent_volatility_from_prices(last_30_days)  # Placeholder
historical_volatility = portfolio_volatility
ratio = recent_volatility / (historical_volatility + 1e-10)
if ratio > 2 or ratio < 0.5:
    print(f"WARNING: Recent volatility ({recent_volatility:.2f}) differs significantly from")
    print(f"historical metrics ({historical_volatility:.2f}). Ratio: {ratio:.2f}")
    print("Consider updating reference metrics if market regime has changed.")
```

If `calculate_recent_volatility_from_prices` is not available, add a **code comment noting this risk** and recommend manual review of recent market conditions before trusting the output.

---

**7. Zero Portfolio Volatility Edge Case Leads to Zero VaR; Interpretation Unclear**

**Location:** Section 8 (Calculate VaR), Section 10 (Edge Cases table)

**Problem:**  
The design states that if all positions are zero, σₚ = 0 and VaR = 0, which is mathematically correct. However, the edge case table lists this as "Info (not error)". In a portfolio risk context, VaR = 0 is typically a **warning condition**, not a routine result. If the portfolio has no positions, why is the workflow running? The design should clarify intent.

**Concrete fix:**  
Add a pre-flight check:
```python
total_positions = abs(c_slot_mapping.values()).sum()  # Sum of absolute position notionals
if total_positions == 0:
    print("WARNING: Portfolio has zero net positions. VaR = $0.")
    print("This is valid but unusual. Verify that positions_current table is not empty.")
    # Optionally proceed or exit; make this a user decision
```

Document whether proceeding with zero positions is acceptable or if it should trigger an error. If acceptable, justify why.

---

**8. Fewer Than 14 Series Treated as Fatal; But Requirements List 14 Fixed Series**

**Location:** Section 2 (Contract Slot Mapping), Edge Cases (row: Fewer than 14 series)

**Problem:**  
The design raises `ValueError` if fewer than 14 series are found. The requirements state 14 fixed series {NOV26, DEC26, JAN27, FEB27, FEB28, JAN28, JUL27, JUN27, MAR27, APR27, MAY27, AUG27, NOV27, OCT27}. However, the database query (Section 1) allows any series returned by the query. If the user's positions only include 10 of the 14 series, the design **rejects the calculation entirely**.

This is overly strict. A portfolio can have positions in fewer than 14 contracts; the missing contracts simply have zero position and contribute zero to portfolio variance.

**Concrete fix:**  
Change the logic to allow fewer than 14 series:
```python
# Query positions
positions = query_positions()  # Returns dict of {series: net_position}

# Map all 14 expected series to C-slots; use 0 if not in query
all_series = ['NOV26', 'DEC26', 'JAN27', ..., 'FEB28']
for c_slot, series in enumerate(sorted_series, 1):
    c_slot_mapping[f'C{c_slot}'] = (series, positions.get(series, 0))

# If fewer than 14 series found, warn but proceed
if len(positions) < 14:
    missing = set(all_series) - set(positions.keys())
    print(f"WARNING: {len(missing)} series have no positions: {missing}")
    print("These will be assigned zero position (C-slot contribution = $0).")
```

**However**, if the interpretation is that the **exact** set of 14 series must exist for the calculation to be meaningful (e.g., because CORREL/VAR are computed for FFc1–FFc14 assuming a specific maturity structure), then document this explicitly and provide a clear error message.

---

**9. DV01 Vector Calculation Mixes Contracts and Basis Points; Units Unclear**

**Location:** Section 6 (Calculate DV01 Vector), Section 5 (Build Covariance), Formula definitions

**Problem:**  
Section 6 defines DV01 as:
```
dᵢ = positionᵢ × 4167 USD/bp
```

And describes position as "net notional" from the database. However, the design never clarifies **units**: Is the position in contracts? In dollars notional? The database column `open_position` is of type `bigint` (verified), which suggests integer counts (contracts), not notional dollars.

The formula assumes position is in **contracts** and multiplies by 4167 (USD/bp) to get **DV01 in USD/bp**. But then the covariance matrix Σ has units of **bp²** (since it's built from log returns, which are in basis points per day per the design). So d'Σd has units of **(USD/bp) × bp² = USD·bp**, which is **dimensionally incorrect** for a variance in USD².

**Concrete fix:**  
Clarify the units throughout:
1. Confirm `open_position` from database is in **contract count**, not notional.
2. Define DV01 as "price sensitivity per contract" in USD per basis point:
   ```python
   dv01_per_contract = 4167  # USD per basis point (CME Fed Funds spec)
   position_contracts = c_slot_mapping[c_slot][1]  # Contract count
   dv01_usd_per_bp = position_contracts * dv01_per_contract
   ```
3. Verify covariance matrix units: If Σᵢⱼ is constructed from log returns in basis points, then Σᵢⱼ has units of **basis points²**. To get portfolio variance in **USD²**, scale d by the DV01 factor and Σ by the square of that factor:
   ```python
   # Covariance matrix Σ has units: basis_points²
   # DV01 vector d has units: USD / basis_point
   # Portfolio variance V = d'Σd has units: (USD/bp)² × bp² = USD²  ✓ Correct
   portfolio_variance = dv01_vector @ cov_matrix @ dv01_vector  # Units: USD²
   portfolio_volatility = np.sqrt(portfolio_variance)  # Units: USD
   ```

If this is wrong, provide the correct formula. **Dimensional analysis must be correct before implementation.**

---

### NIT SEVERITY

**10. Output File Path Hardcoded; No Fallback or User Specification**

**Location:** Section 9 (Write Results to Excel), File Storage subsection

**Problem:**  
The design hardcodes the output path as:
> `c:\Users\Axxela\Desktop\VAR\FUT-01-41-VAR-CORREL.xlsx`

This is inflexible; if the user runs the script from a different directory or wants to output to a different location, they must edit the code.

**Concrete fix (Optional):**  
Add a command-line argument or environment variable:
```python
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--output', default=r'c:\Users\Axxela\Desktop\VAR\FUT-01-41-VAR-CORREL.xlsx')
args = parser.parse_args()
output_file = args.output
```

Or read from environment: `output_file = os.getenv('VAR_OUTPUT_FILE', <default>)`.

---

**11. Logging is Mentioned but Not Specified**

**Location:** Section (Monitoring and Logging)

**Problem:**  
The design mentions "Log DB connect/disconnect status," "Log position counts," etc., but does not specify:
- Log level (DEBUG, INFO, WARNING, ERROR)?
- Output destination (console, file, both)?
- Log format (timestamp? function name?)?

**Concrete fix (Optional):**  
Add logging configuration:
```python
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('portfolio_var.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
```

---

**12. Excel Output Sheet Names "PORTFOLIO" and "POSITIONS" Not Qualified; Collision Risk**

**Location:** Section 9 (Write Results to Excel)

**Problem:**  
If the workbook already has a sheet named "PORTFOLIO" or "POSITIONS" (from a prior run or user-created sheet), the design says "Overwrite silently (log as warning)." This is risky if the user accidentally had important data in those sheets.

**Concrete fix (Optional):**  
Instead of silently overwriting, rename with a timestamp:
```python
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
portfolio_sheet_name = f'PORTFOLIO_{timestamp}'
positions_sheet_name = f'POSITIONS_{timestamp}'
# Or ask for user confirmation before overwriting
```

---

## Verified Assumptions

1. ✓ **Database connectivity:** MySQL stellarrisk database is accessible at 192.168.102.245 with risk_reader credentials.
2. ✓ **Database schema:** `positions_current` table exists with columns `product_name`, `product_series`, `open_position` (and many others).
3. ✓ **Database query works:** Query for `product_name = 'CME 30DayFedFunds'` returns results (verified: returns ≥ 1 series).
4. ✓ **Excel file exists:** `FUT-01-41-VAR-CORREL.xlsx` exists in the specified path with CORREL, VAR, and LOG_RETURNS sheets.
5. ✓ **CORREL sheet structure:** 35×35 correlation matrix indexed by FFc1–FFc35 (verified: loaded successfully).
6. ✓ **VAR sheet structure:** Contains Std.Dev column for all 35 instruments (verified: present with numeric values).
7. ✓ **Dependencies available:** pandas, numpy, mysql-connector-python, openpyxl are all used in existing scripts.
8. ✓ **Python version:** Python 3.8+ confirmed working in environment.
9. ✓ **Normal distribution assumption:** Design uses z-scores 1.645 and 2.326 (standard for normal VaR; assumption stated in requirements).

---

## Unverified / Wrong Assumptions

1. ✗ **C-to-FFc mapping:** CRITICAL. Design assumes C1–C14 maps to FFc1–FFc14 "by position order," but this is contradicted by the user's conversation history (messages 4–7), which clarifies that C-slots are **rolling live contracts** while FFc1–FFc35 are **fixed historical contracts**. This mapping must be resolved before implementation (see Finding #1).

2. ✗ **DV01 factor ($4167 USD/bp):** Not verified against CME spec or existing codebase. Claimed "market standard" but the calculation is not shown; $1M notional / 30 days should yield ~$3.33/bp, not $4167. Requires verification (see Finding #5).

3. ✗ **Regime shift risk:** Assumption 2 (reference metrics are directly applicable) is acknowledged but never tested. If market volatility has changed significantly since the historical period, VaR estimates will be wrong (see Finding #6).

4. ? **Zero portfolio volatility is acceptable:** Design treats this as "Info" but does not clarify whether it's expected or a warning sign (see Finding #7).

5. ? **Fewer than 14 series should be fatal:** Design rejects portfolios with < 14 series, but a portfolio can legitimately have positions in only a subset of contracts (see Finding #8).

---

## Blockers for Implementation

The following must be resolved before the code can be written:

1. **[CRITICAL] Resolve C-to-FFc mapping (Finding #1):** Choose Path A (expiration date matching) or Path B (use FFc1–FFc14 directly, accept regime shift risk). Update design with chosen path and provide implementation detail.

2. **[HIGH] Verify DV01 factor (Finding #5):** Confirm $4167 USD/bp with CME documentation or internal spec. If different, provide correct factor.

3. **[HIGH] Fix Excel VAR sheet loading (Finding #2):** Update design to include `skiprows=5` and document the header row structure.

4. **[HIGH] Add covariance matrix validation (Finding #3):** Check correlation matrix symmetry before constructing covariance; add diagnostics if not symmetric.

5. **[HIGH] Add portfolio variance sign check (Finding #4):** Check covariance matrix positive semi-definiteness before portfolio variance calculation; provide diagnostic output if negative variance occurs.

6. **[MEDIUM] Verify "directly applicable" assumption (Finding #6):** Add a test or warning to detect if recent volatility differs significantly from historical.

7. **[MEDIUM] Clarify unit consistency (Finding #9):** Verify dimensional analysis is correct for portfolio variance calculation (USD²).

---

## Design Quality Assessment

| Aspect | Assessment | Notes |
|--------|------------|-------|
| Architecture | ✓ Sound | Matrix-based approach is mathematically correct. |
| Completeness | ✗ Incomplete | Missing C-to-FFc mapping strategy; ambiguous data transformations. |
| Clarity | ✗ Unclear | Mixing of FFc (fixed) and C-slot (rolling) concepts; dimensional units unclear. |
| Feasibility | ✓ Feasible | Database, Excel, and dependencies all verified; performance target is achievable. |
| Risk Mitigation | ✗ Weak | Multiple unverified assumptions (DV01, regime shift, mapping) not addressed. |
| Error Handling | ~ Partial | Some edge cases covered; others (e.g., singular covariance, recent volatility shift) underspecified. |
| Testing Strategy | ✓ Mentioned | Plan exists; no specific test cases defined. |

---

## Recommendation

**Verdict: CHANGES_REQUESTED**

Do not proceed to implementation. The design requires:

1. **User decision on C-to-FFc mapping** (Path A or Path B) — this is **not** a detail for the coder to decide.
2. **Verification of DV01 factor** — critical for correct portfolio variance scaling.
3. **Clarification of Excel sheet loading** — VAR sheet header offset must be specified.
4. **Resolution of dimensional units** — ensure portfolio variance formula is correct.

Once these four items are addressed and documented in the design, implementation can proceed. The remaining findings (validation, diagnostics, optional improvements) can be incorporated during implementation but do not block the start.

---

## Next Steps

1. **User reviews findings #1, #5, #8, #9** (the blockers).
2. **User decides: Path A or Path B for C-to-FFc mapping** and provides rationale.
3. **User verifies DV01 factor** with CME spec or confirms it's acceptable as-is.
4. **Designer updates the design document** with user's decisions and resubmits.
5. **Design Review confirms** blockers are resolved and approves.
6. **Implementation can begin**.

---
