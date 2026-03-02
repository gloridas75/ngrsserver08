#!/usr/bin/env python
"""
Reorder monthlyHourLimits to put specific rules before generic "All" rules
"""
import json

with open('input/RST-20260301-F9EA0EDE_Solver_Input.json', 'r') as f:
    data = json.load(f)

# Extract and reorder monthlyHourLimits
rules = data.get('monthlyHourLimits', [])

# Separate generic and specific rules
generic_rules = []
specific_rules = []

for rule in rules:
    applicable = rule.get('applicableTo', {})
    emp_type = applicable.get('employeeType', 'All')
    schemes = applicable.get('schemes', ['All'])
    products = applicable.get('productTypeIds', ['All'])
    
    # If ALL three are 'All', it's generic
    if emp_type == 'All' and 'All' in schemes and 'All' in products:
        generic_rules.append(rule)
    else:
        specific_rules.append(rule)

# Reorder: specific first, then generic
data['monthlyHourLimits'] = specific_rules + generic_rules

# Save
with open('input/RST-20260301-F9EA0EDE_Solver_Input.json', 'w') as f:
    json.dump(data, f, indent=2)

print('✓ Reordered monthlyHourLimits:')
print(f'  Specific rules: {len(specific_rules)}')
print(f'  Generic rules: {len(generic_rules)}')
print('\nNew order:')
for i, rule in enumerate(data['monthlyHourLimits'], 1):
    rule_id = rule.get('id', 'NO_ID')
    applicable = rule.get('applicableTo', {})
    emp_type = applicable.get('employeeType', 'All')
    schemes = applicable.get('schemes', ['All'])
    products = applicable.get('productTypeIds', ['All'])
    calc_method = rule.get('hourCalculationMethod', '')
    
    print(f'{i}. {rule_id}: {emp_type} + {schemes} + {products} ({calc_method})')
