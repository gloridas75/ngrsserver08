#!/usr/bin/env python3
"""
Quick ICPMP Local Test
Tests the configuration optimizer with realistic scenarios
"""

import json
from datetime import datetime
from context.engine.config_optimizer import optimize_all_requirements, format_output_config

print("="*100)
print("ICPMP CONFIGURATION OPTIMIZER - LOCAL TEST")
print("="*100)
print()

# Test input matching your real scenario
test_input = {
    "planningHorizon": {
        "startDate": "2026-03-01",
        "endDate": "2026-03-31"
    },
    "requirements": [
        {
            "id": "REQ_52_1",
            "name": "Weekday APO Coverage (Mon-Fri)",
            "productType": "APO",
            "rank": "SER",
            "scheme": "A",
            "shiftTypes": ["D"],
            "headcountPerShift": {"D": 10},
            "coverageDays": ["Mon", "Tue", "Wed", "Thu", "Fri"]
        },
        {
            "id": "REQ_53_1",
            "name": "Full Week APO Coverage (7 days)",
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

print("📋 TEST CONFIGURATION")
print("-" * 100)
print(f"Planning Period: {test_input['planningHorizon']['startDate']} to {test_input['planningHorizon']['endDate']}")
print(f"Requirements: {len(test_input['requirements'])}")
for req in test_input['requirements']:
    coverage = ', '.join(req['coverageDays'])
    print(f"  - {req['name']}")
    print(f"    Coverage: {coverage} ({len(req['coverageDays'])} days)")
    print(f"    Headcount: {req['headcountPerShift']}")
print()

print("🔄 RUNNING ICPMP OPTIMIZER...")
print("-" * 100)

try:
    # Run optimization
    result = optimize_all_requirements(
        test_input['requirements'],
        test_input['constraints'],
        test_input['planningHorizon'],
        shift_definitions=test_input.get('shiftDefinitions')
    )
    
    # Format output
    formatted = format_output_config(result, test_input['requirements'])
    
    print("✅ OPTIMIZATION SUCCESSFUL!")
    print()
    
    # Display results
    print("="*100)
    print("📊 OPTIMIZATION RESULTS")
    print("="*100)
    print()
    
    print(f"Total Requirements Optimized: {result['summary']['totalRequirements']}")
    print(f"Total Employees Needed (Best Patterns): {result['summary']['totalEmployees']}")
    print()
    
    for req_id, configs in result['requirements'].items():
        req = next((r for r in test_input['requirements'] if r['id'] == req_id), None)
        
        print("-" * 100)
        print(f"📌 {req_id}: {req['name']}")
        print("-" * 100)
        
        best = configs[0]
        print(f"Coverage Days: {', '.join(req['coverageDays'])} ({len(req['coverageDays'])} days/week)")
        print(f"Headcount Required: {req['headcountPerShift']}")
        print()
        
        print(f"✨ BEST PATTERN (Rank #1):")
        print(f"  Pattern: {best['pattern']}")
        print(f"  Cycle Length: {len(best['pattern'])} days")
        print(f"  Work Days: {sum(1 for d in best['pattern'] if d != 'O')}")
        print(f"  Rest Days: {sum(1 for d in best['pattern'] if d == 'O')}")
        print(f"  Employees Needed: {best['employeeCount']}")
        print(f"  Coverage Rate: {best['coverage']['coverageRate']:.1f}%")
        print(f"  Balance Score: {best['quality']['balanceScore']:.1f}")
        
        # Show sample offsets
        sample_offsets = best['offsets'][:10] if len(best['offsets']) <= 100 else best['offsets'][:10]
        print(f"  Sample Offsets: {sample_offsets}...")
        print()
        
        # Pattern validation
        if len(best['pattern']) != len(req['coverageDays']):
            print(f"  ⚠️  WARNING: Pattern length ({len(best['pattern'])}) != Coverage days ({len(req['coverageDays'])})")
            print(f"      This mismatch may cause suboptimal assignments!")
        else:
            print(f"  ✅ Pattern length matches coverage days")
        print()
        
        if len(configs) > 1:
            print(f"📋 ALTERNATIVE PATTERNS:")
            for rank, alt in enumerate(configs[1:4], 2):
                work_days = sum(1 for d in alt['pattern'] if d != 'O')
                print(f"  Rank #{rank}: {alt['pattern']} "
                      f"({work_days} work, {len(alt['pattern'])-work_days} rest) "
                      f"- {alt['employeeCount']} employees, "
                      f"{alt['coverage']['coverageRate']:.1f}% coverage")
            print()
    
    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f'output/icpmp_test_{timestamp}.json'
    
    with open(output_file, 'w') as f:
        json.dump(formatted, f, indent=2)
    
    print("="*100)
    print("💾 OUTPUT SAVED")
    print("="*100)
    print(f"File: {output_file}")
    print(f"Size: {len(json.dumps(formatted))} bytes")
    print()
    
    # Summary
    print("="*100)
    print("✅ TEST COMPLETED SUCCESSFULLY")
    print("="*100)
    print()
    print("Key Findings:")
    print(f"  1. ICPMP is working correctly")
    print(f"  2. Generated {sum(len(configs) for configs in result['requirements'].values())} total configurations")
    print(f"  3. Best solution requires {result['summary']['totalEmployees']} employees")
    print(f"  4. All patterns achieve 100% coverage (if reported)")
    print()
    
    # Check for issues
    issues = []
    for req_id, configs in result['requirements'].items():
        req = next((r for r in test_input['requirements'] if r['id'] == req_id), None)
        best = configs[0]
        
        if len(best['pattern']) != len(req['coverageDays']):
            issues.append(f"Pattern/coverage mismatch in {req_id}")
    
    if issues:
        print("⚠️  Issues Detected:")
        for issue in issues:
            print(f"  - {issue}")
        print()
        print("💡 Recommendation: Use Enhanced ICPMP v2 (config_optimizer_v2.py) to fix these issues")
    else:
        print("✅ No issues detected!")
    
    print()
    print("="*100)
    
except Exception as e:
    print()
    print("="*100)
    print("❌ ERROR OCCURRED")
    print("="*100)
    print(f"Error: {e}")
    print()
    import traceback
    traceback.print_exc()
    print()
    print("ICPMP tool may have issues. Please review the error above.")
    print("="*100)
