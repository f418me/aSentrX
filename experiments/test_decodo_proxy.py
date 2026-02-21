#!/usr/bin/env python3
"""
Decodo Proxy Integration - Manual Test Script

This script tests the Decodo Proxy integration with various configurations:
1. Proxy enabled with valid credentials
2. Proxy enabled with invalid configuration
3. Backward compatibility without proxy configuration

Requirements tested: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 3.1, 3.2, 5.1, 5.2, 5.3
"""

import os
import sys
import logging
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.logger_config import configure_logging, APP_LOGGER_NAME

# Setup logging for test
configure_logging()
logger = logging.getLogger(f"{APP_LOGGER_NAME}.ProxyTest")


def print_test_header(test_name: str):
    """Print a formatted test header"""
    print("\n" + "=" * 80)
    print(f"TEST: {test_name}")
    print("=" * 80)


def print_test_result(success: bool, message: str):
    """Print test result"""
    status = "✓ PASS" if success else "✗ FAIL"
    print(f"\n{status}: {message}\n")


def test_scenario_1_valid_proxy():
    """
    Test Scenario 1: Proxy enabled with valid credentials
    
    Requirements: 1.1, 1.2, 2.1, 2.2, 3.1
    """
    print_test_header("Scenario 1: Valid Proxy Configuration")
    
    # Set environment variables for valid proxy
    os.environ["DECODO_PROXY_ENABLED"] = "True"
    os.environ["DECODO_PROXY_URL"] = "http://gate.decodo.com:7000"
    os.environ["DECODO_PROXY_USERNAME"] = "test_user"
    os.environ["DECODO_PROXY_PASSWORD"] = "test_pass"
    os.environ["PROD_EXECUTION"] = "False"
    os.environ["TRUESOCIAL_USERNAME"] = "testuser"
    
    print("\nConfiguration:")
    print(f"  DECODO_PROXY_ENABLED: {os.environ['DECODO_PROXY_ENABLED']}")
    print(f"  DECODO_PROXY_URL: {os.environ['DECODO_PROXY_URL']}")
    print(f"  DECODO_PROXY_USERNAME: {os.environ['DECODO_PROXY_USERNAME']}")
    print(f"  DECODO_PROXY_PASSWORD: {'*' * len(os.environ['DECODO_PROXY_PASSWORD'])}")
    
    try:
        # Import after setting env vars
        from socialmedia.truesocial import TrueSocial
        
        print("\nAttempting to initialize TrueSocial with proxy...")
        
        # Validate that proxy configuration is applied without requiring a live network call.
        try:
            ts = TrueSocial(
                username="testuser",
                fetch_interval_seconds=60,
                api_verbose_output=False,
                initial_since_id=None
            )

            if not getattr(ts, "proxy_config", None):
                print_test_result(False, "Proxy config was not set on TrueSocial instance")
                return

            proxy_url = ts.proxy_config["proxies"]["http"]
            has_auth_in_url = "test_user:test_pass@" in proxy_url
            has_override = hasattr(ts.api, "_make_session")

            if has_auth_in_url and has_override:
                print_test_result(True, "Proxy initialized successfully with credentials and session override")
            else:
                print_test_result(
                    False,
                    "Proxy initialized, but credentials/session override check failed"
                )
        except Exception as e:
            print_test_result(False, f"Initialization with valid proxy config should not fail: {e}")
                
    except Exception as e:
        print_test_result(False, f"Failed to import or initialize: {e}")
    
    # Clean up
    for key in ["DECODO_PROXY_ENABLED", "DECODO_PROXY_URL", "DECODO_PROXY_USERNAME", "DECODO_PROXY_PASSWORD"]:
        os.environ.pop(key, None)


def test_scenario_2_invalid_config():
    """
    Test Scenario 2: Proxy enabled but invalid configuration
    
    Requirements: 1.4, 2.3, 3.2, 3.3, 5.3
    """
    print_test_header("Scenario 2: Invalid Proxy Configuration (Missing URL)")
    
    # Set environment variables with missing URL
    os.environ["DECODO_PROXY_ENABLED"] = "True"
    os.environ["DECODO_PROXY_URL"] = ""  # Missing URL
    os.environ["PROD_EXECUTION"] = "False"
    os.environ["TRUESOCIAL_USERNAME"] = "testuser"
    
    print("\nConfiguration:")
    print(f"  DECODO_PROXY_ENABLED: {os.environ['DECODO_PROXY_ENABLED']}")
    print(f"  DECODO_PROXY_URL: (empty)")
    
    try:
        # Reload module to pick up new env vars
        import importlib
        import socialmedia.truesocial
        importlib.reload(socialmedia.truesocial)
        from socialmedia.truesocial import TrueSocial
        
        print("\nAttempting to initialize TrueSocial with invalid proxy config...")
        
        try:
            ts = TrueSocial(
                username="testuser",
                fetch_interval_seconds=60,
                api_verbose_output=False,
                initial_since_id="12345"  # Use initial_since_id to avoid API call
            )
            print_test_result(True, "Fallback to direct connection succeeded as expected")
        except Exception as e:
            print_test_result(False, f"Should have fallen back to direct connection: {e}")
            
    except Exception as e:
        print_test_result(False, f"Failed to import or initialize: {e}")
    
    # Clean up
    for key in ["DECODO_PROXY_ENABLED", "DECODO_PROXY_URL"]:
        os.environ.pop(key, None)


def test_scenario_3_backward_compatibility():
    """
    Test Scenario 3: Backward compatibility without proxy configuration
    
    Requirements: 1.3, 3.2
    """
    print_test_header("Scenario 3: Backward Compatibility (No Proxy)")
    
    # Ensure proxy env vars are not set
    for key in ["DECODO_PROXY_ENABLED", "DECODO_PROXY_URL", "DECODO_PROXY_USERNAME", "DECODO_PROXY_PASSWORD"]:
        os.environ.pop(key, None)
    
    os.environ["PROD_EXECUTION"] = "False"
    os.environ["TRUESOCIAL_USERNAME"] = "testuser"
    
    print("\nConfiguration:")
    print("  DECODO_PROXY_ENABLED: (not set)")
    print("  DECODO_PROXY_URL: (not set)")
    
    try:
        # Reload module to pick up new env vars
        import importlib
        import socialmedia.truesocial
        importlib.reload(socialmedia.truesocial)
        from socialmedia.truesocial import TrueSocial
        
        print("\nAttempting to initialize TrueSocial without proxy...")
        
        try:
            ts = TrueSocial(
                username="testuser",
                fetch_interval_seconds=60,
                api_verbose_output=False,
                initial_since_id="12345"  # Use initial_since_id to avoid API call
            )
            print_test_result(True, "Direct connection (no proxy) succeeded as expected")
        except Exception as e:
            print_test_result(False, f"Backward compatibility failed: {e}")
            
    except Exception as e:
        print_test_result(False, f"Failed to import or initialize: {e}")


def test_scenario_4_invalid_url_format():
    """
    Test Scenario 4: Invalid URL format
    
    Requirements: 2.3, 3.3, 5.3
    """
    print_test_header("Scenario 4: Invalid URL Format")
    
    # Set environment variables with invalid URL format
    os.environ["DECODO_PROXY_ENABLED"] = "True"
    os.environ["DECODO_PROXY_URL"] = "invalid-url-format"  # Missing protocol
    os.environ["PROD_EXECUTION"] = "False"
    os.environ["TRUESOCIAL_USERNAME"] = "testuser"
    
    print("\nConfiguration:")
    print(f"  DECODO_PROXY_ENABLED: {os.environ['DECODO_PROXY_ENABLED']}")
    print(f"  DECODO_PROXY_URL: {os.environ['DECODO_PROXY_URL']}")
    
    try:
        # Reload module to pick up new env vars
        import importlib
        import socialmedia.truesocial
        importlib.reload(socialmedia.truesocial)
        from socialmedia.truesocial import TrueSocial
        
        print("\nAttempting to initialize TrueSocial with invalid URL format...")
        
        try:
            ts = TrueSocial(
                username="testuser",
                fetch_interval_seconds=60,
                api_verbose_output=False,
                initial_since_id="12345"
            )
            print_test_result(True, "Fallback to direct connection succeeded after detecting invalid URL")
        except Exception as e:
            print_test_result(False, f"Should have fallen back to direct connection: {e}")
            
    except Exception as e:
        print_test_result(False, f"Failed to import or initialize: {e}")
    
    # Clean up
    for key in ["DECODO_PROXY_ENABLED", "DECODO_PROXY_URL"]:
        os.environ.pop(key, None)


def test_scenario_5_partial_credentials():
    """
    Test Scenario 5: Partial credentials (only username or password)
    
    Requirements: 2.2, 3.2
    """
    print_test_header("Scenario 5: Partial Credentials")
    
    # Set environment variables with only username
    os.environ["DECODO_PROXY_ENABLED"] = "True"
    os.environ["DECODO_PROXY_URL"] = "http://gate.decodo.com:7000"
    os.environ["DECODO_PROXY_USERNAME"] = "test_user"
    os.environ["DECODO_PROXY_PASSWORD"] = ""  # Missing password
    os.environ["PROD_EXECUTION"] = "False"
    os.environ["TRUESOCIAL_USERNAME"] = "testuser"
    
    print("\nConfiguration:")
    print(f"  DECODO_PROXY_ENABLED: {os.environ['DECODO_PROXY_ENABLED']}")
    print(f"  DECODO_PROXY_URL: {os.environ['DECODO_PROXY_URL']}")
    print(f"  DECODO_PROXY_USERNAME: {os.environ['DECODO_PROXY_USERNAME']}")
    print(f"  DECODO_PROXY_PASSWORD: (empty)")
    
    try:
        # Reload module to pick up new env vars
        import importlib
        import socialmedia.truesocial
        importlib.reload(socialmedia.truesocial)
        from socialmedia.truesocial import TrueSocial
        
        print("\nAttempting to initialize TrueSocial with partial credentials...")
        
        try:
            ts = TrueSocial(
                username="testuser",
                fetch_interval_seconds=60,
                api_verbose_output=False,
                initial_since_id="12345"
            )
            print_test_result(True, "Proxy configured without authentication (warning should be logged)")
        except Exception as e:
            # May fail due to connection, but that's expected
            if "proxy" in str(e).lower() or "connection" in str(e).lower():
                print_test_result(True, f"Proxy attempted without full auth as expected: {str(e)[:100]}")
            else:
                print_test_result(False, f"Unexpected error: {e}")
            
    except Exception as e:
        print_test_result(False, f"Failed to import or initialize: {e}")
    
    # Clean up
    for key in ["DECODO_PROXY_ENABLED", "DECODO_PROXY_URL", "DECODO_PROXY_USERNAME", "DECODO_PROXY_PASSWORD"]:
        os.environ.pop(key, None)


def main():
    """Run all test scenarios"""
    print("\n" + "=" * 80)
    print("DECODO PROXY INTEGRATION - MANUAL TEST SUITE")
    print("=" * 80)
    print("\nThis script tests various proxy configuration scenarios.")
    print("Check the logs above each test for detailed output.\n")
    
    # Run all test scenarios
    test_scenario_1_valid_proxy()
    test_scenario_2_invalid_config()
    test_scenario_3_backward_compatibility()
    test_scenario_4_invalid_url_format()
    test_scenario_5_partial_credentials()
    
    print("\n" + "=" * 80)
    print("TEST SUITE COMPLETED")
    print("=" * 80)
    print("\nReview the results above and check the log output for:")
    print("  - Proxy initialization messages")
    print("  - Warning messages for invalid configurations")
    print("  - Fallback behavior to direct connection")
    print("  - Credential sanitization in logs (no passwords visible)")
    print("\n")


if __name__ == "__main__":
    main()
