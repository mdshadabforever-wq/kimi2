class AlignmentEngine:
    @staticmethod
    def calculate_alignment(trends: dict[str, str]) -> tuple[bool, str, int]:
        """Calculates trend alignment across the 4 timeframes (Daily, 1h, 15m, 5m).
        Minimum 3 of 4 timeframes must align in the same direction (either BULLISH or BEARISH).
        
        Returns: (is_aligned, aligned_direction, score)
        """
        required_tfs = ["Daily", "1h", "15m", "5m"]
        active_trends = {tf: trends.get(tf, "NEUTRAL") for tf in required_tfs}
        
        bullish_count = sum(1 for tf in required_tfs if active_trends[tf] == "BULLISH")
        bearish_count = sum(1 for tf in required_tfs if active_trends[tf] == "BEARISH")
        
        if bullish_count >= 3:
            score = 100 if bullish_count == 4 else 75
            return True, "BULLISH", score
        elif bearish_count >= 3:
            score = 100 if bearish_count == 4 else 75
            return True, "BEARISH", score
            
        return False, "NEUTRAL", 0
