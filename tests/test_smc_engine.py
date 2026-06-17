import datetime
import pytest
import asyncio
from decimal import Decimal
import database
from market_structure.bos_detector import BOSDetector, find_swing_points
from market_structure.choch_detector import CHOCHDetector
from market_structure.order_block_detector import OrderBlockDetector
from market_structure.fvg_detector import FVGDetector
from market_structure.structure_validator import StructureValidator
from market_structure.structure_scorer import StructureScorer
from market_structure.direction_mapper import DirectionMapper
from market_structure.structure_persistence import StructurePersistence
from market_structure.recovery_manager import RecoveryManager
from market_structure.smc_engine import SMCEngine
from market_data.instrument_loader import InstrumentLoader

# Setup database for tests
@pytest.fixture(scope="module", autouse=True)
def setup_database_schema():
    database.init_db("schema.sql")
    # Clean up SMC tables
    database.execute_query("DELETE FROM smc_structures;")
    database.execute_query("DELETE FROM order_block_memory;")

def create_base_candle(time, price, is_green=True):
    offset = Decimal("0.5") if is_green else Decimal("-0.5")
    return {
        "time": time,
        "open": price - offset,
        "high": price + Decimal("0.8"),
        "low": price - Decimal("0.8"),
        "close": price,
        "volume": 100,
        "vwap": price
    }

def test_bullish_bos_detection():
    """1. Test Bullish BOS detection."""
    engine = SMCEngine()
    symbol = "SBIN"
    tf = "5m"
    engine.warmup_symbol(symbol)
    
    # 1. Clear database tables
    database.execute_query("DELETE FROM smc_structures WHERE symbol = %s;", (symbol,))
    
    # 2. Establish a Swing High using a 5-candle pattern
    # Highs: 10, 11, 15, 12, 10
    base_time = datetime.datetime(2026, 6, 15, 9, 30, 0)
    highs = [10.0, 11.0, 15.0, 12.0, 10.0]
    
    for i, h in enumerate(highs):
        candle = {
            "time": base_time + datetime.timedelta(minutes=5 * i),
            "open": Decimal("9.5"),
            "high": Decimal(str(h)),
            "low": Decimal("9.0"),
            "close": Decimal("10.0")
        }
        engine.process_candle(symbol, tf, candle)
        
    # Verify latest Swing High is confirmed at index 2 (price 15)
    state = engine.states[symbol][tf]
    assert state["latest_swing_high"] == Decimal("15.0")
    
    # 3. Create a candle that closes above the latest Swing High (15.0)
    # Since current_trend defaults to BULLISH, this will trigger a Bullish BOS
    break_candle = {
        "time": base_time + datetime.timedelta(minutes=25),
        "open": Decimal("14.0"),
        "high": Decimal("16.5"),
        "low": Decimal("13.5"),
        "close": Decimal("16.0")
    }
    engine.process_candle(symbol, tf, break_candle)
    
    # Verify DB has recorded the BOS
    structs = StructurePersistence.load_structures(symbol, tf)
    bos_structs = [s for s in structs if s["structure_type"] == "BOS" and s["direction"] == "BULLISH"]
    assert len(bos_structs) == 1
    assert bos_structs[0]["top_price"] == Decimal("15.0")
    assert bos_structs[0]["bottom_price"] == Decimal("15.0")

def test_bearish_bos_detection():
    """2. Test Bearish BOS detection."""
    engine = SMCEngine()
    symbol = "TCS"
    tf = "5m"
    engine.warmup_symbol(symbol)
    
    database.execute_query("DELETE FROM smc_structures WHERE symbol = %s;", (symbol,))
    
    # Set trend to BEARISH first
    engine.states[symbol][tf]["current_trend"] = "BEARISH"
    
    # Establish a Swing Low
    # Lows: 20, 19, 15, 17, 20
    base_time = datetime.datetime(2026, 6, 15, 10, 0, 0)
    lows = [20.0, 19.0, 15.0, 17.0, 20.0]
    
    for i, l in enumerate(lows):
        candle = {
            "time": base_time + datetime.timedelta(minutes=5 * i),
            "open": Decimal("22.0"),
            "high": Decimal("23.0"),
            "low": Decimal(str(l)),
            "close": Decimal("21.0")
        }
        engine.process_candle(symbol, tf, candle)
        
    state = engine.states[symbol][tf]
    assert state["latest_swing_low"] == Decimal("15.0")
    
    # Close candle below swing low (15.0) -> Bearish BOS
    break_candle = {
        "time": base_time + datetime.timedelta(minutes=25),
        "open": Decimal("16.0"),
        "high": Decimal("16.0"),
        "low": Decimal("13.0"),
        "close": Decimal("14.0")
    }
    engine.process_candle(symbol, tf, break_candle)
    
    structs = StructurePersistence.load_structures(symbol, tf)
    bos_structs = [s for s in structs if s["structure_type"] == "BOS" and s["direction"] == "BEARISH"]
    assert len(bos_structs) == 1
    assert bos_structs[0]["bottom_price"] == Decimal("15.0")

def test_bullish_choch_detection():
    """3. Test Bullish CHOCH detection."""
    engine = SMCEngine()
    symbol = "INFY"
    tf = "5m"
    engine.warmup_symbol(symbol)
    
    database.execute_query("DELETE FROM smc_structures WHERE symbol = %s;", (symbol,))
    
    # 1. Set trend to BEARISH
    engine.states[symbol][tf]["current_trend"] = "BEARISH"
    
    # 2. Establish Swing High
    base_time = datetime.datetime(2026, 6, 15, 11, 0, 0)
    highs = [10.0, 11.0, 15.0, 12.0, 10.0]
    for i, h in enumerate(highs):
        candle = {
            "time": base_time + datetime.timedelta(minutes=5 * i),
            "open": Decimal("9.5"),
            "high": Decimal(str(h)),
            "low": Decimal("9.0"),
            "close": Decimal("10.0")
        }
        engine.process_candle(symbol, tf, candle)
        
    # 3. Close candle above Swing High -> Bullish CHOCH + flips trend to BULLISH
    break_candle = {
        "time": base_time + datetime.timedelta(minutes=25),
        "open": Decimal("14.0"),
        "high": Decimal("16.5"),
        "low": Decimal("13.5"),
        "close": Decimal("16.0")
    }
    engine.process_candle(symbol, tf, break_candle)
    
    assert engine.states[symbol][tf]["current_trend"] == "BULLISH"
    structs = StructurePersistence.load_structures(symbol, tf)
    choch_structs = [s for s in structs if s["structure_type"] == "CHOCH" and s["direction"] == "BULLISH"]
    assert len(choch_structs) == 1

def test_bearish_choch_detection():
    """4. Test Bearish CHOCH detection."""
    engine = SMCEngine()
    symbol = "HDFCBANK"
    tf = "5m"
    engine.warmup_symbol(symbol)
    
    database.execute_query("DELETE FROM smc_structures WHERE symbol = %s;", (symbol,))
    
    # 1. Set trend to BULLISH
    engine.states[symbol][tf]["current_trend"] = "BULLISH"
    
    # 2. Establish Swing Low
    base_time = datetime.datetime(2026, 6, 15, 12, 0, 0)
    lows = [20.0, 19.0, 15.0, 17.0, 20.0]
    for i, l in enumerate(lows):
        candle = {
            "time": base_time + datetime.timedelta(minutes=5 * i),
            "open": Decimal("22.0"),
            "high": Decimal("23.0"),
            "low": Decimal(str(l)),
            "close": Decimal("21.0")
        }
        engine.process_candle(symbol, tf, candle)
        
    # 3. Close candle below Swing Low -> Bearish CHOCH + flips trend to BEARISH
    break_candle = {
        "time": base_time + datetime.timedelta(minutes=25),
        "open": Decimal("16.0"),
        "high": Decimal("16.0"),
        "low": Decimal("13.0"),
        "close": Decimal("14.0")
    }
    engine.process_candle(symbol, tf, break_candle)
    
    assert engine.states[symbol][tf]["current_trend"] == "BEARISH"
    structs = StructurePersistence.load_structures(symbol, tf)
    choch_structs = [s for s in structs if s["structure_type"] == "CHOCH" and s["direction"] == "BEARISH"]
    assert len(choch_structs) == 1

def test_bullish_order_block():
    """5. Test Bullish Order Block detection."""
    engine = SMCEngine()
    symbol = "RELIANCE"
    tf = "15m"
    engine.warmup_symbol(symbol)
    
    database.execute_query("DELETE FROM order_block_memory WHERE symbol = %s;", (symbol,))
    
    # Generate 14 flat candles to establish ATR = 1.0
    base_time = datetime.datetime(2026, 6, 15, 9, 30, 0)
    for i in range(14):
        candle = {
            "time": base_time + datetime.timedelta(minutes=15 * i),
            "open": Decimal("100.0"),
            "high": Decimal("100.5"),
            "low": Decimal("99.5"),
            "close": Decimal("100.0")
        }
        engine.process_candle(symbol, tf, candle)
        
    # 15th candle: last opposite bearish candle
    ob_candle = {
        "time": base_time + datetime.timedelta(minutes=15 * 14),
        "open": Decimal("100.0"),
        "high": Decimal("100.5"),
        "low": Decimal("98.0"),
        "close": Decimal("98.5")
    }
    engine.process_candle(symbol, tf, ob_candle)
    
    # 3 strong bullish candles (gain >= 1.5 * ATR(14) where ATR is approx 1.0)
    for i in range(3):
        candle = {
            "time": base_time + datetime.timedelta(minutes=15 * (15 + i)),
            "open": Decimal(str(98.5 + i * 1.5)),
            "high": Decimal(str(98.5 + (i + 1) * 1.5 + 0.2)),
            "low": Decimal(str(98.5 + i * 1.5 - 0.2)),
            "close": Decimal(str(98.5 + (i + 1) * 1.5))
        }
        engine.process_candle(symbol, tf, candle)
        
    # Add 1 more dummy candle to trigger OB check for the preceding impulse
    dummy_candle = {
        "time": base_time + datetime.timedelta(minutes=15 * 18),
        "open": Decimal("103.0"),
        "high": Decimal("103.5"),
        "low": Decimal("102.5"),
        "close": Decimal("103.0")
    }
    engine.process_candle(symbol, tf, dummy_candle)
        
    # Verify order block has been saved in DB
    obs = StructurePersistence.load_order_blocks(symbol, tf)
    assert len(obs) == 1
    assert obs[0]["ob_type"] == "BULLISH"
    assert obs[0]["ob_high"] == Decimal("100.5")
    assert obs[0]["ob_low"] == Decimal("98.0")

def test_bearish_order_block():
    """6. Test Bearish Order Block detection."""
    engine = SMCEngine()
    symbol = "RELIANCE"
    tf = "5m"
    engine.warmup_symbol(symbol)
    
    database.execute_query("DELETE FROM order_block_memory WHERE symbol = %s;", (symbol,))
    
    # Generate 14 flat candles to establish ATR = 1.0
    base_time = datetime.datetime(2026, 6, 15, 9, 30, 0)
    for i in range(14):
        candle = {
            "time": base_time + datetime.timedelta(minutes=5 * i),
            "open": Decimal("100.0"),
            "high": Decimal("100.5"),
            "low": Decimal("99.5"),
            "close": Decimal("100.0")
        }
        engine.process_candle(symbol, tf, candle)
        
    # 15th candle: last opposite bullish candle
    ob_candle = {
        "time": base_time + datetime.timedelta(minutes=5 * 14),
        "open": Decimal("98.5"),
        "high": Decimal("102.0"),
        "low": Decimal("98.0"),
        "close": Decimal("101.5")
    }
    engine.process_candle(symbol, tf, ob_candle)
    
    # 3 strong bearish candles (drop >= 1.5 * ATR(14))
    for i in range(3):
        candle = {
            "time": base_time + datetime.timedelta(minutes=5 * (15 + i)),
            "open": Decimal(str(101.5 - i * 1.5)),
            "high": Decimal(str(101.5 - i * 1.5 + 0.2)),
            "low": Decimal(str(101.5 - (i + 1) * 1.5 - 0.2)),
            "close": Decimal(str(101.5 - (i + 1) * 1.5))
        }
        engine.process_candle(symbol, tf, candle)
        
    # Add 1 more dummy candle to trigger OB check for the preceding impulse
    dummy_candle = {
        "time": base_time + datetime.timedelta(minutes=5 * 18),
        "open": Decimal("97.0"),
        "high": Decimal("97.5"),
        "low": Decimal("96.5"),
        "close": Decimal("97.0")
    }
    engine.process_candle(symbol, tf, dummy_candle)
        
    obs = StructurePersistence.load_order_blocks(symbol, tf)
    assert len(obs) == 1
    assert obs[0]["ob_type"] == "BEARISH"
    assert obs[0]["ob_high"] == Decimal("102.0")
    assert obs[0]["ob_low"] == Decimal("98.0")

def test_bullish_fvg():
    """7. Test Bullish FVG detection."""
    engine = SMCEngine()
    symbol = "ICICIBANK"
    tf = "5m"
    engine.warmup_symbol(symbol)
    
    database.execute_query("DELETE FROM smc_structures WHERE symbol = %s;", (symbol,))
    
    # Candle 1: High = 100
    c1 = {"time": datetime.datetime(2026, 6, 15, 9, 30, 0), "open": 98.0, "high": 100.0, "low": 97.0, "close": 99.0}
    # Candle 2: Bullish candle
    c2 = {"time": datetime.datetime(2026, 6, 15, 9, 35, 0), "open": 99.0, "high": 105.0, "low": 99.0, "close": 104.0}
    # Candle 3: Low = 101.5 (Low > C1 High)
    c3 = {"time": datetime.datetime(2026, 6, 15, 9, 40, 0), "open": 104.0, "high": 106.0, "low": 101.5, "close": 105.0}
    
    engine.process_candle(symbol, tf, c1)
    engine.process_candle(symbol, tf, c2)
    engine.process_candle(symbol, tf, c3)
    
    structs = StructurePersistence.load_structures(symbol, tf)
    fvgs = [s for s in structs if s["structure_type"] == "FVG" and s["direction"] == "BULLISH"]
    assert len(fvgs) == 1
    assert fvgs[0]["top_price"] == Decimal("101.5")
    assert fvgs[0]["bottom_price"] == Decimal("100.0")

def test_bearish_fvg():
    """8. Test Bearish FVG detection."""
    engine = SMCEngine()
    symbol = "ICICIBANK"
    tf = "15m"
    engine.warmup_symbol(symbol)
    
    database.execute_query("DELETE FROM smc_structures WHERE symbol = %s;", (symbol,))
    
    # Candle 1: Low = 100
    c1 = {"time": datetime.datetime(2026, 6, 15, 9, 30, 0), "open": 102.0, "high": 103.0, "low": 100.0, "close": 101.0}
    # Candle 2: Bearish candle
    c2 = {"time": datetime.datetime(2026, 6, 15, 9, 45, 0), "open": 101.0, "high": 101.0, "low": 95.0, "close": 96.0}
    # Candle 3: High = 98.5 (High < C1 Low)
    c3 = {"time": datetime.datetime(2026, 6, 15, 10, 0, 0), "open": 96.0, "high": 98.5, "low": 94.0, "close": 95.0}
    
    engine.process_candle(symbol, tf, c1)
    engine.process_candle(symbol, tf, c2)
    engine.process_candle(symbol, tf, c3)
    
    structs = StructurePersistence.load_structures(symbol, tf)
    fvgs = [s for s in structs if s["structure_type"] == "FVG" and s["direction"] == "BEARISH"]
    assert len(fvgs) == 1
    assert fvgs[0]["top_price"] == Decimal("100.0")
    assert fvgs[0]["bottom_price"] == Decimal("98.5")

def test_timeframes_structure_detection():
    """9 & 10. Verify 5m and 15m structure detection separately."""
    engine = SMCEngine()
    symbol = "SBIN_TF"
    
    # Clean database market data for this symbol to start fresh
    database.execute_query("DELETE FROM market_data WHERE symbol = %s;", (symbol,))
    
    engine.warmup_symbol(symbol)
    
    # 5m candle
    c5 = {"time": datetime.datetime(2026, 6, 15, 13, 0, 0), "open": 10.0, "high": 12.0, "low": 9.0, "close": 11.0}
    engine.process_candle(symbol, "5m", c5)
    
    # 15m candle
    c15 = {"time": datetime.datetime(2026, 6, 15, 13, 0, 0), "open": 10.0, "high": 12.0, "low": 9.0, "close": 11.0}
    engine.process_candle(symbol, "15m", c15)
    
    assert len(engine.states[symbol]["5m"]["candles"]) == 1
    assert len(engine.states[symbol]["15m"]["candles"]) == 1

def test_direction_mapping():
    """13, 14, 15. Test LONG, SHORT, and NO DIRECTION mapping."""
    # LONG: Bullish Break (BOS/CHOCH) + Bullish Zone (OB/FVG)
    s_bull_break = {"structure_type": "BOS", "direction": "BULLISH"}
    s_bull_zone = {"structure_type": "OB", "direction": "BULLISH"}
    
    assert DirectionMapper.map_direction([s_bull_break], [s_bull_zone]) == "LONG"
    
    # SHORT: Bearish Break + Bearish Zone
    s_bear_break = {"structure_type": "CHOCH", "direction": "BEARISH"}
    s_bear_zone = {"structure_type": "FVG", "direction": "BEARISH"}
    
    assert DirectionMapper.map_direction([s_bear_break], [s_bear_zone]) == "SHORT"
    
    # NO DIRECTION: Mixed or insufficient
    assert DirectionMapper.map_direction([s_bull_break], []) == "NO_DIRECTION"
    assert DirectionMapper.map_direction([s_bull_break, s_bear_break], [s_bull_zone]) == "NO_DIRECTION"

def test_cross_timeframe_pass_fail():
    """11 & 12. Test Cross-timeframe PASS and FAIL rules."""
    # Min 2 valid structures, at least 1 from 5m, at least 1 from 15m, same direction
    struct_5m = [{"structure_type": "BOS", "direction": "BULLISH"}]
    struct_15m = [{"structure_type": "OB", "direction": "BULLISH"}]
    
    # PASS
    is_valid, status = StructureValidator.validate_cross_timeframe(struct_5m, struct_15m, "BULLISH")
    assert is_valid is True
    assert status == "PASS"
    
    # FAIL: missing 15m structure
    is_valid, status = StructureValidator.validate_cross_timeframe(struct_5m, [], "BULLISH")
    assert is_valid is False
    assert status == "FAIL"
    
    # FAIL: opposite direction
    struct_15m_bear = [{"structure_type": "OB", "direction": "BEARISH"}]
    is_valid, status = StructureValidator.validate_cross_timeframe(struct_5m, struct_15m_bear, "BULLISH")
    assert is_valid is False
    assert status == "FAIL"

def test_structure_persistence():
    """16. Test persistence of structures into the database."""
    symbol = "PERSIST_TEST"
    tf = "5m"
    test_time = datetime.datetime(2026, 6, 15, 14, 0, 0)
    
    database.execute_query("DELETE FROM smc_structures WHERE symbol = %s;", (symbol,))
    
    StructurePersistence.save_structure(
        time=test_time,
        symbol=symbol,
        timeframe=tf,
        structure_type="BOS",
        direction="BULLISH",
        top_price=Decimal("500.5"),
        bottom_price=Decimal("500.5")
    )
    
    structs = StructurePersistence.load_structures(symbol, tf)
    assert len(structs) == 1
    assert structs[0]["structure_type"] == "BOS"
    assert structs[0]["direction"] == "BULLISH"
    assert structs[0]["top_price"] == Decimal("500.5")

def test_restart_recovery():
    """17. Test restart recovery using RecoveryManager."""
    symbol = "RECOVER_TEST"
    tf = "15m"
    test_time = datetime.datetime(2026, 6, 15, 15, 0, 0)
    
    database.execute_query("DELETE FROM smc_structures WHERE symbol = %s;", (symbol,))
    database.execute_query("DELETE FROM order_block_memory WHERE symbol = %s;", (symbol,))
    
    # Save a FVG
    StructurePersistence.save_structure(
        time=test_time,
        symbol=symbol,
        timeframe=tf,
        structure_type="FVG",
        direction="BULLISH",
        top_price=Decimal("200.0"),
        bottom_price=Decimal("190.0")
    )
    
    # Save a CHOCH to set current trend
    StructurePersistence.save_structure(
        time=test_time - datetime.timedelta(minutes=15),
        symbol=symbol,
        timeframe=tf,
        structure_type="CHOCH",
        direction="BEARISH",
        top_price=Decimal("210.0"),
        bottom_price=Decimal("210.0")
    )
    
    # Recover state using RecoveryManager
    candles = [
        {"time": test_time, "open": 195, "high": 202, "low": 188, "close": 196}
    ]
    
    state = RecoveryManager.recover_state(symbol, tf, candles)
    assert state["current_trend"] == "BEARISH"
    assert len(state["active_fvgs"]) == 1
    assert state["active_fvgs"][0]["top_price"] == Decimal("200.0")

def test_multi_symbol_processing():
    """18. Test multi-symbol isolation in SMCEngine."""
    engine = SMCEngine()
    sym1 = "RELIANCE_MS1"
    sym2 = "TCS_MS2"
    
    # Clean database market data for these symbols to start fresh
    database.execute_query("DELETE FROM market_data WHERE symbol IN (%s, %s);", (sym1, sym2))
    
    engine.warmup_symbol(sym1)
    engine.warmup_symbol(sym2)
    
    c1 = {"time": datetime.datetime(2026, 6, 15, 16, 0, 0), "open": 100, "high": 102, "low": 99, "close": 101}
    engine.process_candle(sym1, "5m", c1)
    
    assert len(engine.states[sym1]["5m"]["candles"]) == 1
    assert len(engine.states[sym2]["5m"]["candles"]) == 0

def test_nifty_50_processing():
    """19. Test loader and warmup for NIFTY 50 constituents."""
    loader = InstrumentLoader()
    symbols = loader.symbols
    assert len(symbols) == 50
    
    engine = SMCEngine()
    # Warm up first 5 symbols
    for s in symbols[:5]:
        engine.warmup_symbol(s)
        assert s in engine.states

@pytest.mark.asyncio
async def test_concurrent_execution():
    """20. Test concurrent processing of ticks for multiple symbols."""
    engine = SMCEngine()
    symbols = ["RELIANCE", "TCS", "INFY", "SBIN", "ICICIBANK"]
    for s in symbols:
        engine.warmup_symbol(s)
        
    async def run_tick(sym):
        tick = {
            "symbol": sym,
            "price": 100.0,
            "volume": 10,
            "time": datetime.datetime(2026, 6, 15, 17, 0, 0)
        }
        setup = engine.process_tick(tick)
        assert setup["symbol"] == sym
        
    await asyncio.gather(*(run_tick(s) for s in symbols))
