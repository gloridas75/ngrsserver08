"""Debug script to analyze work pattern matching."""
import json
from datetime import date

# Load input
with open('input/input_v0.7.json') as f:
    data = json.load(f)

# Load output
with open('output/output_2111_1812.json') as f:
    output = json.load(f)

# Get employees and patterns
employees = {e['employeeId']: e for e in data['employees']}
demand = data['demandItems'][0]
requirements = {r['requirementId']: r for r in demand['requirements']}

# Get anchor date
anchor_str = demand['shifts'][0].get('coverageAnchor', demand.get('shiftStartDate'))
anchor = date.fromisoformat(anchor_str)

print(f"Coverage Anchor: {anchor} ({anchor.strftime('%A')})\n")

# Analyze first week of assignments
print("=" * 80)
print("EMPLOYEE ASSIGNMENTS - FIRST WEEK (Dec 1-7)")
print("=" * 80)

for emp_id, emp in employees.items():
    offset = emp.get('rotationOffset', 0)
    product = emp['productTypeId']
    
    # Find relevant requirement pattern
    req_pattern = None
    for req_id, req in requirements.items():
        if req['productTypeId'] == product:
            req_pattern = req.get('workPattern', [])
            print(f"\n{emp_id} (offset={offset}, product={product})")
            print(f"  Pattern: {req_pattern}")
            break
    
    if not req_pattern:
        continue
    
    # Check first 7 days
    for day_num in range(7):
        current_date = date(2025, 12, 1 + day_num)
        days_from_anchor = (current_date - anchor).days
        emp_cycle_day = (days_from_anchor - offset) % len(req_pattern)
        expected_shift = req_pattern[emp_cycle_day]
        
        # Find actual assignment
        actual = []
        for assignment in output['assignments']:
            if (assignment.get('employeeId') == emp_id and 
                assignment.get('date') == current_date.isoformat()):
                actual.append(assignment['shiftCode'])
        
        actual_str = ', '.join(actual) if actual else 'OFF'
        match = "✓" if (actual and expected_shift in actual) or (not actual and expected_shift == 'O') else "✗"
        
        print(f"  {current_date.strftime('%Y-%m-%d %a')}: Expected={expected_shift:2s}, Actual={actual_str:3s} {match}")

print("\n" + "=" * 80)
print("REQUIREMENT PATTERNS")
print("=" * 80)
for req_id, req in requirements.items():
    pattern = req.get('workPattern', [])
    print(f"{req_id} ({req['productTypeId']}): {pattern}")
