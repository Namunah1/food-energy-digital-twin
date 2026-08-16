# Manual Download Required

## Dataset: FAOSTAT Detailed Trade Matrix
**Priority: CRITICAL**
**Reason blocked:** fenixservices.fao.org returns HTTP 403 from this environment.
The FAO FAOSTAT servers do not allow programmatic access without browser authentication.

---

## What to download

1. Go to: https://www.fao.org/faostat/en/#data/TM

2. Select these filters:
   - **Countries:** All countries (select "All")
   - **Elements:** Export Quantity
   - **Items (list):** 
     - Wheat and products
     - Maize and products  
     - Rice and products
     - Barley and products
     - Soya beans
   - **Years:** 2005, 2006, 2007, 2008, 2009, 2019, 2020, 2021, 2022, 2023

3. Click **Download Data** → choose **CSV**

4. The file will be named something like:
   `Trade_DetailedTradeMatrix_E_All_Data.csv`
   (~200-500 MB depending on selection)

5. **Save it to:**
   `data/raw/fao/Trade_DetailedTradeMatrix_E_All_Data.csv`

---

## What happens after you save it

Run the integration script:

```bash
cd Food_Energy_Systemic_Risk_ABM
python3 src/pipeline/integrate_fao_trade_matrix.py
```

This script will:
1. Filter to the 35 ABM nodes (hub countries + blocs)
2. Aggregate to total grain export flows per bilateral pair
3. Compute corrected C_ij values from real flows
4. Replace the current `C_ij_corrected` (USDA proxy) with FAO actuals
5. Save updated `data/processed/network_weights.csv`

---

## Why this matters

The current `C_ij_corrected` column is a proxy correction using USDA PSD
total export volumes. It correctly identifies the direction of misranking
(Ukraine > Germany for MENA exports) but cannot capture bilateral 
destination-specific flows. The FAO Trade Matrix provides:

- Actual tonnes flowing from reporter to partner, by commodity
- Allows computing what share of Egypt's wheat imports come from Ukraine vs Russia
- Enables proper calibration of the RC cascade transmission network

Expected improvement: retrodiction of the 2022 cascade path should
improve once the MENA import-source structure matches real data.
