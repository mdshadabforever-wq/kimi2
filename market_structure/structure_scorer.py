class StructureScorer:
    @staticmethod
    def calculate_quality_score(confirmations_count: int) -> int:
        """Calculates the SMC Quality Score (0-100) based on the number of confirmed structures:
          - 0 confirmations = 0
          - 1 confirmation = 40
          - 2 confirmations = 70
          - 3+ confirmations = 100
        """
        if confirmations_count == 0:
            return 0
        elif confirmations_count == 1:
            return 40
        elif confirmations_count == 2:
            return 70
        else:
            return 100
