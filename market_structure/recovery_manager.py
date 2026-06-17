import datetime
from decimal import Decimal
from market_structure.structure_persistence import StructurePersistence
from market_structure.bos_detector import find_swing_points

class RecoveryManager:
    @staticmethod
    def recover_state(symbol: str, timeframe: str, candles: list[dict]) -> dict:
        """Restores the active SMC memory state for a given symbol and timeframe from database records.
        
        Args:
            symbol: The asset symbol (e.g., 'RELIANCE').
            timeframe: The timeframe ('5m' or '15m').
            candles: Chronological list of recent candles to find the latest swings.
            
        Returns:
            A dictionary containing the reconstructed state.
        """
        # 1. Load active (unbroken) order blocks
        active_obs = StructurePersistence.load_order_blocks(symbol, timeframe)
        
        # 2. Load active (unmitigated) FVGs from smc_structures
        all_structures = StructurePersistence.load_structures(symbol, timeframe)
        active_fvgs = [
            s for s in all_structures
            if s["structure_type"] == "FVG" and not s["mitigated"]
        ]
        
        # 3. Determine current trend direction (check latest CHOCH or fallback)
        chochs = [s for s in all_structures if s["structure_type"] == "CHOCH"]
        if chochs:
            # Sort by time to get the absolute latest CHOCH
            latest_choch = max(chochs, key=lambda x: x["time"])
            current_trend = latest_choch["direction"]
        else:
            current_trend = "BULLISH" # standard default
            
        # 4. Detect the latest confirmed Swing High and Swing Low from the recent candle history
        swing_highs, swing_lows = find_swing_points(candles)
        
        latest_sh = Decimal(str(swing_highs[-1]["price"])) if swing_highs else None
        latest_sl = Decimal(str(swing_lows[-1]["price"])) if swing_lows else None
        
        return {
            "current_trend": current_trend,
            "latest_swing_high": latest_sh,
            "latest_swing_low": latest_sl,
            "active_obs": active_obs,
            "active_fvgs": active_fvgs
        }
