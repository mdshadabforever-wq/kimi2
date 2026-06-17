import csv
import os
import database

class InstrumentLoader:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(InstrumentLoader, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self, csv_path="nifty50_instruments.csv"):
        if self.initialized:
            return
        self.csv_path = csv_path
        self.symbols = []
        self.token_to_symbol = {}
        self.symbol_to_token = {}
        self.load()
        self.initialized = True

    def load(self):
        """Loads symbols and tokens from CSV file, and syncs to database."""
        if not os.path.exists(self.csv_path):
            raise FileNotFoundError(f"Instrument file '{self.csv_path}' not found.")
            
        new_symbols = []
        new_token_to_symbol = {}
        new_symbol_to_token = {}
        
        with open(self.csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                symbol = row['symbol'].strip()
                token = row['token'].strip()
                new_symbols.append(symbol)
                new_token_to_symbol[token] = symbol
                new_symbol_to_token[symbol] = token
                
        self.symbols = new_symbols
        self.token_to_symbol = new_token_to_symbol
        self.symbol_to_token = new_symbol_to_token
        
        self.sync_to_db()
        print(f"Loaded {len(self.symbols)} instruments from '{self.csv_path}'.")

    def reload(self):
        """Reloads constituents from CSV and updates mappings on the fly."""
        self.load()

    def sync_to_db(self):
        """Syncs the loaded instruments to the geie_master_map table."""
        # Clean up database master map if needed or run UPSERT
        query = """
            INSERT INTO geie_master_map (symbol, last_updated)
            VALUES (%s, NOW())
            ON CONFLICT (symbol) DO UPDATE SET last_updated = NOW();
        """
        for sym in self.symbols:
            try:
                database.execute_query(query, (sym,))
            except Exception as e:
                # Silently catch DB errors if DB is simulating outage or not ready
                pass

    def get_symbol(self, token: str) -> str:
        return self.token_to_symbol.get(token)

    def get_token(self, symbol: str) -> str:
        return self.symbol_to_token.get(symbol)

    def is_valid_symbol(self, symbol: str) -> bool:
        return symbol in self.symbol_to_token
