import json
import os

log_path = r"C:\Users\shadab\.gemini\antigravity\brain\b1ea20ff-d5d4-4ef9-986e-f6f38b669ec4\.system_generated\logs\transcript_full.jsonl"

def print_steps():
    if not os.path.exists(log_path):
        print("Log path does not exist")
        return
    with open("scratch/spec_steps_10_13.txt", "w", encoding="utf-8") as out:
        with open(log_path, 'r', encoding='utf-8') as f:
            for line in f:
                obj = json.loads(line)
                step_idx = obj.get("step_index")
                if step_idx in [10, 13]:
                    out.write(f"=== STEP {step_idx} ===\n")
                    out.write(obj.get("content") + "\n")
                    out.write("=" * 60 + "\n")

if __name__ == "__main__":
    print_steps()
