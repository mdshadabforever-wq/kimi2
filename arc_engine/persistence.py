import datetime
import database


class ARCPersistence:
    """Handles all database write operations for the ARC Engine.
    Clarification 008, Sections 11 and 4.

    Schema decision (accepted):
        signals.arc_decision stores enum label only (APPROVE/CAUTION/REJECT).
        Full ARC decision JSON is written to audit_log.metadata via audit.py.
        No schema migration required.
    """

    @staticmethod
    def save_arc_decision_label(signal_id: str, arc_decision: str) -> bool:
        """Writes the ARC decision label (APPROVE/CAUTION/REJECT) to signals.arc_decision.

        Args:
            signal_id: The unique signal identifier.
            arc_decision: One of APPROVE / CAUTION / REJECT.

        Returns:
            True if successful, False on failure.
        """
        query = """
            UPDATE signals
            SET arc_decision = %s
            WHERE signal_id = %s;
        """
        try:
            database.execute_query(query, (arc_decision, signal_id))
            return True
        except Exception as e:
            print(f"[ARC PERSISTENCE] Error saving arc_decision for {signal_id}: {e}")
            return False

    @staticmethod
    def save_geie_direction_to_signal(signal_id: str, geie_direction: str, geie_confidence: str) -> bool:
        """Writes GEIE direction and confidence to the signals table.
        Uses existing signals.geie_direction and geie_confidence columns.
        """
        query = """
            UPDATE signals
            SET geie_direction = %s, geie_confidence = %s
            WHERE signal_id = %s;
        """
        try:
            database.execute_query(query, (geie_direction, geie_confidence, signal_id))
            return True
        except Exception as e:
            print(f"[ARC PERSISTENCE] Error saving GEIE fields for {signal_id}: {e}")
            return False

    @staticmethod
    def cancel_rejected_signal(signal_id: str) -> bool:
        """Updates signal status to CANCELLED when ARC issues a REJECT.
        Only cancels if status is currently ACTIVE.
        """
        query = """
            UPDATE signals
            SET status = 'CANCELLED'
            WHERE signal_id = %s AND status = 'ACTIVE';
        """
        try:
            database.execute_query(query, (signal_id,))
            return True
        except Exception as e:
            print(f"[ARC PERSISTENCE] Error cancelling signal {signal_id}: {e}")
            return False

    @staticmethod
    def load_active_signals_with_arc(session_date: datetime.date) -> list:
        """Loads all active signals that have an ARC decision for the session date.
        Used during recovery to restore in-memory state without re-calling Claude.
        """
        query = """
            SELECT signal_id, symbol, direction, arc_decision
            FROM signals
            WHERE created_at::date = %s AND arc_decision IS NOT NULL
            ORDER BY created_at ASC;
        """
        try:
            rows = database.execute_query(query, (session_date,), fetch=True)
            return [
                {"signal_id": r[0], "symbol": r[1], "direction": r[2], "arc_decision": r[3]}
                for r in rows
            ] if rows else []
        except Exception as e:
            print(f"[ARC PERSISTENCE] Error loading active signals: {e}")
            return []
