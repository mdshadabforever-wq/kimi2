import json
import os

log_path = r"C:\Users\shadab\.gemini\antigravity\brain\b1ea20ff-d5d4-4ef9-986e-f6f38b669ec4\.system_generated\logs\transcript_full.jsonl"

def search():
    if not os.path.exists(log_path):
        print("Log path does not exist")
        return
        
    keywords = ["Supertrend", "EMA", "indicator", "warmup", "alignment scoring", "alignment score"]
    
    with open("scratch/indicator_spec.txt", "w", encoding="utf-8") as out:
        with open(log_path, 'r', encoding='utf-8') as f:
            for idx, line in enumerate(f):
                try:
                    obj = json.loads(line)
                    content = obj.get("content", "")
                    if not content:
                        continue
                    found = [kw for kw in keywords if kw.lower() in content.lower()]
                    if found:
                        lines = content.split('\n')
                        out.write(f"=== Step Index {obj.get('step_index')} (Match: {found}) ===\n")
                        for l_no, l in enumerate(lines):
                            if any(kw.lower() in l.lower() for kw in keywords):
                                out.write(f"  Line {l_no}: {l}\n")
                        out.write("-" * 50 + "\n")
                except Exception as e:
                    pass
    print("Wrote results to scratch/indicator_spec.txt")

if __name__ == "__main__":
    search()
