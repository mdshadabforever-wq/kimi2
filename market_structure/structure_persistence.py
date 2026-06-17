import datetime
from decimal import Decimal
import database

class StructurePersistence:
    @staticmethod
    def save_structure(time: datetime.datetime, symbol: str, timeframe: str, structure_type: str, direction: str, top_price: Decimal, bottom_price: Decimal, mitigated: bool = False, mitigated_at: datetime.datetime = None):
        """Saves a BOS, CHOCH, or FVG structural point to the smc_structures TimescaleDB table."""
        query = """
            INSERT INTO smc_structures (time, symbol, timeframe, structure_type, direction, top_price, bottom_price, mitigated, mitigated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (time, symbol, timeframe, structure_type, direction)
            DO UPDATE SET
                top_price = EXCLUDED.top_price,
                bottom_price = EXCLUDED.bottom_price,
                mitigated = EXCLUDED.mitigated,
                mitigated_at = EXCLUDED.mitigated_at;
        """
        try:
            database.execute_query(query, (time, symbol, timeframe, structure_type, direction, top_price, bottom_price, mitigated, mitigated_at))
        except Exception as e:
            print(f"[STRUCTURE PERSISTENCE] Error saving structure for {symbol}: {e}")

    @staticmethod
    def save_order_block(symbol: str, timeframe: str, ob_type: str, ob_high: Decimal, ob_low: Decimal, ob_midpoint: Decimal, first_detected: datetime.datetime):
        """Saves a new Order Block to the order_block_memory table if it doesn't already exist."""
        check_query = """
            SELECT id FROM order_block_memory
            WHERE symbol = %s AND timeframe = %s AND ob_type = %s AND ob_high = %s AND ob_low = %s;
        """
        try:
            res = database.execute_query(check_query, (symbol, timeframe, ob_type, ob_high, ob_low), fetch=True)
            if not res:
                insert_query = """
                    INSERT INTO order_block_memory (symbol, timeframe, ob_type, ob_high, ob_low, ob_midpoint, first_detected)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                """
                database.execute_query(insert_query, (symbol, timeframe, ob_type, ob_high, ob_low, ob_midpoint, first_detected))
        except Exception as e:
            print(f"[STRUCTURE PERSISTENCE] Error saving order block for {symbol}: {e}")

    @staticmethod
    def update_order_block(ob_id: int, last_tested: datetime.datetime, test_count: int, held_count: int, broken: bool, broken_at: datetime.datetime):
        """Updates test count, held count, and mitigation status of an existing Order Block."""
        query = """
            UPDATE order_block_memory
            SET last_tested = %s, test_count = %s, held_count = %s, broken = %s, broken_at = %s
            WHERE id = %s;
        """
        try:
            database.execute_query(query, (last_tested, test_count, held_count, broken, broken_at, ob_id))
        except Exception as e:
            print(f"[STRUCTURE PERSISTENCE] Error updating order block ID {ob_id}: {e}")

    @staticmethod
    def load_structures(symbol: str, timeframe: str) -> list[dict]:
        """Loads all persisted structural points for a symbol and timeframe."""
        query = """
            SELECT time, structure_type, direction, top_price, bottom_price, mitigated, mitigated_at
            FROM smc_structures
            WHERE symbol = %s AND timeframe = %s
            ORDER BY time ASC;
        """
        structures = []
        try:
            res = database.execute_query(query, (symbol, timeframe), fetch=True)
            for row in res:
                structures.append({
                    "time": row[0],
                    "structure_type": row[1],
                    "direction": row[2],
                    "top_price": Decimal(str(row[3])),
                    "bottom_price": Decimal(str(row[4])),
                    "mitigated": row[5],
                    "mitigated_at": row[6]
                })
        except Exception as e:
            print(f"[STRUCTURE PERSISTENCE] Error loading structures for {symbol}: {e}")
        return structures

    @staticmethod
    def load_order_blocks(symbol: str, timeframe: str) -> list[dict]:
        """Loads all active (unbroken) Order Blocks for a symbol and timeframe."""
        query = """
            SELECT id, ob_type, ob_high, ob_low, ob_midpoint, first_detected, last_tested, test_count, held_count, broken, broken_at
            FROM order_block_memory
            WHERE symbol = %s AND timeframe = %s AND broken = FALSE
            ORDER BY first_detected ASC;
        """
        obs = []
        try:
            res = database.execute_query(query, (symbol, timeframe), fetch=True)
            for row in res:
                obs.append({
                    "id": row[0],
                    "ob_type": row[1],
                    "ob_high": Decimal(str(row[2])),
                    "ob_low": Decimal(str(row[3])),
                    "ob_midpoint": Decimal(str(row[4])),
                    "first_detected": row[5],
                    "last_tested": row[6],
                    "test_count": row[7],
                    "held_count": row[8],
                    "broken": row[9],
                    "broken_at": row[10]
                })
        except Exception as e:
            print(f"[STRUCTURE PERSISTENCE] Error loading order blocks for {symbol}: {e}")
        return obs
