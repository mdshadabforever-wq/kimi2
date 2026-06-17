import json
import os

log_path = r"C:\Users\shadab\.gemini\antigravity\brain\b1ea20ff-d5d4-4ef9-986e-f6f38b669ec4\.system_generated\logs\transcript_full.jsonl"

def dump_spec():
    if not os.path.exists(log_path):
        print("Log path does not exist")
        return
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            obj = json.loads(line)
            if obj.get("step_index") == 0:
                with open("scratch/full_spec.txt", "w", encoding="utf-8") as out:
                    out.write(obj.get("content"))
                print("Wrote complete untruncated specification to scratch/full_spec.txt")
                break

if __name__ == "__main__":
    dump_spec()
