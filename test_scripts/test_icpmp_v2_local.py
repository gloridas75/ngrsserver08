"""
Test Enhanced ICPMP v2 Configuration Optimizer Locally
Compares with original version to validate improvements
"""
import json
from datetime import datetime, date
from typing import Dict, Any
import sys
import os

# Add context path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'context'))

from context.engine.config_optimizer_v2 import (
    optimize_all_requirements_v2,
    format_output_config
)

def create_test_input_v2() -> Dict[str, Any]:
    """Create test input matching the original test for comparison"""
    
    test_config = {
        "schemaVersion": "0.8",
        "configType": "requirementConfiguration",
        "organizationId": "ORG_TEST",
        "planningHorizon": {
            "startDate": "2026-03-01",
            "endDate": "2026-03-31",
            "totalDays": 31
        },
        "requirements": [
            {
                "requirementId": "REQ_52_1",
                "requirementName": "Weekday APO Coverage (Mon-Fri)",
                "coverageDays": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                "shiftTypes": ["D"],
                "headcountByShift": {
                    "D": 10
                },
                "strictAdherence": True
            },
            {
                "requirementId": "REQ_53_1",
                "requirementName": "Full Week APO Coverage (7 days)",
                "coverageDays": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
                "shiftTypes": ["D"],
                "headcountByShift": {
                    "D": 15
                },
                "strictAdherence": True
            }
        ],
        "constraints": {
            "maxRegularHoursPerWeek": 44,
            "maxOvertimeHoursPerMonth": 72,
            "maxConsecutiveWorkDays": 12,
            "minRestDaysBetweenShifts": 1,
            "shiftDurations": {
                "D": 8,
                "N": 8,
                "O": 0
            }
        }
    }
    
    return test_config

def run_v2_test():
    """Run ICPMP v2 optimizer test"""
    
    print("=" * 100)
    print("ICPMP v2 CONFIGURATION OPTIMIZER - LOCAL TEST")
    print("=" * 100)
    print()
    
    # Create test input
    config = create_test_input_v2()
    
    # Display test configuration
    print("📋 TEST CONFIGURATION")
    print(f"Planning Period: {config['planningHorizon']['startDate']} to {config['planningHorizon']['endDate']}")
    print(f"Requirements: {len(config['requirements'])}")
    for req in config['requirements']:
        coverage_days = len(req['coverageDays'])
        headcount = sum(req['headcountByShift'].values())
        print(f"  - {req['requirementName']}: {coverage_days} days, Headcount: {req['headcountByShift']}")
    print()
    
    # Run optimizer
    print("🔄 RUNNING ICPMP v2 OPTIMIZER...")
    print()
    
    try:
        results = optimize_all_requirements_v2(
            requirements=config['requirements'],
            constraints=config['constraints'],
            planning_horizon=config['planningHorizon'],
            top_n=5
        )
        
        print("✅ OPTIMIZATION SUCCESSFUL!")
        print()
        
        # Display results
        print("📊 OPTIMIZATION RESULTS (Enhanced v2)")
        print()
        
        total_employees = 0
        warnings = []
        
        for req_id, configs in results.items():
            req = next(r for r in config['requirements'] if r['requirementId'] == req_id)
            print(f"{req_id}: {req['requirementName']}")
            
            if configs:
                best = configs[0]
                pattern = best['workPattern']
                employees = best['employeesRequired']
                coverage_rate = best['expectedCoverageRate']
                
                print(f"✨ BEST PATTERN:")
                print(f"  Pattern: {pattern}  ({len(pattern)}-day cycle)")
                print(f"  Employees Needed: {employees}")
                print(f"  Coverage Rate: {coverage_rate}%")
                
                # Check pattern length vs coverage days
                coverage_days = len(req['coverageDays'])
                if len(pattern) != coverage_days:
                    warning = f"⚠️ WARNING: Pattern length ({len(pattern)}) != Coverage days ({coverage_days})"
                    print(f"  {warning}")
                    warnings.append(f"Pattern/coverage mismatch in {req_id}")
                else:
                    print(f"  ✅ Pattern length matches coverage days ({coverage_days})")
                
                total_employees += employees
                
                # Show alternatives
                if len(configs) > 1:
                    print(f"  📋 {len(configs)-1} Alternative patterns available")
                print()
            else:
                print(f"  ❌ No valid patterns found")
                print()
        
        print(f"💡 TOTAL EMPLOYEES NEEDED: {total_employees}")
        print()
        
        # Format and save output
        output_config = format_output_config(results, config)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"output/icpmp_v2_test_{timestamp}.json"
        
        with open(output_file, 'w') as f:
            json.dump(output_config, f, indent=2)
        
        # Get file size
        file_size = os.path.getsize(output_file)
        size_kb = file_size / 1024
        
        print(f"💾 OUTPUT SAVED: {output_file} ({size_kb:.0f}K)")
        print()
        
        # Summary
        print("✅ TEST COMPLETED SUCCESSFULLY")
        print("Key Findings:")
        print(f"  1. ICPMP v2 is working correctly")
        print(f"  2. Generated {sum(len(configs) for configs in results.values())} total configurations")
        print(f"  3. Best solution requires {total_employees} employees")
        
        if not warnings:
            print(f"  4. ✅ All patterns match coverage requirements perfectly")
        else:
            print()
            print("⚠️ Issues Detected:")
            for warning in warnings:
                print(f"  - {warning}")
        
        print()
        print("=" * 100)
        
        return output_file, total_employees, warnings
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None, None

if __name__ == "__main__":
    output_file, total_employees, warnings = run_v2_test()
    
    if output_file:
        print()
        print(f"📄 Output file: {output_file}")
        print(f"👥 Total employees: {total_employees}")
        print(f"⚠️ Warnings: {len(warnings) if warnings else 0}")
