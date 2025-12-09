#!/usr/bin/env python3
"""
Enhanced ICPMP Configuration Optimizer Test
Integrates new rotation preprocessing capabilities for better pattern recommendations.
"""

import json
from context.engine.config_optimizer import optimize_all_requirements, format_output_config
from context.engine.rotation_preprocessor import (
    extract_consolidated_patterns,
    simulate_pattern_filling
)
from datetime import datetime

# Test with real scenario
test_input = {
    "planningHorizon": {
        "startDate": "2026-03-01",
        "endDate": "2026-03-31"
    },
    "requirements": [
        {
            "id": "REQ_52_1_WEEKDAY",
            "name": "Weekday Coverage (Mon-Fri)",
            "productType": "APO",
            "rank": "SER",
            "scheme": "A",
            "shiftTypes": ["D"],
            "headcountPerShift": {"D": 10},
            "coverageDays": ["Mon", "Tue", "Wed", "Thu", "Fri"]
        },
        {
            "id": "REQ_53_1_FULLWEEK",
            "name": "Full Week Coverage (7 days)",
            "productType": "APO",
            "rank": "SER",
            "scheme": "A",
            "shiftTypes": ["D"],
            "headcountPerShift": {"D": 15},
            "coverageDays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        }
    ],
    "constraints": {
        "maxWeeklyNormalHours": 44,
        "maxMonthlyOTHours": 72,
        "maxConsecutiveWorkDays": 12,
        "minOffDaysPerWeek": 1
    },
    "shiftDefinitions": {
        "D": {
            "grossHours": 12.0,
            "lunchBreak": 1.0
        }
    }
}

print("="*100)
print("ENHANCED ICPMP TEST - Integration with Rotation Preprocessing")
print("="*100)
print()

# Run optimization
print("Running ICPMP optimization...")
result = optimize_all_requirements(
    test_input['requirements'],
    test_input['constraints'],
    test_input['planningHorizon'],
    shift_definitions=test_input.get('shiftDefinitions')
)

# Format output
formatted = format_output_config(result, test_input['requirements'])

print("\n" + "="*100)
print("ANALYSIS: PATTERN RECOMMENDATIONS VS COVERAGE REQUIREMENTS")
print("="*100)

for req in test_input['requirements']:
    req_id = req['id']
    coverage_days = req.get('coverageDays', [])
    coverage_length = len(coverage_days)
    
    print(f"\n{req_id}: {req['name']}")
    print(f"  Coverage: {', '.join(coverage_days)} ({coverage_length} days/week)")
    print(f"  Headcount Required: {req['headcountPerShift']}")
    
    if req_id in result['requirements']:
        configs = result['requirements'][req_id]
        best_config = configs[0]
        
        pattern = best_config['pattern']
        pattern_length = len(pattern)
        work_days = sum(1 for d in pattern if d != 'O')
        
        print(f"\n  BEST PATTERN RECOMMENDED:")
        print(f"    Pattern: {pattern} (length={pattern_length})")
        print(f"    Work days: {work_days}, Rest days: {pattern_length - work_days}")
        print(f"    Employees needed: {best_config['employeeCount']}")
        print(f"    Coverage rate: {best_config['coverage']['coverageRate']:.1f}%")
        
        # VALIDATION: Check if pattern length matches coverage
        if pattern_length != coverage_length and coverage_length < 7:
            print(f"\n  ⚠️  VALIDATION WARNING:")
            print(f"      Pattern length ({pattern_length}) != Coverage days ({coverage_length})")
            print(f"      Recommendation: Truncate pattern to {coverage_length} days")
            print(f"      Suggested pattern: {pattern[:coverage_length]}")
        
        # Show alternatives
        if len(configs) > 1:
            print(f"\n  ALTERNATIVES:")
            for i, alt_config in enumerate(configs[1:4], 2):  # Show top 3 alternatives
                alt_pattern = alt_config['pattern']
                alt_work = sum(1 for d in alt_pattern if d != 'O')
                print(f"    #{i}: {alt_pattern} "
                      f"({alt_work} work, {len(alt_pattern) - alt_work} rest) "
                      f"- {alt_config['employeeCount']} employees, "
                      f"{alt_config['coverage']['coverageRate']:.1f}% coverage")

print("\n" + "="*100)
print("IMPROVEMENT RECOMMENDATIONS")
print("="*100)

recommendations = []

# Check for pattern/coverage mismatches
for req in test_input['requirements']:
    req_id = req['id']
    coverage_days = req.get('coverageDays', [])
    coverage_length = len(coverage_days)
    
    if req_id in result['requirements']:
        best_pattern = result['requirements'][req_id][0]['pattern']
        pattern_length = len(best_pattern)
        
        if pattern_length != coverage_length and coverage_length < 7:
            recommendations.append({
                'requirement': req_id,
                'issue': 'Pattern length mismatch',
                'action': f'Add validation: pattern length should match coverage days ({coverage_length})',
                'priority': 'HIGH'
            })

# Integration with preprocessing
recommendations.append({
    'requirement': 'ALL',
    'issue': 'Static offset generation',
    'action': 'Integrate rotation_preprocessor.py for intelligent offset distribution',
    'priority': 'MEDIUM',
    'details': 'Use greedy sequential filling for better offset diversity'
})

recommendations.append({
    'requirement': 'ALL',
    'issue': 'No flexible employee handling',
    'action': 'Add offset=-1 option for truly flexible employees',
    'priority': 'HIGH',
    'details': 'Some employees may not fit any pattern perfectly'
})

recommendations.append({
    'requirement': 'ALL',
    'issue': 'Pattern suggestions ignore actual calendar',
    'action': 'Consider coverageDays when generating patterns',
    'priority': 'HIGH',
    'details': 'Mon-Fri coverage needs 5-day patterns, not 6-day'
})

for i, rec in enumerate(recommendations, 1):
    print(f"\n{i}. [{rec['priority']}] {rec['requirement']}: {rec['issue']}")
    print(f"   Action: {rec['action']}")
    if 'details' in rec:
        print(f"   Details: {rec['details']}")

print("\n" + "="*100)
print("INTEGRATION OPPORTUNITIES")
print("="*100)

integration_points = [
    {
        'component': 'Pattern Generation',
        'current': 'Fixed 6-day cycle with generic patterns',
        'enhancement': 'Dynamic cycle based on coverageDays (5 for Mon-Fri, 7 for full week)',
        'benefit': 'Eliminates pattern/coverage mismatches automatically'
    },
    {
        'component': 'Offset Distribution',
        'current': 'Simple modulo distribution: offsets = [i % pattern_length]',
        'enhancement': 'Use rotation_preprocessor.simulate_pattern_filling()',
        'benefit': 'Guarantees headcount coverage, identifies flexible employees'
    },
    {
        'component': 'Employee Count Calculation',
        'current': 'Theoretical minimum based on work ratio',
        'enhancement': 'Actual simulation with calendar awareness',
        'benefit': 'More accurate employee requirements'
    },
    {
        'component': 'Validation',
        'current': 'Basic feasibility checks',
        'enhancement': 'Add pattern length vs coverage days validation',
        'benefit': 'Catches configuration errors before solving'
    }
]

for i, point in enumerate(integration_points, 1):
    print(f"\n{i}. {point['component']}")
    print(f"   Current: {point['current']}")
    print(f"   Enhancement: {point['enhancement']}")
    print(f"   Benefit: {point['benefit']}")

# Save output
output_path = 'output/icpmp_enhanced_test.json'
with open(output_path, 'w') as f:
    json.dump(formatted, f, indent=2)

print(f"\n✅ Output saved to: {output_path}")
print("\n" + "="*100)
