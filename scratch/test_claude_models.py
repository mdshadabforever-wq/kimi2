import urllib.request
import urllib.error
import json
import os

def run_claude_model(model_name):
    url = "https://api.anthropic.com/v1/messages"
    key = os.getenv("CLAUDE_API_KEY", "")
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    payload = {
        "model": model_name,
        "max_tokens": 1024,
        "messages": [
            {"role": "user", "content": "Hello, world"}
        ]
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"Claude success with model {model_name}:")
            print(resp.read().decode("utf-8")[:300])
            return True
    except Exception as e:
        print(f"Claude failed with model {model_name}: {e}")
        if hasattr(e, 'read'):
            print(e.read().decode("utf-8"))
        return False

if __name__ == "__main__":
    for m in ["claude-3-5-sonnet-20240620", "claude-3-5-sonnet-latest", "claude-3-haiku-20240307", "claude-3-5-haiku-20241022"]:
        if run_claude_model(m):
            break
