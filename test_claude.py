#!/usr/bin/env python3
"""
Detailed diagnostic script for Claude API issues
"""

import os
import sys

print("=" * 70)
print("CLAUDE API DIAGNOSTIC TOOL")
print("=" * 70)

# Step 1: Check Python version
print("\n[1] Python Version")
print(f"    Version: {sys.version}")
if sys.version_info < (3, 7):
    print("    ⚠️  WARNING: Python 3.7+ recommended")

# Step 2: Check if anthropic package is installed
print("\n[2] Anthropic Package")
try:
    import anthropic
    print(f"    ✓ anthropic package installed")
    print(f"    Version: {anthropic.__version__}")
except ImportError as e:
    print(f"    ✗ anthropic package NOT installed")
    print(f"    Error: {e}")
    print("\n    To install: pip install anthropic")
    sys.exit(1)

# Step 3: Check API key
print("\n[3] API Key Check")
api_key = os.getenv("ANTHROPIC_API_KEY")
if api_key:
    print(f"    ✓ ANTHROPIC_API_KEY is set")
    print(f"    Length: {len(api_key)} characters")
    print(f"    Starts with: {api_key[:15]}...")
    print(f"    Ends with: ...{api_key[-10:]}")
    
    # Check for common issues
    if api_key.startswith(' ') or api_key.endswith(' '):
        print("    ⚠️  WARNING: API key has leading/trailing spaces!")
    if '\n' in api_key or '\r' in api_key:
        print("    ⚠️  WARNING: API key contains newline characters!")
    if not api_key.startswith('sk-ant-'):
        print("    ⚠️  WARNING: API key doesn't start with 'sk-ant-'")
        print("    (This might be an old or invalid key format)")
else:
    print("    ✗ ANTHROPIC_API_KEY is NOT set")
    print("\n    To set it:")
    print("    macOS/Linux: export ANTHROPIC_API_KEY='your-key-here'")
    print("    Windows:     setx ANTHROPIC_API_KEY \"your-key-here\"")
    sys.exit(1)

# Step 4: Try to create client
print("\n[4] Client Initialization")
try:
    client = anthropic.Anthropic(api_key=api_key)
    print("    ✓ Client object created")
except Exception as e:
    print(f"    ✗ Failed to create client")
    print(f"    Error type: {type(e).__name__}")
    print(f"    Error message: {e}")
    sys.exit(1)

# Step 5: Test basic connection with detailed error handling
print("\n[5] API Connection Test")
print("    Attempting to send a minimal test request...")
try:
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=10,
        messages=[
            {"role": "user", "content": "Say 'test'."}
        ]
    )
    print("    ✓ API request successful!")
    print(f"    Response: {response.content[0].text}")
    
except anthropic.AuthenticationError as e:
    print("    ✗ Authentication Error")
    print(f"    Message: {e}")
    print("\n    This means your API key is invalid or has been revoked.")
    print("    Solutions:")
    print("    1. Go to https://console.anthropic.com/settings/keys")
    print("    2. Create a new API key")
    print("    3. Set it again: export ANTHROPIC_API_KEY='new-key-here'")
    
except anthropic.PermissionDeniedError as e:
    print("    ✗ Permission Denied")
    print(f"    Message: {e}")
    print("\n    Your API key doesn't have permission for this request.")
    print("    Check your account status at https://console.anthropic.com/")
    
except anthropic.RateLimitError as e:
    print("    ✗ Rate Limit Exceeded")
    print(f"    Message: {e}")
    print("\n    You've made too many requests. Wait a moment and try again.")
    
except anthropic.APIConnectionError as e:
    print("    ✗ Connection Error")
    print(f"    Message: {e}")
    print("\n    Cannot reach Anthropic's servers.")
    print("    Solutions:")
    print("    1. Check your internet connection")
    print("    2. Check if you're behind a firewall/proxy")
    print("    3. Try: curl https://api.anthropic.com/")
    
except anthropic.APIError as e:
    print("    ✗ API Error")
    print(f"    Status code: {e.status_code if hasattr(e, 'status_code') else 'Unknown'}")
    print(f"    Message: {e}")
    print("\n    This is a general API error.")
    
except Exception as e:
    print("    ✗ Unexpected Error")
    print(f"    Error type: {type(e).__name__}")
    print(f"    Message: {e}")
    print(f"\n    Full error details:")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("DIAGNOSTIC COMPLETE")
print("=" * 70)