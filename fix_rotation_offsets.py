#!/usr/bin/env python3
"""
Fix rotation offsets to stagger employee rest days across the week.
This prevents all employees from resting on the same days.
"""

import json
import sys

def fix_rotation_offsets(input_file, output_file=None):
    """
    Distribute rotation offsets across 0-6 to stagger rest days.
    
    Args:
        input_file: Path to input JSON
        output_file: Path to save fixed JSON (default: overwrites input)
    """
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    employees = data.get('employees', [])
    num_employees = len(employees)
    
    print(f"Fixing rotation offsets for {num_employees} employees...")
    print(f"Before: All offsets = {employees[0]['rotationOffset'] if employees else 'N/A'}")
    
    # Distribute offsets evenly across 0-6 (7-day cycle)
    for i, emp in enumerate(employees):
        emp['rotationOffset'] = i % 7
    
    # Show distribution
    offset_counts = {}
    for emp in employees:
        offset = emp['rotationOffset']
        offset_counts[offset] = offset_counts.get(offset, 0) + 1
    
    print(f"After distribution:")
    for offset in range(7):
        count = offset_counts.get(offset, 0)
        print(f"  Offset {offset}: {count} employees")
    
    # Save
    if output_file is None:
        output_file = input_file
    
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\n✓ Fixed input saved to: {output_file}")
    print("\nWhat this fixes:")
    print("  - Employees now rest on different days of the week")
    print("  - Example: Offset 0 rests on Thu-Fri, Offset 1 rests on Fri-Sat, etc.")
    print("  - Coverage gaps eliminated")
    
    return data

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python fix_rotation_offsets.py <input_file> [output_file]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    fix_rotation_offsets(input_file, output_file)
