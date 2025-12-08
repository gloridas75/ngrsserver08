#!/usr/bin/env python3
"""
Analyze remaining 42 unassigned slots - specifically the Friday clustering.

Results show 90% of unassigned slots are on Fridays:
- 2026-03-06: 12 slots
- 2026-03-13: 5 slots
- 2026-03-20: 16 slots
- 2026-03-27: 5 slots
"""

import json
from datetime import datetime
from collections import defaultdict

def analyze_unassigned_slots():
    """Analyze the unassigned slots by date, shift, demand, and pattern."""
    
    # Load the latest output
    with open('output/output_1206_1953.json', 'r') as f:
        result = json.load(f)
    
    # Load input to get pattern info
    with open('input/AUTO-20251206-233E7006_Solver_Input.json', 'r') as f:
        input_data = json.load(f)
    
    print("\n" + "="*100)
    print("UNASSIGNED SLOTS ANALYSIS - Friday Clustering Investigation")
    print("="*100)
    
    # Build demand/requirement lookup
    demand_map = {}
    for demand in input_data['demandItems']:
        demand_id = demand['demandId']
        for req in demand.get('requirements', []):
            req_id = req['requirementId']
            demand_map[req_id] = {
                'demandId': demand_id,
                'workPattern': req.get('workPattern', []),
                'headcount': req.get('headcount', 0),
                'productType': req.get('productTypeId', 'N/A'),
                'rank': req.get('rankId', 'N/A')
            }
        for shift in demand.get('shifts', []):
            shift_id = shift.get('demandShiftId', 'unknown')
            coverage_days = shift.get('coverageDays', [])
            demand_map[f"shift_{shift_id}"] = {
                'coverageDays': coverage_days
            }
    
    # Collect unassigned slots
    unassigned_info = result.get('scoreBreakdown', {}).get('unassignedSlots', {})
    unassigned_slots = unassigned_info.get('slots', [])
    
    print(f"\nTotal Unassigned: {len(unassigned_slots)}")
    print(f"Total Slots: {unassigned_info['total']}")
    print(f"Coverage: {(1 - unassigned_info['count']/unassigned_info['total'])*100:.1f}%")
    
    # Group by date
    by_date = defaultdict(list)
    for slot in unassigned_slots:
        date_str = slot['date']
        by_date[date_str].append(slot)
    
    print(f"\n{'='*100}")
    print("UNASSIGNED SLOTS BY DATE")
    print(f"{'='*100}")
    
    friday_total = 0
    other_total = 0
    
    for date_str in sorted(by_date.keys()):
        slots = by_date[date_str]
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        weekday = date_obj.strftime('%A')
        
        is_friday = (weekday == 'Friday')
        if is_friday:
            friday_total += len(slots)
        else:
            other_total += len(slots)
        
        # Group by requirement
        by_req = defaultdict(list)
        for slot in slots:
            req_id = slot.get('requirementId', 'unknown')
            by_req[req_id].append(slot)
        
        print(f"\n{date_str} ({weekday}) - {len(slots)} unassigned {'🔴 FRIDAY' if is_friday else ''}")
        
        for req_id, req_slots in by_req.items():
            info = demand_map.get(req_id, {})
            pattern = info.get('workPattern', [])
            headcount = info.get('headcount', 0)
            
            # Show shift breakdown
            shift_counts = defaultdict(int)
            for slot in req_slots:
                shift_counts[slot.get('shiftCode', 'N/A')] += 1
            
            shift_details = ', '.join([f"{shift}:{count}" for shift, count in shift_counts.items()])
            
            print(f"  Req {req_id}: {len(req_slots)} slots ({shift_details})")
            print(f"    Pattern: {pattern} (length={len(pattern)})")
            print(f"    Headcount: {headcount}")
            print(f"    Product: {info.get('productType', 'N/A')}, Rank: {info.get('rank', 'N/A')}")
    
    print(f"\n{'='*100}")
    print("FRIDAY CLUSTERING SUMMARY")
    print(f"{'='*100}")
    print(f"Friday unassigned: {friday_total} ({friday_total/len(unassigned_slots)*100:.1f}%)")
    print(f"Other days unassigned: {other_total} ({other_total/len(unassigned_slots)*100:.1f}%)")
    
    # Pattern analysis
    print(f"\n{'='*100}")
    print("PATTERN ANALYSIS")
    print(f"{'='*100}")
    
    by_pattern = defaultdict(int)
    for slot in unassigned_slots:
        req_id = slot.get('requirementId', 'unknown')
        info = demand_map.get(req_id, {})
        pattern = tuple(info.get('workPattern', []))
        by_pattern[pattern] += 1
    
    for pattern, count in sorted(by_pattern.items(), key=lambda x: x[1], reverse=True):
        print(f"Pattern {list(pattern)}: {count} unassigned slots")
    
    # Shift analysis
    print(f"\n{'='*100}")
    print("SHIFT CODE ANALYSIS")
    print(f"{'='*100}")
    
    by_shift = defaultdict(int)
    for slot in unassigned_slots:
        shift = slot.get('shiftCode', 'N/A')
        by_shift[shift] += 1
    
    for shift, count in sorted(by_shift.items(), key=lambda x: x[1], reverse=True):
        print(f"Shift {shift}: {count} unassigned slots")
    
    # Employee utilization
    print(f"\n{'='*100}")
    print("EMPLOYEE UTILIZATION")
    print(f"{'='*100}")
    
    employees = input_data['employees']
    print(f"Total employees: {len(employees)}")
    
    # Check offset distribution
    offset_counts = defaultdict(int)
    flexible_count = 0
    for emp in employees:
        offset = emp.get('rotationOffset', 0)
        if offset == -1:
            flexible_count += 1
        offset_counts[offset] += 1
    
    print(f"\nRotation Offset Distribution:")
    for offset in sorted(offset_counts.keys()):
        count = offset_counts[offset]
        print(f"  Offset {offset}: {count} employees")
    
    print(f"\nFlexible employees (offset=-1): {flexible_count} ({flexible_count/len(employees)*100:.1f}%)")
    print(f"Pattern-following employees: {len(employees) - flexible_count} ({(len(employees) - flexible_count)/len(employees)*100:.1f}%)")
    
    # Hypothesis: Friday is day 4 (0-indexed) in 5-day pattern ['D','D','D','O','O']
    # Employees with offset=4 would rest on Friday
    print(f"\n{'='*100}")
    print("FRIDAY HYPOTHESIS")
    print(f"{'='*100}")
    print("Pattern 1 (Mon-Fri): ['D','D','D','O','O']")
    print("  Day 0 (Mon): D")
    print("  Day 1 (Tue): D")
    print("  Day 2 (Wed): D")
    print("  Day 3 (Thu): O")
    print("  Day 4 (Fri): O  <-- FRIDAY IS REST DAY")
    print("\nEmployees with offset=3 or offset=4 would be OFF on Thursday or Friday")
    print("This explains Friday clustering!")
    
    offset_3_4 = sum(1 for emp in employees if emp.get('rotationOffset', 0) in [3, 4])
    print(f"\nEmployees with offset=3 or 4: {offset_3_4}")
    print(f"Expected employees available for Friday Pattern 1: ~{len(employees) - flexible_count - offset_3_4}")


if __name__ == '__main__':
    analyze_unassigned_slots()
