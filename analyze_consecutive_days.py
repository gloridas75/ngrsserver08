#!/usr/bin/env python3
"""
Analyze consecutive work days for each employee in solver output.
"""

import json
from datetime import datetime, timedelta
from collections import defaultdict

def parse_date(date_str):
    """Parse date string to datetime."""
    return datetime.strptime(date_str, "%Y-%m-%d")

def find_consecutive_sequences(dates):
    """Find all consecutive work day sequences."""
    if not dates:
        return []
    
    sorted_dates = sorted([parse_date(d) for d in dates])
    sequences = []
    current_sequence = [sorted_dates[0]]
    
    for i in range(1, len(sorted_dates)):
        if (sorted_dates[i] - current_sequence[-1]).days == 1:
            # Consecutive day
            current_sequence.append(sorted_dates[i])
        else:
            # Gap - save current sequence and start new one
            sequences.append(current_sequence)
            current_sequence = [sorted_dates[i]]
    
    # Don't forget the last sequence
    sequences.append(current_sequence)
    
    return sequences

def analyze_output(filename):
    """Analyze solver output for consecutive work patterns."""
    with open(filename, 'r') as f:
        data = json.load(f)
    
    # Group assignments by employee
    employee_dates = defaultdict(list)
    for assignment in data['assignments']:
        employee_dates[assignment['employeeId']].append(assignment['date'])
    
    print("=" * 80)
    print("CONSECUTIVE WORK DAY ANALYSIS")
    print("=" * 80)
    print()
    
    max_consecutive_overall = 0
    max_consecutive_employee = None
    
    for emp_id in sorted(employee_dates.keys()):
        dates = employee_dates[emp_id]
        sequences = find_consecutive_sequences(dates)
        
        # Find longest sequence
        max_length = max(len(seq) for seq in sequences)
        max_seq = max(sequences, key=len)
        
        if max_length > max_consecutive_overall:
            max_consecutive_overall = max_length
            max_consecutive_employee = emp_id
        
        # Get employee details
        emp_roster = next((e for e in data['employeeRoster'] if e['employeeId'] == emp_id), None)
        offset = emp_roster['rotationOffset'] if emp_roster else 'N/A'
        
        print(f"Employee: {emp_id} | Offset: {offset}")
        print(f"  Total work days: {len(dates)}")
        print(f"  Max consecutive: {max_length} days")
        print(f"  Longest sequence: {max_seq[0].strftime('%Y-%m-%d')} to {max_seq[-1].strftime('%Y-%m-%d')}")
        
        # Show all sequences >= 4 days
        long_sequences = [s for s in sequences if len(s) >= 4]
        if long_sequences:
            print(f"  Sequences >= 4 days:")
            for seq in long_sequences:
                print(f"    {len(seq)} days: {seq[0].strftime('%Y-%m-%d')} to {seq[-1].strftime('%Y-%m-%d')}")
        
        print()
    
    print("=" * 80)
    print(f"SUMMARY")
    print("=" * 80)
    print(f"Maximum consecutive work days: {max_consecutive_overall} days")
    print(f"Employee with max consecutive: {max_consecutive_employee}")
    print()
    
    # Check if any employee worked 6 consecutive days
    if max_consecutive_overall >= 6:
        print("✓ At least one employee worked 6+ consecutive days")
    else:
        print("✗ NO employee worked 6 consecutive days")
        print("  This is unexpected for DDDDDOD pattern!")

if __name__ == '__main__':
    analyze_output('/Users/glori/Downloads/solver_output_sync.json')
