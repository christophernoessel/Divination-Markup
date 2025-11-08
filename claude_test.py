#!/usr/bin/env python3
"""
Test script to verify Claude API connection and configuration
"""

import os
from divmarkup_ask_claude import AskClaude

def test_api_key():
    """Check if API key is set"""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        print("✓ ANTHROPIC_API_KEY is set")
        print(f"  Key starts with: {api_key[:10]}...")
        return True
    else:
        print("✗ ANTHROPIC_API_KEY is NOT set")
        print("\nTo set it:")
        print("  macOS/Linux: export ANTHROPIC_API_KEY='your-key-here'")
        print("  Windows:     setx ANTHROPIC_API_KEY \"your-key-here\"")
        return False

def test_client_initialization():
    """Test if Claude client initializes"""
    print("\nInitializing Claude client...")
    try:
        ask_claude = AskClaude()
        if ask_claude.client is not None:
            print("✓ Claude client initialized successfully")
            return True, ask_claude
        else:
            print("✗ Claude client failed to initialize")
            print("  Check that your API key is valid")
            return False, None
    except Exception as e:
        print(f"✗ Error initializing Claude client: {e}")
        return False, None

def test_simple_request(ask_claude):
    """Test a simple API request"""
    print("\nTesting simple API request...")
    test_text = "The sun rises in the east."
    
    try:
        response = ask_claude.recommend_apodosis(test_text)
        
        if response == ask_claude.no_gpt_error_message():
            print("✗ API request failed")
            return False
        
        print("✓ API request successful")
        print(f"  Sent: {test_text}")
        print(f"  Response: {response}")
        return True
    except Exception as e:
        print(f"✗ Error making API request: {e}")
        return False

def main():
    print("=" * 60)
    print("Claude API Connection Test")
    print("=" * 60)
    
    # Test 1: Check API key
    if not test_api_key():
        print("\n❌ Cannot proceed without API key")
        return
    
    # Test 2: Initialize client
    success, ask_claude = test_client_initialization()
    if not success:
        print("\n❌ Cannot proceed without valid client")
        return
    
    # Test 3: Make a simple request
    if test_simple_request(ask_claude):
        print("\n" + "=" * 60)
        print("✅ All tests passed! Claude is ready to use.")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("❌ API request failed. Check your API key and internet connection.")
        print("=" * 60)

if __name__ == "__main__":
    main()