import database

class GEIEMasterMapLoader:
    @staticmethod
    def seed_master_map():
        """Seeds the geie_master_map database table with initial triggers."""
        # Clean current mapping
        database.execute_query("DELETE FROM geie_master_map;")
        
        triggers = [
            ("TATASTEEL", ["steel_price_up", "china_production_cuts", "infra_spending_up", "govt_stimulus"], ["china_dumping", "coal_cost_up", "domestic_demand_down"], ["neutral_market"]),
            ("JSWSTEEL", ["steel_price_up", "china_production_cuts", "infra_spending_up"], ["china_dumping", "coal_cost_up", "iron_ore_cost_up"], ["neutral_market"]),
            ("HINDALCO", ["aluminum_price_up", "global_demand_up", "auto_demand"], ["aluminum_price_down", "coal_cost_up", "china_dumping"], []),
            ("HDFCBANK", ["gdp_growth", "credit_growth", "rate_cut", "fii_inflow"], ["rate_hike", "npa_rise", "regulatory_tightening"], []),
            ("ICICIBANK", ["gdp_growth", "credit_growth", "rate_cut", "fii_inflow"], ["rate_hike", "npa_rise", "regulatory_tightening"], []),
            ("SBIN", ["govt_spending", "rate_cut", "psu_revival", "infra_projects"], ["rate_hike", "npa_rise", "privatization_fear"], []),
            ("KOTAKBANK", ["gdp_growth", "credit_growth", "rate_cut", "fii_inflow"], ["rate_hike", "npa_rise"], []),
            ("AXISBANK", ["gdp_growth", "credit_growth", "rate_cut", "fii_inflow"], ["rate_hike", "npa_rise"], []),
            ("INDUSINDBK", ["gdp_growth", "credit_growth", "rate_cut", "fii_inflow"], ["rate_hike", "npa_rise"], [])
        ]
        
        query = """
            INSERT INTO geie_master_map (symbol, positive_triggers, negative_triggers, neutral_triggers)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (symbol) DO NOTHING;
        """
        for sym, pos, neg, neu in triggers:
            database.execute_query(query, (sym, pos, neg, neu))
            
    @staticmethod
    def load_triggers() -> dict:
        """Loads all stock triggers from the master map table."""
        query = "SELECT symbol, positive_triggers, negative_triggers, neutral_triggers FROM geie_master_map;"
        try:
            res = database.execute_query(query, fetch=True)
            mapping = {}
            if res:
                for row in res:
                    mapping[row[0]] = {
                        "positive": row[1] if row[1] else [],
                        "negative": row[2] if row[2] else [],
                        "neutral": row[3] if row[3] else []
                    }
            return mapping
        except Exception as e:
            print(f"[MASTER MAP LOADER] Error loading master map: {e}")
        return {}
