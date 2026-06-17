import urllib.request
import urllib.error
import json
import sys
import os

# Set standard output to UTF-8 to prevent Windows terminal encoding errors
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def test_exact_user_gemini(model_name="gemini-flash-latest"):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
    key = os.getenv("GEMINI_API_KEY", "")
    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": key
    }
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": "Explain how AI works in a few words"
                    }
                ]
            }
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
            print(f"Gemini {model_name} response:")
            print(resp.read().decode("utf-8"))
            return True
    except Exception as e:
        print(f"Gemini {model_name} failed: {e}")
        if hasattr(e, 'read'):
            try:
                print(e.read().decode("utf-8"))
            except Exception:
                pass
        return False

def test_exact_user_claude():
    url = "https://api.anthropic.com/v1/messages"
    key = os.getenv("CLAUDE_API_KEY", "")
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    payload = {
        "model": "claude-sonnet-4-6",
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
            print("Claude response:")
            print(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Claude exact failed: {e}")
        if hasattr(e, 'read'):
            print(e.read().decode("utf-8"))

if __name__ == "__main__":
    gemini_tests = [
        # (version, model)
        ("v1beta", "gemini-flash-latest"),
        ("v1", "gemini-1.5-flash"),
        ("v1beta", "gemini-1.5-flash-latest"),
        ("v1beta", "gemini-2.5-flash"),
        ("v1beta", "gemini-1.5-pro"),
    ]
    for ver, model in gemini_tests:
        url = f"https://generativelanguage.googleapis.com/{ver}/models/{model}:generateContent"
        key = os.getenv("GEMINI_API_KEY", "")
        headers = {
            "Content-Type": "application/json",
            "X-goog-api-key": key
        }
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": "Explain how AI works in a few words"
                        }
                    ]
                }
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
                print(f"Gemini {ver}/{model} SUCCESS:")
                print(resp.read().decode("utf-8"))
                break
        except Exception as e:
            print(f"Gemini {ver}/{model} FAILED: {e}")
            if hasattr(e, 'read'):
                try:
                    print(e.read().decode("utf-8")[:300])
                except Exception:
                    pass
    test_exact_user_claude()
