# GEIE Engine Specification

This document defines the Global Event Impact Evaluation (GEIE) Engine, which maps global macroeconomic events to Nifty 50 stock-level impact using Gemini.

---

## 1. Engine Specifications

* **Model:** Gemini Flash
* **Runs:** Pre-market at 08:05 AM IST only. Never runs in the live scan.
* **Cache:** Stored in Redis; valid for the entire day.
* **Live Scan:** Uses the cached GEIE results only. No live API calls are made during the live 60-second scan.
* **Weight:** 0% in composite scoring. The `magnitude` field (1-3 scale) is for human reference only; the system only consumes the `direction` field.

---

## 2. GEIE Input Prompt Context (v4.6)
The pre-market run constructs a prompt for Gemini to analyze:
1. **FII Trend:** FII trend for the last 5 days.
2. **Block Deals:** Any major block/bulk deals from the previous day.
3. **Options OI Concentration:** Option chain concentration levels.
4. **Key Support Zones:** Major support and resistance levels.

---

## 3. Output JSON Schema (Mandatory)

Gemini must return valid JSON matching this schema:

```json
{
  "event_id": "GEIE-YYYY-MM-DD-001",
  "timestamp": "IST timestamp",
  "market_sentiment": "RISK_ON",
  "stock_impacts": {
    "TATASTEEL": {
      "direction": "POSITIVE",
      "magnitude": 2,
      "reasons": ["China production cuts"],
      "confidence": "HIGH",
      "urgency": "INTRADAY"
    }
  },
  "fii_5day_trend": "BUYING or SELLING or MIXED",
  "institutional_bias": "BULLISH or BEARISH or NEUTRAL",
  "key_support_from_options": "price level",
  "key_resistance_from_options": "price level",
  "top_beneficiaries": ["TATASTEEL", "JSWSTEEL"],
  "top_losers": ["MARUTI", "TATAMOTORS"],
  "geie_status": "ACTIVE"
}
```

---

## 4. Failure Fallback Policy

If the Gemini API times out or returns an error:
1. Log a warning to the `audit_log` with `result = "FALLBACK"`.
2. Mark `geie_status` as `UNAVAILABLE`.
3. Retrieve the **last valid snapshot** of GEIE results from Redis.
4. Snapshots are valid for a maximum of **60 minutes**.
5. If no valid snapshot exists or the 60-minute window has expired: All stocks default to `NEUTRAL` direction.
6. **Critical Rule:** GEIE failure must **NEVER** block any alert.

---

## 5. GEIE Master Map — All 50 Stocks

The master map associates stock symbols with event triggers for evaluation:

### Metals
* **TATASTEEL**
  * positive: `steel_price_up`, `china_production_cuts`, `infra_spending_up`, `govt_stimulus`
  * negative: `china_dumping`, `coal_cost_up`, `domestic_demand_down`
* **JSWSTEEL**
  * positive: `steel_price_up`, `china_production_cuts`, `infra_spending_up`
  * negative: `china_dumping`, `coal_cost_up`, `iron_ore_cost_up`
* **HINDALCO**
  * positive: `aluminum_price_up`, `global_demand_up`, `auto_demand`
  * negative: `aluminum_price_down`, `coal_cost_up`, `china_dumping`

### Banking
* **HDFCBANK**
  * positive: `gdp_growth`, `credit_growth`, `rate_cut`, `fii_inflow`
  * negative: `rate_hike`, `npa_rise`, `regulatory_tightening`
* **ICICIBANK**
  * positive: `gdp_growth`, `credit_growth`, `rate_cut`, `fii_inflow`
  * negative: `rate_hike`, `npa_rise`, `regulatory_tightening`
* **SBIN**
  * positive: `govt_spending`, `rate_cut`, `psu_revival`, `infra_projects`
  * negative: `rate_hike`, `npa_rise`, `privatization_fear`
* **KOTAKBANK**
  * positive: `gdp_growth`, `credit_growth`, `rate_cut`, `fii_inflow`
  * negative: `rate_hike`, `npa_rise`
* **AXISBANK**
  * positive: `gdp_growth`, `credit_growth`, `rate_cut`, `fii_inflow`
  * negative: `rate_hike`, `npa_rise`
* **INDUSINDBK**
  * positive: `gdp_growth`, `credit_growth`, `rate_cut`, `fii_inflow`
  * negative: `rate_hike`, `npa_rise`, `regulatory_tightening`
* **BAJFINANCE**
  * positive: `credit_growth`, `consumer_demand`, `rate_cut`, `fintech_growth`
  * negative: `rate_hike`, `npa_rise`, `regulatory_tightening`
* **BAJAJFINSV**
  * positive: `insurance_growth`, `rate_cut`
  * negative: `rate_hike`, `claims_spike`

### IT
* **INFY**
  * positive: `usd_strong`, `us_it_spend_up`, `digital_transformation`, `ai_adoption`
  * negative: `usd_weak`, `us_recession`, `immigration_restrictions`
* **TCS**
  * positive: `usd_strong`, `us_it_spend_up`, `digital_transformation`
  * negative: `usd_weak`, `us_recession`, `immigration_restrictions`
* **HCLTECH**
  * positive: `usd_strong`, `us_it_spend_up`, `digital_transformation`
  * negative: `usd_weak`, `us_recession`
* **WIPRO**
  * positive: `usd_strong`, `us_it_spend_up`
  * negative: `usd_weak`, `us_recession`, `margin_pressure`
* **TECHM**
  * positive: `usd_strong`, `us_it_spend_up`, `auto_tech`
  * negative: `usd_weak`, `us_recession`

### Energy
* **RELIANCE**
  * positive: `refining_margins_up`, `energy_demand_growth`, `jio_growth`
  * negative: `windfall_tax`, `oil_price_crash`, `regulatory_restrictions`
* **ONGC**
  * positive: `oil_price_up`, `govt_support`
  * negative: `oil_price_crash`, `windfall_tax`, `subsidy_burden`
* **BPCL**
  * positive: `crude_price_down`, `marketing_margin_up`
  * negative: `crude_price_up`, `subsidy_burden`
* **NTPC**
  * positive: `power_demand_up`, `renewable_push`, `govt_spending`
  * negative: `coal_shortage`, `regulatory_delay`
* **POWERGRID**
  * positive: `power_demand_up`, `transmission_expansion`
  * negative: `regulatory_delay`, `land_acquisition_issues`
* **COALINDIA**
  * positive: `power_demand_up`, `coal_price_up`
  * negative: `renewable_push`, `environmental_restrictions`

### Auto
* **MARUTI**
  * positive: `rate_cut`, `rural_demand_up`, `commodity_cost_down`
  * negative: `steel_cost_up`, `fuel_price_up`, `rate_hike`
* **TATAMOTORS**
  * positive: `ev_adoption`, `jlr_recovery`, `commodity_cost_down`
  * negative: `steel_cost_up`, `chip_shortage`, `uk_recession`
* **M&M**
  * positive: `tractor_demand_up`, `rural_growth`, `suv_demand`, `rate_cut`
  * negative: `steel_cost_up`, `fuel_price_up`, `rate_hike`
* **BAJAJ-AUTO**
  * positive: `two_wheeler_demand`, `export_growth`, `rate_cut`
  * negative: `fuel_price_up`, `rate_hike`, `electric_competition`
* **HEROMOTOCO**
  * positive: `two_wheeler_demand`, `rural_growth`, `rate_cut`
  * negative: `fuel_price_up`, `rate_hike`, `electric_competition`
* **EICHERMOT**
  * positive: `premium_bike_demand`, `export_growth`, `rate_cut`
  * negative: `fuel_price_up`, `rate_hike`, `electric_competition`

### Pharma
* **SUNPHARMA**
  * positive: `fda_approval`, `patent_wins`, `generic_boom`, `us_demand_up`
  * negative: `fda_warning`, `patent_loss`, `pricing_pressure`
* **DRREDDY**
  * positive: `fda_approval`, `patent_wins`, `generic_boom`
  * negative: `fda_warning`, `patent_loss`, `pricing_pressure`
* **CIPLA**
  * positive: `fda_approval`, `generic_boom`, `api_demand`
  * negative: `fda_warning`, `pricing_pressure`
* **DIVISLAB**
  * positive: `api_demand`, `china_alternative`, `fda_approval`
  * negative: `china_competition`, `fda_warning`

### FMCG
* **HINDUNILVR**
  * positive: `rural_demand_up`, `monsoon_good`, `premiumization`
  * negative: `inflation_up`, `rural_distress`
* **ITC**
  * positive: `cigarette_volume_up`, `hotel_recovery`, `fmcg_growth`
  * negative: `tax_hike_cigarette`, `esg_pressure`
* **NESTLEIND**
  * positive: `urban_demand_up`, `premiumization`
  * negative: `inflation_up`, `input_cost_up`
* **BRITANNIA**
  * positive: `rural_demand_up`, `monsoon_good`, `inflation_down`
  * negative: `inflation_up`, `input_cost_up`
* **TATACONSUM**
  * positive: `beverage_demand`, `premiumization`
  * negative: `inflation_up`, `input_cost_up`

### Infrastructure
* **LT**
  * positive: `infra_spending`, `govt_capex`, `order_book_up`
  * negative: `interest_rate_up`, `execution_delay`
* **ULTRACEMCO**
  * positive: `infra_spending`, `housing_demand`
  * negative: `fuel_cost_up`, `competition`
* **GRASIM**
  * positive: `cement_demand`, `textile_recovery`
  * negative: `fuel_cost_up`, `cotton_price_up`
* **ADANIENT**
  * positive: `infra_spending`, `cement_demand`, `energy_transition`
  * negative: `regulatory_scrutiny`, `debt_concerns`
* **ADANIPORTS**
  * positive: `trade_growth`, `port_expansion`, `logistics_boom`
  * negative: `trade_war`, `regulatory_scrutiny`

### Others
* **BHARTIARTL**
  * positive: `tariff_hike`, `5g_rollout`, `data_consumption_up`
  * negative: `tariff_war`, `regulatory_fine`
* **ASIANPAINT**
  * positive: `housing_demand`, `monsoon_good`, `premiumization`
  * negative: `input_cost_up`, `competition`
* **TITAN**
  * positive: `gold_price_up`, `wedding_season`, `premiumization`
  * negative: `gold_price_crash`, `competition`
* **APOLLOHOSP**
  * positive: `healthcare_spending`, `insurance_penetration`
  * negative: `regulatory_price_cap`, `input_cost_up`
* **SBILIFE**
  * positive: `insurance_penetration`, `rate_cut`, `vnb_margin_up`
  * negative: `rate_hike`, `claims_spike`
* **HDFCLIFE**
  * positive: `insurance_penetration`, `rate_cut`, `vnb_margin_up`
  * negative: `rate_hike`, `claims_spike`
* **UPL**
  * positive: `monsoon_good`, `global_agri_demand`
  * negative: `monsoon_bad`, `generic_competition`
