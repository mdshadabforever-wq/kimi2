import os
import sys
from dotenv import load_dotenv
import sys

# Configure standard output to use UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Add root folder to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Load dot env file explicitly
load_dotenv()

from production.gemini_production import GeminiProduction
from production.claude_production import ClaudeProduction

def test_gemini():
    print("=== Testing Real Gemini API ===")
    api_key = os.getenv("GEMINI_API_KEY")
    print(f"Loaded Gemini Key: {api_key[:10]}...")
    
    gemini = GeminiProduction(api_key=api_key)
    try:
        response = gemini.generate_report(
            prompt="Hello, this is IIIS. Confirm you are online by replying 'Gemini is online and ready for IIIS production.'",
            system_context="You are the IIIS assistant."
        )
        print("[SUCCESS] Gemini API Response:")
        print(response.strip())
        return True
    except Exception as e:
        print(f"[FAILED] Gemini API call failed: {e}")
        return False

def test_claude():
    print("\n=== Testing Real Claude API ===")
    api_key = os.getenv("CLAUDE_API_KEY")
    print(f"Loaded Claude Key: {api_key[:10]}...")
    
    claude = ClaudeProduction(api_key=api_key)
    try:
        # We test the postmortem tool extraction schema
        test_facts = {
            "symbol": "RELIANCE",
            "direction": "LONG",
            "entry_price": 2400.00,
            "exit_price": 2380.00,
            "stop_loss": 2380.00,
            "volume_at_entry": 10000,
            "average_volume": 50000
        }
        response = claude.generate_postmortem(test_facts)
        print("[SUCCESS] Claude API Response (Structured JSON Tool Use):")
        print(response)
        return True
    except Exception as e:
        print(f"[FAILED] Claude API call failed: {e}")
        return False

if __name__ == "__main__":
    gem_ok = test_gemini()
    cla_ok = test_claude()
    if gem_ok and cla_ok:
        print("\n[OK] Both Gemini and Claude APIs are fully verified and operational!")
    else:
        print("\n[ERROR] One or both API calls failed. Please inspect logs.")
