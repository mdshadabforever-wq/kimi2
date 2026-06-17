import datetime
import pytest
from decimal import Decimal
import database
from backtesting.historical_downloader import HistoricalDownloader
from backtesting.metrics_calculator import MetricsCalculator
from backtesting.replay_engine import SignalReplayEngine
from backtesting.backtest_runner import BacktestRunner

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    database.init_db("schema.sql")

def test_historical_downloader():
    """Test generating and saving synthetic market data."""
    HistoricalDownloader.generate_and_save_data(days_lookback=10)
    
    # Check that database has Daily and 1h data
    daily_count = database.execute_query("SELECT count(*) FROM market_data WHERE timeframe = 'Daily';", fetch=True)[0][0]
    hourly_count = database.execute_query("SELECT count(*) FROM market_data WHERE timeframe = '1h';", fetch=True)[0][0]
    
    assert daily_count == 50 * 10
    assert hourly_count == 50 * 10 * 6

def test_metrics_calculator():
    """Test metrics calculation logic."""
    trade_history = [
        {"signal_id": "S1", "pnl": Decimal("5000.0")},
        {"signal_id": "S2", "pnl": Decimal("10000.0")},
        {"signal_id": "S3", "pnl": Decimal("-5000.0")},
        {"signal_id": "S4", "pnl": Decimal("-5000.0")},
        {"signal_id": "S5", "pnl": Decimal("5000.0")},
    ]
    daily_metrics = {
        datetime.date(2026, 6, 1): {"capital": Decimal("1005000.0")},
        datetime.date(2026, 6, 2): {"capital": Decimal("1015000.0")},
        datetime.date(2026, 6, 3): {"capital": Decimal("1010000.0")},
        datetime.date(2026, 6, 4): {"capital": Decimal("1005000.0")},
        datetime.date(2026, 6, 5): {"capital": Decimal("1010000.0")},
    }
    
    res = MetricsCalculator.calculate_performance(trade_history, daily_metrics, initial_capital=1000000.0)
    assert res["total_trades"] == 5
    assert res["total_wins"] == 3
    assert res["total_losses"] == 2
    assert res["win_rate"] == 60.0
    assert res["profit_factor"] == 2.0 # (5000+10000+5000) / (5000+5000) = 20000 / 10000 = 2.0
    assert res["max_drawdown"] == round(((1015000.0 - 1005000.0) / 1015000.0) * 100.0, 2)
    assert res["total_pnl"] == Decimal("10000.0")

def test_end_to_end_backtest():
    """Test full backtest run over 15 trading days."""
    # Let's seed 15 trading days
    HistoricalDownloader.generate_and_save_data(days_lookback=15)
    
    performance = BacktestRunner.run_90_day_backtest(initial_capital=1000000.0, risk_pct=0.5)
    assert performance["total_trades"] > 0
    assert performance["win_rate"] >= 0.0
    assert performance["profit_factor"] >= 0.0
