# Portfolio-Level VaR Calculation Requirements

## Summary

Build a portfolio-level Value-at-Risk (VaR) calculation system for CME 30-Day Fed Funds futures positions. The system will dynamically map live trading positions to contract slot-pairs (C1–C14, representing the 14 currently-active front contracts across a ~16-month expiration window from NOV26 to FEB28), aggregate positions by contract month, retrieve correlation and volatility metrics from Excel reference data (CORREL and VAR sheets), construct a covariance matrix, calculate portfolio variance and volatility, and compute VaR at 95% and 99% confidence intervals. Results and position details will be written to a new Excel workbook with PORTFOLIO and POSITIONS sheets and verified against completion criteria.

**Key assumption:** The Excel file (FUT-01-41-VAR-CORREL.xlsx) contains pre-computed correlation (CORREL sheet) and standard deviation / volatility metrics (VAR sheet) for historical contracts FFc1–FFc35. These will be read as reference metrics and mapped to the live C-slot contracts based on chronological expiration order.

---

## Functional Requirements

1. **Read correlation and volatility from Excel**
   - Load CORREL sheet: 35×35 correlation matrix (FFc1–FFc35)
   - Load VAR sheet: extract Std.Dev column for all 35 instruments
   - Validate matrix dimensions and data completeness (no NaN values)

2. **Query and aggregate live positions**
   - Connect to MySQL database (stellarrisk, positions_current table)
   - Filter for product_name = 'CME 30DayFedFunds' and product_series in {NOV26, DEC26, JAN27, FEB27, FEB28, JAN28, JUL27, JUN27, MAR27, APR27, MAY27, AUG27, NOV27, OCT27}
   - Group positions by product_series and sum open_position (net notional)
   - Handle case where a contract has no positions (zero net) gracefully

3. **Map positions to C-slot contracts**
   - Determine contract expiration dates by parsing month/year code (e.g., NOV26 → 2026-11)
   - Sort all active series chronologically by expiration date
   - Assign C1 to the front contract (earliest expiration), C2 to the second, etc., up to C14
   - Store mapping (e.g., C1 → NOV26, C2 → DEC26) for reference in output

4. **Build 14×14 covariance matrix**
   - Extract correlation ρᵢⱼ and standard deviations σᵢ, σⱼ for each C-slot pair (i, j) from the Excel reference metrics
   - Apply formula: Σᵢⱼ = ρᵢⱼ × σᵢ × σⱼ
   - Return symmetric covariance matrix (14×14)

5. **Calculate dollar sensitivity (DV01 vector)**
   - For each C-slot position, convert notional basis points to dollar sensitivity: dᵢ = position × 4167 (USD per basis point)
   - Assumption: each Fed Funds contract notional is 4167 USD per basis point (standard market convention)

6. **Calculate portfolio variance and volatility**
   - Compute portfolio variance: V = d'Σd (where d is the DV01 vector, Σ is covariance matrix)
   - Compute portfolio volatility: σₚ = √V (in USD)

7. **Calculate portfolio VaR at confidence levels**
   - VaR at 95% confidence: 1.645 × σₚ
   - VaR at 99% confidence: 2.326 × σₚ
   - Results in USD

8. **Write results to Excel**
   - Create or overwrite PORTFOLIO sheet with:
     - Portfolio metrics: total net notional, portfolio volatility (σₚ), VaR_95%, VaR_99%
     - C-slot mapping table
   - Create POSITIONS sheet with:
     - Columns: C_slot, product_series, expiration_date, net_position, dv01, contribution_to_variance
     - One row per C-slot (C1–C14)
     - Include zero-position slots if no live positions exist
   - File destination: FUT-01-41-VAR-CORREL.xlsx (same file, new sheets or overwrites)

9. **Verify and finalize**
   - Run final_submission_check.py to validate:
     - Excel sheets exist and contain expected columns
     - No NaN values in outputs
     - Dimensions match (14 contracts, 2 confidence levels, portfolio summary)
   - Report success or failure with diagnostic output

---

## Non-Functional Requirements

- **Database availability:** MySQL connection to stellarrisk on 192.168.102.245 must be active
- **Excel compatibility:** Output workbook must be readable in Excel and LibreOffice (XLSX format)
- **Performance:** Calculation must complete in < 5 seconds for current position set (~14 contracts)
- **Data freshness:** Positions retrieved from positions_current table reflect real-time state
- **Reproducibility:** Calculations use deterministic reference metrics (correlation/volatility from fixed Excel file)

---

## Acceptance Criteria

1. **Data pipeline integrity**
   - [ ] Excel CORREL sheet successfully loads as 35×35 correlation matrix with no NaN values
   - [ ] Excel VAR sheet successfully loads with Std.Dev column; all 14 active series have defined metrics
   - [ ] MySQL query returns ≥ 1 and ≤ 14 product series with net positions (sum of open_position per series)

2. **Contract slot mapping**
   - [ ] All 14 active product series (NOV26–FEB28) are identified from database query results
   - [ ] Series are sorted chronologically by expiration date (NOV26 earliest, FEB28 latest)
   - [ ] Mapping C1–C14 reflects this chronological order in output documentation

3. **Covariance matrix construction**
   - [ ] 14×14 covariance matrix is symmetric (Σᵢⱼ = Σⱼᵢ for all i, j)
   - [ ] Diagonal values equal σᵢ² (variance of each contract, extracted from VAR sheet)
   - [ ] All off-diagonal values fall in expected range (product of correlation [−1, 1] and positive σᵢ, σⱼ)

4. **Portfolio variance and volatility**
   - [ ] Portfolio variance V ≥ 0 (mathematically valid)
   - [ ] Portfolio volatility σₚ = √V > 0 (meaningful risk measure)
   - [ ] Volatility value is in USD and differs from individual contract volatilities (portfolio effect)

5. **VaR calculations**
   - [ ] VaR_95% = 1.645 × σₚ and is positive (USD)
   - [ ] VaR_99% = 2.326 × σₚ and is positive (USD)
   - [ ] VaR_99% > VaR_95% (99% confidence implies higher loss threshold)

6. **Excel output structure**
   - [ ] PORTFOLIO sheet contains rows: "Portfolio Volatility ($)", "VaR_95% ($)", "VaR_99% ($)"
   - [ ] POSITIONS sheet has 14 rows (one per C-slot) with columns: C_slot, product_series, expiration_date, net_position, dv01, contribution_to_variance
   - [ ] All numeric values in Excel are formatted and readable (no scientific notation overflow or formatting errors)
   - [ ] Output file is valid XLSX and opens without corruption warnings

7. **Verification**
   - [ ] final_submission_check.py runs without errors
   - [ ] Check confirms presence of PORTFOLIO and POSITIONS sheets
   - [ ] Check confirms no NaN or missing values in output sheets
   - [ ] Check outputs pass/fail summary to console

---

## Out of Scope

- Historical backtesting of VaR model accuracy (e.g., comparing predicted vs. realized losses)
- Stress testing scenarios or hypothetical position adjustments
- Rolling window or time-series VaR updates (single snapshot calculation)
- Risk decomposition by trader, desk, or strategy
- Integration with real-time P&L or margin systems
- Building or validating the correlation and volatility metrics (those are sourced from pre-computed Excel file)
- Handling of options, swaptions, or non-linear instruments (scope is linear ED futures only)
- Multi-currency or cross-asset hedging analysis
- Model validation against regulatory VaR standards (e.g., SEC, CFTC rules)

---

## Assumptions

1. **Contract mapping:** The 14 distinct product series queried from positions_current can be chronologically ordered by expiration date (month/year code parsing) and consistently map to C1–C14.

2. **Reference metrics:** Correlation and standard deviation values in the Excel file (FFc1–FFc35 historical contracts) are directly applicable to the current live contracts (C1–C14) without adjustment for market regime changes.

3. **DV01 conversion:** Each basis point move in Fed Funds futures notional equals $4167 per contract. This is a market standard and reflects 30-day, $1 million notional contract.

4. **Database schema:** The positions_current table contains columns: product_name, product_series, open_position (net position in contracts or notional).

5. **Excel format:** Output is written to the existing FUT-01-41-VAR-CORREL.xlsx file; new sheets (PORTFOLIO, POSITIONS) are added or overwritten if they already exist.

6. **Normal distribution:** VaR calculation assumes portfolio returns are normally distributed, justifying use of 1.645 and 2.326 z-scores for 95% and 99% confidence intervals.

7. **No transaction costs or market impact:** Sensitivity calculation is purely mathematical; real portfolio rebalancing may incur slippage not captured here.

---

## Verification Checklist

Before marking this phase complete, confirm:
- [ ] All 9 functional requirements are clearly understood and testable
- [ ] Acceptance criteria are specific and numbered (7 categories, 30+ checkpoints)
- [ ] Assumptions are documented and reasonable given the conversational context
- [ ] Out of scope is clear (no hidden scope creep)
- [ ] Non-functional requirements align with deployment environment (Windows, MySQL, Excel)
