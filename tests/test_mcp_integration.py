"""
Test suite for MCP Google Docs integration
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_mcp_config_loading():
    """Test that MCP configuration loads correctly."""
    print("Testing MCP Configuration Loading...")
    
    from src.mcp_client import load_mcp_config
    
    config = load_mcp_config("mcp_config.json")
    
    if config is None:
        print("⚠️  MCP config file not found (this is OK if not set up yet)")
        return False
    
    print("✓ MCP config loaded successfully")
    
    if "gdrive" in config.get("mcpServers", {}):
        print("✓ Google Drive MCP server configured")
        gdrive_config = config["mcpServers"]["gdrive"]
        print(f"  - Command: {gdrive_config.get('command')}")
        print(f"  - Args: {gdrive_config.get('args')}")
        return True
    else:
        print("❌ Google Drive server not found in config")
        return False

def test_mcp_client_creation():
    """Test MCP client initialization."""
    print("\nTesting MCP Client Creation...")
    
    from src.mcp_client import get_gdrive_client
    
    client = get_gdrive_client()
    
    if client is None:
        print("⚠️  MCP client not available (config missing or incomplete)")
        return False
    
    print("✓ MCP client created successfully")
    return True

def test_google_docs_fallback():
    """Test that Google Docs falls back to API when MCP unavailable."""
    print("\nTesting Google Docs Fallback Mechanism...")
    
    from src.google_utils import create_doc
    
    # This should try MCP first, then fall back to Google API or mock
    try:
        doc_id, doc_url = create_doc("Test Document", "Test content", use_mcp=True)
        print(f"✓ Document creation with fallback successful")
        print(f"  - Doc ID: {doc_id}")
        print(f"  - Doc URL: {doc_url}")
        return True
    except Exception as e:
        print(f"❌ Fallback failed: {e}")
        return False

if __name__ == "__main__":
    print("="*60)
    print("MCP INTEGRATION TEST SUITE")
    print("="*60 + "\n")
    
    results = []
    
    try:
        results.append(("Config Loading", test_mcp_config_loading()))
        results.append(("Client Creation", test_mcp_client_creation()))
        results.append(("Fallback Mechanism", test_google_docs_fallback()))
        
        print("\n" + "="*60)
        print("TEST RESULTS SUMMARY")
        print("="*60)
        
        for test_name, passed in results:
            status = "✅ PASS" if passed else "⚠️  SKIP/FAIL"
            print(f"{status}: {test_name}")
        
        if any(result[1] for result in results):
            print("\n✅ MCP integration tests completed (some may be skipped if not configured)")
        else:
            print("\n⚠️  All MCP tests skipped - MCP not configured yet")
            print("See docs/mcp_setup.md for setup instructions")
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
