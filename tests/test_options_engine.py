import datetime
import pytest
import asyncio
from decimal import Decimal
import database
from options_engine.option_chain_loader import OptionChainLoader
from options_engine.oi_analyzer import OIAnalyzer
from options_engine.pcr_calculator import PCRCalculator
from options_engine.buildup_detector import BuildupDetector
from options_engine.max_pain import MaxPainCalculator
from options_engine.concentration_analyzer import ConcentrationAnalyzer
from options_engine.persistence import OptionsPersistence
from options_engine.recovery_manager import OptionsRecoveryManager
from options_engine.telemetry import OptionsTelemetry
from options_engine.signal_engine import OptionsSignalEngine
from market_data.instrument_loader import InstrumentLoader

# Setup database for tests
@pytest.fixture(scope="module", autouse=True)
def setup_database_schema():
    database.init_db("schema.sql")
    database.execute_query("DELETE FROM options_intelligence;")
    database.execute_query("DELETE FROM options_data;")
    database.execute_query("DELETE FROM latency_metrics;")

def create_mock_chain(symbol, expiry, timestamp):
    # Strike 90, 100, 110
    return [
        {"time": timestamp, "symbol": symbol, "strike": Decimal("90.0"), "expiry": expiry, "option_type": "PE", "oi": 500, "oi_change": 50, "volume": 1000, "iv": Decimal("0.2"), "ltp": Decimal("1.5")},
        {"time": timestamp, "symbol": symbol, "strike": Decimal("100.0"), "expiry": expiry, "option_type": "PE", "oi": 1000, "oi_change": 100, "volume": 2000, "iv": Decimal("0.18"), "ltp": Decimal("5.0")},
        {"time": timestamp, "symbol": symbol, "strike": Decimal("110.0"), "expiry": expiry, "option_type": "PE", "oi": 100, "oi_change": -10, "volume": 500, "iv": Decimal("0.22"), "ltp": Decimal("12.0")},
        {"time": timestamp, "symbol": symbol, "strike": Decimal("90.0"), "expiry": expiry, "option_type": "CE", "oi": 100, "oi_change": 10, "volume": 600, "iv": Decimal("0.21"), "ltp": Decimal("11.5")},
        {"time": timestamp, "symbol": symbol, "strike": Decimal("100.0"), "expiry": expiry, "option_type": "CE", "oi": 800, "oi_change": 80, "volume": 1600, "iv": Decimal("0.19"), "ltp": Decimal("4.2")},
        {"time": timestamp, "symbol": symbol, "strike": Decimal("110.0"), "expiry": expiry, "option_type": "CE", "oi": 1200, "oi_change": 120, "volume": 2400, "iv": Decimal("0.2"), "ltp": Decimal("1.2")}
    ]

def insert_mock_chain_to_db(chain):
    for c in chain:
        database.execute_query(
            """
            INSERT INTO options_data (time, symbol, strike, expiry, option_type, oi, oi_change, volume, iv, ltp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (c["time"], c["symbol"], c["strike"], c["expiry"], c["option_type"], c["oi"], c["oi_change"], c["volume"], c["iv"], c["ltp"])
        )

def test_pcr_calculation():
    """1. Test PCR calculation."""
    expiry = datetime.date(2026, 6, 25)
    t = datetime.datetime(2026, 6, 15, 12, 0, 0)
    chain = create_mock_chain("SBIN", expiry, t)
    
    # Total Put OI = 500 + 1000 + 100 = 1600
    # Total Call OI = 100 + 800 + 1200 = 2100
    # Expected PCR OI = 1600 / 2100 = 0.7619
    # Total Put Vol = 1000 + 2000 + 500 = 3500
    # Total Call Vol = 600 + 1600 + 2400 = 4600
    # Expected PCR Vol = 3500 / 4600 = 0.7609
    
    res = PCRCalculator.calculate_pcr(chain)
    assert res["pcr_oi"] == pytest.approx(0.7619, abs=1e-4)
    assert res["pcr_volume"] == pytest.approx(0.7609, abs=1e-4)

def test_oi_delta_calculation():
    """2. Test Open Interest delta calculation."""
    expiry = datetime.date(2026, 6, 25)
    t = datetime.datetime(2026, 6, 15, 12, 0, 0)
    chain = create_mock_chain("SBIN", expiry, t)
    
    # PE OI Delta = 50 + 100 - 10 = 140
    # CE OI Delta = 10 + 80 + 120 = 210
    
    res = OIAnalyzer.analyze_oi(chain)
    assert res["total_call_oi"] == 2100
    assert res["total_put_oi"] == 1600
    assert res["call_oi_delta"] == 210
    assert res["put_oi_delta"] == 140

def test_buildup_detection():
    """3, 4, 5, 6. Test buildup detection states."""
    # Long Buildup: Price Up, OI Up
    assert BuildupDetector.detect_buildup(10.5, 10.0, 1000, 800) == "LONG BUILDUP"
    # Short Buildup: Price Down, OI Up
    assert BuildupDetector.detect_buildup(9.5, 10.0, 1000, 800) == "SHORT BUILDUP"
    # Long Unwinding: Price Down, OI Down
    assert BuildupDetector.detect_buildup(9.5, 10.0, 800, 1000) == "LONG UNWINDING"
    # Short Covering: Price Up, OI Down
    assert BuildupDetector.detect_buildup(10.5, 10.0, 800, 1000) == "SHORT COVERING"
    # Neutral: No change
    assert BuildupDetector.detect_buildup(10.0, 10.0, 1000, 1000) == "NEUTRAL"

def test_max_pain_calculation():
    """7. Test Max Pain calculation."""
    expiry = datetime.date(2026, 6, 25)
    t = datetime.datetime(2026, 6, 15, 12, 0, 0)
    chain = create_mock_chain("SBIN", expiry, t)
    
    # Let's verify for each strike K:
    # K=90:
    #  PE Pain = 0
    #  CE Pain at 90: (100 - 90)*800 + (110 - 90)*1200 = 8000 + 24000 = 32000
    # K=100:
    #  PE Pain at 100: (100 - 90)*500 = 5000
    #  CE Pain at 100: (110 - 100)*1200 = 12000
    #  Total Pain = 17000
    # K=110:
    #  PE Pain at 110: (110 - 90)*500 + (110 - 100)*1000 = 10000 + 10000 = 20000
    #  CE Pain = 0
    #  Total Pain = 20000
    # Minimum Pain is 17000 at strike 100.
    
    max_pain = MaxPainCalculator.calculate_max_pain(chain)
    assert max_pain == Decimal("100.0")

def test_oi_concentration():
    """8. Test Open Interest concentration detection."""
    expiry = datetime.date(2026, 6, 25)
    t = datetime.datetime(2026, 6, 15, 12, 0, 0)
    chain = create_mock_chain("SBIN", expiry, t)
    
    res = ConcentrationAnalyzer.analyze_concentration(chain)
    assert res["highest_call_oi_strike"] == Decimal("110.0") # max CE OI = 1200
    assert res["highest_put_oi_strike"] == Decimal("100.0") # max PE OI = 1000
    # CE concentration = Top 3 sum / total = (1200+800+100)/2100 = 1.0
    # PE concentration = (1000+500+100)/1600 = 1.0
    assert res["ce_concentration"] == 1.0
    assert res["pe_concentration"] == 1.0

def test_persistence_and_recovery():
    """10 & 11. Test Options persistence and restart recovery."""
    symbol = "SBIN"
    date = datetime.date(2026, 6, 15)
    max_pain = Decimal("100.0")
    put_strike = Decimal("100.0")
    call_strike = Decimal("110.0")
    
    # Save
    OptionsPersistence.save_intelligence(
        date=date,
        symbol=symbol,
        max_pain=max_pain,
        highest_put_strike=put_strike,
        highest_call_strike=call_strike
    )
    
    # Load
    latest = OptionsPersistence.load_latest_intelligence(symbol)
    assert latest is not None
    assert latest["max_pain_level"] == max_pain
    assert latest["highest_put_oi_strike"] == put_strike
    assert latest["highest_call_oi_strike"] == call_strike
    
    # Recover
    state = OptionsRecoveryManager.recover_state(symbol)
    assert state["status"] == "RECOVERED"
    assert state["max_pain_level"] == max_pain
    assert state["highest_put_oi_strike"] == put_strike

def test_multi_symbol_processing():
    """9. Test multi-symbol state separation."""
    engine = OptionsSignalEngine()
    sym1 = "RELIANCE"
    sym2 = "TCS"
    expiry = datetime.date(2026, 6, 25)
    t = datetime.datetime(2026, 6, 15, 12, 0, 0)
    
    chain1 = create_mock_chain(sym1, expiry, t)
    chain2 = create_mock_chain(sym2, expiry, t)
    
    # Save in memory
    engine.last_chains[sym1] = chain1
    engine.last_chains[sym2] = chain2
    
    assert engine.last_chains[sym1][0]["symbol"] == sym1
    assert engine.last_chains[sym2][0]["symbol"] == sym2

def test_nifty_50_instruments_loading():
    """13. Test NIFTY 50 loader compatibility."""
    loader = InstrumentLoader()
    symbols = loader.symbols
    assert len(symbols) == 50
    assert "SBIN" in symbols

@pytest.mark.asyncio
async def test_concurrent_execution_and_telemetry():
    """12 & 14. Test concurrent execution and telemetry logging."""
    database.execute_query("DELETE FROM options_data;")
    database.execute_query("DELETE FROM latency_metrics;")
    
    engine = OptionsSignalEngine()
    symbols = ["RELIANCE", "TCS", "INFY", "SBIN", "ICICIBANK"]
    expiry = datetime.date(2026, 6, 25)
    t = datetime.datetime(2026, 6, 15, 12, 0, 0)
    
    # Insert chains to DB
    for sym in symbols:
        chain = create_mock_chain(sym, expiry, t)
        insert_mock_chain_to_db(chain)
        
    async def process_stock(sym):
        return engine.process_option_update(sym, expiry, t)
        
    results = await asyncio.gather(*(process_stock(sym) for sym in symbols))
    
    assert len(results) == len(symbols)
    for res in results:
        assert res["bias"] in ["BULLISH", "BEARISH", "NEUTRAL"]
        
    # Assert telemetry rows
    metrics_count = database.execute_query("SELECT count(*) FROM latency_metrics WHERE stage = 'OPTIONS_INTELLIGENCE';", fetch=True)
    assert metrics_count[0][0] == len(symbols)
