"""Debug pattern calculation for March 21 (PH)."""
import json
from datetime import datetime

with open('input/RST-20260226-43BF25BE_Solver_Input (1).json') as f:
    data = json.load(f)

demands = data['demandItems']
reqs = demands[0]['requirements']
base_pattern = reqs[0].get('workPattern', [])
pattern_start_date = demands[0].get('shiftStartDate')
coverage_days = reqs[0].get('coverageDays', None)

print(f'Pattern: {base_pattern}')
print(f'Pattern start: {pattern_start_date}')
print(f'Coverage days: {coverage_days}')

employees = data.get('employees', [])
for emp in employees:
    print(f'Employee {emp["employeeId"]}: offset={emp.get("rotationOffset", 0)}')

from context.engine.solver_engine import calculate_pattern_day, calculate_employee_work_pattern

target = datetime(2026, 3, 21).date()
start = datetime.fromisoformat(pattern_start_date).date()
pattern_length = len(base_pattern)

print(f'\nMarch 21, 2026 pattern calculation:')
for emp in employees:
    emp_id = emp['employeeId']
    emp_offset = emp.get('rotationOffset', 0)
    emp_pattern = calculate_employee_work_pattern(base_pattern, emp_offset)
    
    pattern_day = calculate_pattern_day(
        assignment_date=target,
        pattern_start_date=start,
        employee_offset=0,
        pattern_length=pattern_length,
        coverage_days=coverage_days
    )
    expected_shift = emp_pattern[pattern_day]
    print(f'  {emp_id}: offset={emp_offset}, pattern={emp_pattern}, day_idx={pattern_day}, shift={expected_shift}')

# Also check what optimized_offsets would be (solver may stagger)
print(f'\nNote: The solver may use optimized offsets (staggered).')
print(f'If offset changes, the pattern rotates and March 21 could map to D instead of O.')
