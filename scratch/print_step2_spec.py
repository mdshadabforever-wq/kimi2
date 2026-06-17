import json
import os

log_path = r"C:\Users\shadab\.gemini\antigravity\brain\b1ea20ff-d5d4-4ef9-986e-f6f38b669ec4\.system_generated\logs\transcript_full.jsonl"

def search():
    if not os.path.exists(log_path):
        print("Log path does not exist")
        return
    with open("scratch/spec_step2.txt", "w", encoding="utf-8") as out:
        with open(log_path, 'r', encoding='utf-8') as f:
            for line in f:
                obj = json.loads(line)
                if obj.get("step_index") == 0:
                    content = obj.get("content", "")
                    lines = content.split('\n')
                    for idx, l in enumerate(lines):
                        if "MULTI TIMEFRAME" in l.upper() or "STEP 2" in l.upper():
                            out.write(f"--- MATCH AT LINE {idx}: {l} ---\n")
                            start = max(0, idx - 15)
                            end = min(len(lines), idx + 35)
                            for w in range(start, end):
                                out.write(f"{w}: {lines[w]}\n")
                            out.write("=" * 60 + "\n")
                    break

if __name__ == "__main__":
    search()
