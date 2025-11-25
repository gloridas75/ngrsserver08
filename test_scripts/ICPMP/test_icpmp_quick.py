#!/usr/bin/env python3
import json
import requests
from pathlib import Path

# Read input file
with open("input/requirements_simple.json", 'r') as f:
    data = json.load(f)

# Call production endpoint
print("Calling production ICPMP endpoint...")
response = requests.post(
    "https://ngrssolver08.comcentricapps.com/configure",
    json=data,
    headers={'Content-Type': 'application/json'},
    timeout=300
)

print(f"Status: {response.status_code}")

if response.status_code == 200:
    result = response.json()
    
    # Save response
    with open("output/icpmp_production_test.json", 'w') as f:
        json.dump(result, f, indent=2)
    
    print("Response saved to output/icpmp_production_test.json")
    
    # Quick summary
    configs = result.get('configurations', [])
    print(f"\nProcessed {len(configs)} requirements")
    
    total_emp = sum(c['patterns'][0]['employeeCount'] for c in configs if c.get('patterns'))
    print(f"Total employees (best patterns): {total_emp}")
    
    for c in configs:
        req_id = c.get('requirementId')
        patterns = c.get('patterns', [])
        print(f"  {req_id}: {len(patterns)} alternatives")
else:
    print(f"Error: {response.text}")
