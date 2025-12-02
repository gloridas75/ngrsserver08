#!/usr/bin/env python3
"""
Quick verification script to check input file configuration.
Run this on the production server to diagnose issues.

Usage: python3 verify_input.py <input_file.json>
"""

import json
import sys
from collections import Counter

def verify_input(filepath):
    print("=" * 80)
    print(f"VERIFYING: {filepath}")
    print("=" * 80)
    
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ ERROR loading file: {e}")
        return False
    
    print(f"\n✓ File loaded successfully")
    print(f"\nConfiguration:")
    print(f"  Schema: {data.get('schemaVersion', 'MISSING')}")
    print(f"  Planning: {data['planningHorizon']['startDate']} to {data['planningHorizon']['endDate']}")
    print(f"  fixedRotationOffset: {data.get('fixedRotationOffset', 'MISSING')}")
    
    req = data['demandItems'][0]['requirements'][0]
    print(f"  Headcount: {req['headcount']}")
    print(f"  Pattern: {req['workPattern']}")
    
    employees = data['employees']
    print(f"  Total employees: {len(employees)}")
    print(f"  Max to use: {data['solverConfig'].get('maxEmployeesToUse', 'unlimited')}")
    
    # Check rotation offsets
    print(f"\nRotation Offset Distribution:")
    offsets = [emp.get('rotationOffset', -1) for emp in employees]
    offset_dist = Counter(offsets)
    
    for offset in sorted(offset_dist.keys()):
        count = offset_dist[offset]
        print(f"  Offset {offset}: {count} employees ({count/len(employees)*100:.1f}%)")
    
    # Validation checks
    print(f"\nValidation Checks:")
    issues = []
    
    if not data.get('fixedRotationOffset'):
        issues.append("⚠️  fixedRotationOffset is false - solver will optimize offsets (may not work with O-pattern days)")
    else:
        print("  ✓ fixedRotationOffset is true")
    
    if len(offset_dist) == 1 and 0 in offset_dist:
        issues.append("❌ All employees have offset 0 - need staggered offsets (0-5) for D-D-N-N-O-O pattern!")
    elif len(offset_dist) >= 6:
        print(f"  ✓ Offsets are staggered across {len(offset_dist)} values")
    else:
        issues.append(f"⚠️  Only {len(offset_dist)} different offset values - recommend using all 0-5 for 6-day pattern")
    
    if 'O' in req['workPattern']:
        if not data.get('fixedRotationOffset') or len(offset_dist) == 1:
            issues.append("❌ CRITICAL: O-pattern days require fixedRotationOffset=true AND staggered offsets!")
        else:
            print("  ✓ Configuration supports O-pattern days")
    
    if issues:
        print("\n" + "=" * 80)
        print("ISSUES FOUND:")
        print("=" * 80)
        for issue in issues:
            print(f"  {issue}")
        return False
    else:
        print("\n" + "=" * 80)
        print("✓ ALL CHECKS PASSED - Configuration looks good!")
        print("=" * 80)
        return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 verify_input.py <input_file.json>")
        print("\nExample:")
        print("  python3 verify_input.py input/input_v0.8_0212_1300.json")
        sys.exit(1)
    
    success = verify_input(sys.argv[1])
    sys.exit(0 if success else 1)
