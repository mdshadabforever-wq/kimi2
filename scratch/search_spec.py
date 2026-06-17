import json
import os

log_path = r"C:\Users\shadab\.gemini\antigravity\brain\b1ea20ff-d5d4-4ef9-986e-f6f38b669ec4\.system_generated\logs\transcript_full.jsonl"

def search():
    if not os.path.exists(log_path):
        print(f"Log path does not exist: {log_path}")
        return
        
    keywords = ["Multi Timeframe Engine", "Timeframe Analyzer", "trend calculation", "EMA", "Supertrend", "cross-timeframe rule", "alignment scoring", "alignment rule", "trend_engine"]
    
    with open(log_path, 'r', encoding='utf-8') as f:
        for line_no, line in enumerate(f, 1):
            try:
                obj = json.loads(line)
                content = obj.get("content", "")
                if not content:
                    continue
                # If any keyword is found
                found = [kw for kw in keywords if kw.lower() in content.lower()]
                if found:
                    print(f"--- Line {line_no} (Match: {found}) ---")
                    # Print first 200 characters of matching section
                    print(content[:600] + "...")
            except Exception as e:
                pass

if __name__ == "__main__":
    search()
