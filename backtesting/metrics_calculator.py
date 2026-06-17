from decimal import Decimal

class MetricsCalculator:
    @staticmethod
    def calculate_performance(trade_history: list, daily_metrics: dict, initial_capital: float = 1000000.0) -> dict:
        """Calculates key performance metrics for the backtest."""
        total_trades = len(trade_history)
        if total_trades == 0:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "max_drawdown": 0.0,
                "total_pnl": Decimal("0.0"),
                "final_capital": Decimal(str(initial_capital))
            }
            
        wins = [t for t in trade_history if t["pnl"] > 0]
        losses = [t for t in trade_history if t["pnl"] < 0]
        
        total_wins = len(wins)
        win_rate = (total_wins / total_trades) * 100.0
        
        gross_profit = sum(t["pnl"] for t in wins)
        gross_loss = abs(sum(t["pnl"] for t in losses))
        
        profit_factor = float(gross_profit / gross_loss) if gross_loss > 0 else float('inf')
        
        # Calculate daily drawdown curve
        capital_curve = []
        # Sort by date
        sorted_dates = sorted(daily_metrics.keys())
        for d in sorted_dates:
            capital_curve.append(float(daily_metrics[d]["capital"]))
            
        max_drawdown = 0.0
        peak = initial_capital
        for cap in capital_curve:
            if cap > peak:
                peak = cap
            drawdown = ((peak - cap) / peak) * 100.0
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                
        total_pnl = sum(t["pnl"] for t in trade_history)
        final_capital = initial_capital + float(total_pnl)
        
        return {
            "total_trades": total_trades,
            "total_wins": total_wins,
            "total_losses": len(losses),
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown": round(max_drawdown, 2),
            "total_pnl": total_pnl,
            "final_capital": round(final_capital, 2)
        }
