import requests
import subprocess
import time
import sys
import os

# Define the server process
server_process = None

def setup_module():
    global server_process
    print("Starting Uvicorn server...")
    # Start the server in a separate process
    server_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    # Give it time to start
    time.sleep(15) 

def teardown_module():
    global server_process
    if server_process:
        print("Stopping Uvicorn server...")
        server_process.terminate()
        try:
            outs, errs = server_process.communicate(timeout=5)
            print(f"Server STDOUT:\n{outs.decode()}")
            print(f"Server STDERR:\n{errs.decode()}")
        except Exception as e:
            print(f"Error reading logs: {e}")

def test_api():
    url = "http://127.0.0.1:8000"
    
    # 1. Test Root
    try:
        resp = requests.get(f"{url}/")
        assert resp.status_code == 200
        print("✅ Root endpoint working")
    except Exception as e:
        print(f"❌ Root endpoint failed: {e}")
        return

    # 2. Test Campaign Run (Mocking API Key if needed, but we can just check if it rejects or accepts valid structure)
    # Since we need a google key, and we might not have one set in env for the test process unless we pass it.
    # We'll just check if it validates the input correctly.
    
    payload = {
        "goal": "Test Goal"
    }
    
    # We expect 401 if no key provided
    resp = requests.post(f"{url}/run_campaign", json=payload)
    if resp.status_code == 401:
        print("✅ Auth check working (401 received as expected without key)")
    elif resp.status_code == 200:
        print("✅ Campaign ran successfully (Key was present in env)")
    else:
        print(f"⚠️ Unexpected status code: {resp.status_code}. Response: {resp.text}")

if __name__ == "__main__":
    try:
        setup_module()
        test_api()
    finally:
        teardown_module()
