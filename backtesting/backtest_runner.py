import datetime
import database
from backtesting.historical_downloader import HistoricalDownloader
from backtesting.replay_engine import SignalReplayEngine
from backtesting.metrics_calculator import MetricsCalculator

class BacktestRunner:
    @staticmethod
    def run_90_day_backtest(initial_capital: float = 1000000.0, risk_pct: float = 0.5) -> dict:
        """Runs the full 90-day backtesting simulation and returns calculated metrics."""
        # 1. Setup the historical database data
        HistoricalDownloader.generate_and_save_data(days_lookback=90)
        
        # 2. Get the min and max dates of the generated Daily candles
        query = "SELECT min(time)::date, max(time)::date FROM market_data WHERE timeframe = 'Daily';"
        res = database.execute_query(query, fetch=True)
        if not res or not res[0][0]:
            print("[BACKTEST RUNNER] Error: Market data was not populated successfully.")
            return {}
            
        start_date, end_date = res[0][0], res[0][1]
        print(f"[BACKTEST RUNNER] Date Range: {start_date} to {end_date}")
        
        # 3. Instantiate and run replay engine
        engine = SignalReplayEngine(start_date=start_date, end_date=end_date)
        trades = engine.run_replay(capital=initial_capital, risk_pct=risk_pct)
        
        # 4. Calculate performance metrics
        performance = MetricsCalculator.calculate_performance(
            trade_history=trades,
            daily_metrics=engine.daily_metrics,
            initial_capital=initial_capital
        )
        
        print("\n=== Backtest Run Completed ===")
        print(f"Total Trades  : {performance['total_trades']}")
        print(f"Wins / Losses : {performance['total_wins']} / {performance['total_losses']}")
        print(f"Win Rate      : {performance['win_rate']}% (Required > 45%)")
        print(f"Profit Factor : {performance['profit_factor']} (Required > 1.5)")
        print(f"Max Drawdown  : {performance['max_drawdown']}% (Required < 15%)")
        print(f"Total Net PnL : INR {performance['total_pnl']}")
        print(f"Final Capital : INR {performance['final_capital']}")
        
        return performance

if __name__ == "__main__":
    database.init_db()
    BacktestRunner.run_90_day_backtest()
