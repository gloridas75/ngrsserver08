import json
from datetime import datetime, timedelta
from collections import defaultdict
import sys
sys.path.insert(0, 'context/engine')
from solver_engine import calculate_employee_work_pattern, calculate_pattern_day

# Load input
with open('RST-20260113-C9FE1E08_Solver_Input.json', 'r') as f:
    input_data = json.load(f)

# Get pattern info
demands = input_data.get('demandItems', [])
base_pattern = demands[0]['requirements'][0]['workPattern']
pattern_start_date = demands[0]['shiftStartDate']
coverage_days = demands[0]['requirements'][0].get('coverageDays', None)

print(f"Base pattern: {base_pattern}")
print(f"Pattern start date: {pattern_start_date}")

# Test employee 00034833
emp = next(e for e in input_data['employees'] if e['employeeId'] == '00034833')
emp_offset = emp['rotationOffset']

print(f"\nEmployee 00034833:")
print(f"  Offset: {emp_offset}")

# Calculate employee pattern
emp_pattern = calculate_employee_work_pattern(base_pattern, emp_offset)
print(f"  Employee pattern: {emp_pattern}")

# Check a few dates
pattern_start_date_obj = datetime.fromisoformat(pattern_start_date).date()
test_dates = [
    datetime(2026, 5, 1).date(),
    datetime(2026, 5, 6).date(),
    datetime(2026, 5, 7).date(),
]

for test_date in test_dates:
    pattern_day = calculate_pattern_day(
        assignment_date=test_date,
        pattern_start_date=pattern_start_date_obj,
        employee_offset=0,  # Already rotated
        pattern_length=len(base_pattern),
        coverage_days=coverage_days
    )
    expected_shift = emp_pattern[pattern_day]
    print(f"  {test_date}: pattern_day={pattern_day}, expected={expected_shift}")
