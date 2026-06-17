import json
import os

log_path = r"C:\Users\shadab\.gemini\antigravity\brain\b1ea20ff-d5d4-4ef9-986e-f6f38b669ec4\.system_generated\logs\transcript.jsonl"

def search():
    if not os.path.exists(log_path):
        print("Log path does not exist")
        return
    with open(log_path, 'r', encoding='utf-8') as f:
        for idx, line in enumerate(f, 1):
            try:
                obj = json.loads(line)
                step_idx = obj.get("step_index")
                source = obj.get("source")
                type_ = obj.get("type")
                if type_ == "USER_INPUT":
                    content = obj.get("content", "")
                    print(f"Step {step_idx}: Type={type_}, Length={len(content)}")
                    print(content[:500])
                    print("=" * 40)
            except Exception as e:
                pass

if __name__ == "__main__":
    search()
