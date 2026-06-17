import json
import os

log_path = r"C:\Users\shadab\.gemini\antigravity\brain\b1ea20ff-d5d4-4ef9-986e-f6f38b669ec4\.system_generated\logs\transcript_full.jsonl"

def extract():
    if not os.path.exists(log_path):
        print("Log path does not exist")
        return
        
    keywords = ["Multi Timeframe Engine", "Timeframe Analyzer", "Supertrend", "EMA", "trend calculation", "alignment scoring", "alignment rule", "trend_engine"]
    
    with open("scratch/spec_extract.txt", "w", encoding="utf-8") as out:
        with open(log_path, 'r', encoding='utf-8') as f:
            for idx, line in enumerate(f):
                try:
                    obj = json.loads(line)
                    if obj.get("step_index") != 0:
                        continue
                    content = obj.get("content", "")
                    if not content:
                        continue
                    
                    lines = content.split('\n')
                    for line_idx, l in enumerate(lines):
                        if any(kw.lower() in l.lower() for kw in keywords):
                            out.write(f"\n--- MATCH FOUND AT LINE {line_idx} ({l}) ---\n")
                            start = max(0, line_idx - 50)
                            end = min(len(lines), line_idx + 50)
                            for w_idx in range(start, end):
                                out.write(f"{w_idx}: {lines[w_idx]}\n")
                            out.write("=" * 80 + "\n")
                except Exception as e:
                    pass
    print("Wrote spec extract directly to scratch/spec_extract.txt")

if __name__ == "__main__":
    extract()
