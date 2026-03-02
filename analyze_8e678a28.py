import json
from datetime import datetime
from collections import defaultdict

with open('input/RST-20260301-8E678A28_Solver_Input.json', 'r') as f:
    input_data = json.load(f)

with open('input/RST-20260301-8E678A28_Solver_Output.json', 'r') as f:
    output_data = json.load(f)

print('='*80)
print('ISSUE ANALYSIS: RST-20260301-8E678A28')
print('='*80)

print('\n' + '='*80)
print('ISSUE 1: SCHEME A EMPLOYEE (30024914) - PATTERN ADHERENCE')
print('='*80)

# Get Scheme A employee info
sch_a_emp = next(e for e in input_data['employees'] if e['employeeId'] == '30024914')
print(f"\nEmployee 30024914: Scheme {sch_a_emp['scheme']}, APO, Local={sch_a_emp['local']}")
print(f"Expected Pattern: D-D-D-D-D-O (5 work days, 1 off day)")
print(f"Unavailability Days: {len(sch_a_emp['unavailability'])} days")
print(f"  Dates: {', '.join(sch_a_emp['unavailability'])}")

# Get Scheme A assignments
sch_a_assignments = [a for a in output_data['assignments'] 
                     if a.get('employeeId') == '30024914' and a.get('status') in ['ASSIGNED', 'OFF_DAY']]

print(f"\n{'Date':<12} {'Day':<4} {'Status':<12} {'Normal':<8} {'OT':<8}")
print('-'*50)

for assign in sorted(sch_a_assignments, key=lambda x: x['date']):
    date = assign['date']
    day = datetime.strptime(date, '%Y-%m-%d').strftime('%a')
    status = assign['status']
    normal = assign.get('hours', {}).get('normal', 0)
    ot = assign.get('hours', {}).get('ot', 0)
    print(f"{date:<12} {day:<4} {status:<12} {normal:<8.2f} {ot:<8.2f}")

work_days = sum(1 for a in sch_a_assignments if a.get('status') == 'ASSIGNED')
off_days = sum(1 for a in sch_a_assignments if a.get('status') == 'OFF_DAY')
print(f"\nActual Pattern: {work_days} work days, {off_days} off days")
print(f"Expected Pattern: 26 work days (5x5 + 1), 5 off days")
print(f"\n⚠️  ISSUE: Employee has {sch_a_emp['unavailability'].count} unavailability days which")
print(f"   breaks the pattern. Solver treats unavailable days as additional off-days.")

print('\n' + '='*80)
print('ISSUE 2: SCHEME B EMPLOYEE (30024360) - HOUR CALCULATION')
print('='*80)

# Get Scheme B employee info
sch_b_emp = next(e for e in input_data['employees'] if e['employeeId'] == '30024360')
print(f"\nEmployee 30024360: Scheme {sch_b_emp['scheme']}, APO, Local={sch_b_emp['local']}")
print(f"Expected Pattern: D-D-D-D-D-O (5 work days, 1 off day)")
print(f"Hour Calculation Method: weeklyThreshold (44h/work_days per week)")
print(f"  - When 5 work days: 44/5 = 8.8h normal per day")
print(f"  - When 6 work days: 44/6 = 7.33h normal per day")

# Get Scheme B assignments
sch_b_assignments = [a for a in output_data['assignments'] 
                     if a.get('employeeId') == '30024360' and a.get('status') == 'ASSIGNED']

# Analyze by calendar week
weekly_data = defaultdict(lambda: {'dates': [], 'work_days': 0, 'normals': []})

for assign in sch_b_assignments:
    date_obj = datetime.strptime(assign['date'], '%Y-%m-%d')
    # Calendar week (Sunday start)
    week_start = date_obj - datetime.timedelta(days=date_obj.weekday() + 1)
    if date_obj.weekday() == 6:  # Sunday
        week_start = date_obj
    week_key = week_start.strftime('%Y-%m-%d')
    
    weekly_data[week_key]['dates'].append(assign['date'])
    weekly_data[week_key]['work_days'] += 1
    normal = assign.get('hours', {}).get('normal', 0)
    weekly_data[week_key]['normals'].append(normal)

print(f"\n{'Week Start':<12} {'Work Days':<12} {'Avg Normal/Day':<16} {'Expected':<16} {'Status':<10}")
print('-'*75)

for week_start in sorted(weekly_data.keys()):
    data = weekly_data[week_start]
    work_days = data['work_days']
    avg_normal = sum(data['normals']) / len(data['normals']) if data['normals'] else 0
    expected = 44.0 / work_days if work_days > 0 else 0
    status = '✓ OK' if abs(avg_normal - expected) < 0.5 else '✗ WRONG'
    print(f"{week_start:<12} {work_days:<12} {avg_normal:<16.2f} {expected:<16.2f} {status:<10}")

# Get monthly hour limits for Scheme B APO
sch_b_limit = None
for limit in input_data['monthlyHourLimits']:
    applicable_to = limit.get('applicableTo', {})
    if (limit.get('hourCalculationMethod') == 'weeklyThreshold' and 
        'B' in applicable_to.get('schemes', []) and
        'APO' in applicable_to.get('productTypeIds', [])):
        sch_b_limit = limit
        break

if sch_b_limit:
    print(f"\nConfigured Rule: {sch_b_limit['id']}")
    print(f"  Method: {sch_b_limit['hourCalculationMethod']}")
    print(f"  For 31 days: {sch_b_limit['valuesByMonthLength']['31']}")
else:
    print("\n⚠️  NO MATCHING RULE FOUND for Scheme B APO!")
    print("  This could explain the incorrect hour calculations.")

# Show sample day details
print(f"\nSample Day Analysis:")
print(f"{'Date':<12} {'Day':<4} {'Normal':<8} {'OT':<8} {'Gross':<8}")
print('-'*45)
for assign in sch_b_assignments[:10]:
    date = assign['date']
    day = datetime.strptime(date, '%Y-%m-%d').strftime('%a')
    normal = assign.get('hours', {}).get('normal', 0)
    ot = assign.get('hours', {}).get('ot', 0)
    gross = assign.get('hours', {}).get('gross', 0)
    print(f"{date:<12} {day:<4} {normal:<8.2f} {ot:<8.2f} {gross:<8.2f}")

print('\n' + '='*80)
print('ROOT CAUSE SUMMARY')
print('='*80)
print("""
ISSUE 1: Scheme A Pattern Deviation
- Root Cause: Employee 30024914 has 8 unavailability days
- Effect: Solver treats unavailable days as forced off-days
- Result: Pattern becomes irregular with 23 work days + 8 off days (instead of 26+5)
- Fix Needed: Either remove unavailability OR accept irregular pattern

ISSUE 2: Scheme B Normal Hour Calculation
- Root Cause: Hour calculation NOT following weeklyThreshold method correctly
- Expected: 44h / work_days_in_week (8.8h for 5 days, 7.33h for 6 days)
- Fix Needed: Check if pattern_work_days is being passed correctly to 
  calculate_mom_compliant_hours() in output_builder.py
""")
