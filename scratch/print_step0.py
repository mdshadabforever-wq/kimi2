import json
import os

log_path = r"C:\Users\shadab\.gemini\antigravity\brain\b1ea20ff-d5d4-4ef9-986e-f6f38b669ec4\.system_generated\logs\transcript.jsonl"

def print_step0():
    if not os.path.exists(log_path):
        print("Log path does not exist")
        return
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            obj = json.loads(line)
            if obj.get("step_index") == 0:
                with open("scratch/spec_step0.txt", "w", encoding="utf-8") as out:
                    out.write(obj.get("content"))
                print("Wrote specification to scratch/spec_step0.txt")
                break

if __name__ == "__main__":
    print_step0()
