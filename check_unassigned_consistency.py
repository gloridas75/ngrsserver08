#!/usr/bin/env python3
"""
Check UNASSIGNED slot consistency between assignments and employeeRoster
"""
import json
import sys

def check_unassigned_consistency(output_file):
    """Check if UNASSIGNED slots are consistent"""
    with open(output_file, 'r') as f:
        output = json.load(f)
    
    print("="*80)
    print(f"CHECKING: {output_file}")
    print("="*80)
    
    # Get UNASSIGNED from assignments array (check shiftCode, not status)
    unassigned_in_assignments = [a for a in output['assignments'] if a.get('shiftCode') == 'UNASSIGNED']
    
    # Get UNASSIGNED from employeeRoster
    unassigned_in_roster = []
    for emp in output['employeeRoster']:
        for day in emp['dailyStatus']:
            if day.get('status') == 'UNASSIGNED':
                unassigned_in_roster.append({
                    'employeeId': emp['employeeId'],
                    'date': day['date'],
                    'expectedShift': day.get('expectedShift'),
                    'reason': day.get('reason')
                })
    
    # Get summary counts
    summary_unassigned = output['rosterSummary']['byStatus'].get('UNASSIGNED', 0)
    
    print(f"\nUNASSIGNED COUNTS:")
    print(f"  assignments[] array: {len(unassigned_in_assignments)}")
    print(f"  employeeRoster.dailyStatus[]: {len(unassigned_in_roster)}")
    print(f"  rosterSummary.byStatus.UNASSIGNED: {summary_unassigned}")
    
    if unassigned_in_roster:
        print(f"\nSample UNASSIGNED entries from employeeRoster:")
        for i, entry in enumerate(unassigned_in_roster[:3]):
            print(f"  {i+1}. Employee {entry['employeeId']}, Date {entry['date']}")
            print(f"     Expected: {entry['expectedShift']}, Reason: {entry['reason']}")
    
    if unassigned_in_assignments:
        print(f"\nSample UNASSIGNED entries from assignments:")
        for i, entry in enumerate(unassigned_in_assignments[:3]):
            print(f"  {i+1}. Employee {entry.get('employeeId')}, Date {entry.get('date')}")
    
    # Check consistency
    print(f"\n{'='*80}")
    if len(unassigned_in_assignments) == len(unassigned_in_roster) == summary_unassigned:
        print("✅ CONSISTENT: UNASSIGNED counts match across all sections")
        return True
    else:
        print("❌ INCONSISTENT: UNASSIGNED counts DO NOT match")
        discrepancy = len(unassigned_in_roster) - len(unassigned_in_assignments)
        print(f"   Missing from assignments[]: {discrepancy}")
        return False

# Test with recent output
if __name__ == '__main__':
    test_files = [
        'output/output_clean.json',
        'output/regression_RST-20260113-C9FE1E08_Solver_Input_output.json',
        'RST-20260113-C9FE1E08_Solver_Output.json'
    ]
    
    print("\n" + "="*80)
    print("UNASSIGNED SLOT CONSISTENCY CHECK")
    print("="*80 + "\n")
    
    for test_file in test_files:
        try:
            check_unassigned_consistency(test_file)
            print()
        except FileNotFoundError:
            print(f"⚠️  File not found: {test_file}\n")
        except Exception as e:
            print(f"❌ Error checking {test_file}: {e}\n")
