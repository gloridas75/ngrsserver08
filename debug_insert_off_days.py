import json
import sys
sys.path.insert(0, 'src')
from output_builder import insert_off_day_assignments
from collections import defaultdict

# Load input and simulate assignments
with open('RST-20260113-C9FE1E08_Solver_Input.json', 'r') as f:
    input_data = json.load(f)

# Create simple context
ctx = {
    'employees': input_data['employees'],
    'optimized_offsets': {}
}

# Simulate assignments (empty list for testing)
test_assignments = [
    {"employeeId": "00032093", "date": "2026-05-01", "shiftCode": "D"},
    {"employeeId": "00032093", "date": "2026-05-02", "shiftCode": "D"},
]

print("Input employees:", [e['employeeId'] for e in ctx['employees']])
print("Test assignments employee IDs:", list(set([a['employeeId'] for a in test_assignments])))

result = insert_off_day_assignments(test_assignments, input_data, ctx)

off_days = [a for a in result if a.get('status') == 'OFF_DAY']
off_day_emps = list(set([a['employeeId'] for a in off_days]))

print(f"\nGenerated OFF_DAYs: {len(off_days)}")
print(f"Employees with OFF_DAYs: {off_day_emps}")
print(f"Employee 00034833 has OFF_DAYs: {'00034833' in off_day_emps}")
