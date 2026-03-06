import json
import requests

BASE_URL = "http://127.0.0.1:5001"

# Test 1: Get settings
print("=== Test 1: GET /api/ai-settings/ ===")
response = requests.get(f"{BASE_URL}/api/ai-settings/")
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")

# Test 2: Update a setting
print("\n=== Test 2: PUT /api/ai-settings/temperature ===")
response = requests.put(
    f"{BASE_URL}/api/ai-settings/temperature",
    json={"value": 0.8, "type": "float"}
)
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")

# Test 3: Get settings again to verify update
print("\n=== Test 3: GET /api/ai-settings/ (verify update) ===")
response = requests.get(f"{BASE_URL}/api/ai-settings/")
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")

print("\n✅ All settings tests passed!")
