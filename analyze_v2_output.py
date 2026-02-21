#!/usr/bin/env python3
"""Analyze v2 output file."""
import json

with open('output/v2_RST-20260206-2013B17E_Output.json') as f:
    d = json.load(f)

print('=== V2 OUTPUT SUMMARY ===')
print(f'Status: {d.get("solverStatus")}')
print(f'Schema Version: {d.get("schemaVersion")}')
print(f'Total Assignments: {len(d.get("assignments", []))}')

# Check meta for v2 flags
meta = d.get('meta', {})
print(f'\nMeta Info:')
print(f'  API Version: {meta.get("apiVersion", "N/A")}')
print(f'  Used Daily Headcount: {meta.get("usedDailyHeadcount", "N/A")}')
print(f'  Used V2 Slot Builder: {meta.get("usedV2SlotBuilder", "N/A")}')

# Check if assignments have dayType
assignments = d.get('assignments', [])
if assignments:
    sample = assignments[0]
    print(f'\nSample Assignment:')
    print(f'  Employee: {sample.get("employeeId")}')
    print(f'  Date: {sample.get("date")}')
    print(f'  Shift: {sample.get("shiftCode")}')
    print(f'  Day Type: {sample.get("dayType", "MISSING")}')

# Check dailyCoverage
coverage = d.get('dailyCoverage', [])
print(f'\nDaily Coverage Entries: {len(coverage)}')
if coverage:
    # Show sample by dayType
    by_type = {}
    for c in coverage:
        dt = c.get('dayType', 'Normal')
        by_type[dt] = by_type.get(dt, 0) + 1
    print(f'  By Day Type: {by_type}')
    
    # Show first PH if any
    phs = [c for c in coverage if c.get('dayType') == 'PublicHoliday']
    if phs:
        print(f'  Sample PH: {phs[0]}')
