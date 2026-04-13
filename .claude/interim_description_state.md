# Interim Description State
*Captured: 2026-04-14*

## What was built

### Context understood
The `Model Points_Profiles` tab already contained **3 480 planned test names** (MP001–MP3480), a systematic cross-product across all 6 dimensions. The `Panel` tab had only 2 example rows. The task was to assign meaningful parameter values to all 3 480 tests.

### Output files in `backend/`

| File | Description |
|------|-------------|
| `backend/generate_panel.py` | Python script — re-runnable, fully documented |
| `backend/unit_tests_panel.csv` | 3 480 rows, 31 columns — **review this first** |
| `backend/IFRS17_UnitTests_v1.xlsm` | Copy of master workbook with Panel fully populated |

### Parameter logic (by dimension)

| Driver | What was stressed |
|--------|------------------|
| `NORM` | Baseline — all stresses near zero |
| `EXP_VAR` | Actuals-vs-expected columns (premiums, claims, NDIC) |
| `ECON` | EoP current yield curve (±50bp STB / ±250bp MODER / ±1000bp EXTR), floored at 0.1% |
| `DEMO` | EoP benefit/NDIC ratios (mortality) or EoP lapse (persistency) |
| `OPER` | EoP expense / commission / acquisition cost assumptions |
| `Population` | EoP lapse assumption and population risk mix |
| `MODIF` | Split between actuals (current period) and EoP projections |
| `COMB` | Partial contributions from multiple simultaneous drivers |

Opening balances, base rates, and OCI/yield-curve treatment are all differentiated by model type (GMM/VFA/PAA), opening state (PROF/ONER/MARG/NEWB), and OCI election.

### Suggested next steps
1. **Review the CSV** — spot-check a sample across each driver type to confirm the parameter choices match your expectations
2. **Open the xlsm copy** and run the macro against a subset (e.g., first 20 rows) to verify the engine processes them correctly
3. If any driver-direction mapping needs adjustment, edit `generate_panel.py` and re-run — it completes in ~90 seconds
