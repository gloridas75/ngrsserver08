#!/usr/bin/env python3
"""
Analyze ICPMP Production Test Results
"""
import json
from pathlib import Path

def analyze_results():
    """Analyze the ICPMP production test results"""
    
    # Read files
    input_file = Path("input/requirements_simple.json")
    output_file = Path("output/icpmp_production_test.json")
    
    with open(input_file, 'r') as f:
        input_data = json.load(f)
    
    with open(output_file, 'r') as f:
        result = json.load(f)
    
    print("="*80)
    print("ICPMP PRODUCTION TEST SUMMARY")
    print("="*80)
    print(f"Generated: {result.get('generatedAt', 'Unknown')}")
    print(f"Processing Time: {result.get('meta', {}).get('processingTimeMs', 'Unknown')}ms")
    print()
    
    # 1. Total requirements
    input_reqs = input_data.get('requirements', [])
    output_reqs_by_id = {}
    recommendations = result.get('recommendations', [])
    
    for rec in recommendations:
        req_id = rec.get('requirementId')
        if req_id not in output_reqs_by_id:
            output_reqs_by_id[req_id] = []
        output_reqs_by_id[req_id].append(rec)
    
    print(f"1. Total requirements processed: {len(output_reqs_by_id)} (input: {len(input_reqs)})")
    
    if len(output_reqs_by_id) != len(input_reqs):
        print(f"   ⚠️  WARNING: Mismatch! Expected {len(input_reqs)}, got {len(output_reqs_by_id)}")
        missing = set(r['id'] for r in input_reqs) - set(output_reqs_by_id.keys())
        if missing:
            print(f"   Missing requirements: {', '.join(missing)}")
    print()
    
    # 2. Total employees (best patterns)
    total_employees = 0
    for req_id, alternatives in output_reqs_by_id.items():
        best = alternatives[0]  # First is always best
        total_employees += best['configuration']['employeesRequired']
    
    summary_total = result.get('summary', {}).get('totalEmployees', 'N/A')
    print(f"2. Total employees needed (best patterns): {total_employees}")
    print(f"   (Summary field shows: {summary_total})")
    print()
    
    # 3. Per-requirement analysis
    print("3. Per-requirement analysis:")
    print("-" * 80)
    
    all_have_5 = True
    shift_type_issues = []
    
    for req in input_reqs:
        req_id = req['id']
        req_name = req['name']
        expected_shifts = set(req.get('shiftTypes', []))
        
        if req_id not in output_reqs_by_id:
            print(f"\n{req_id} ({req_name}): ❌ NOT FOUND IN RESPONSE")
            all_have_5 = False
            continue
        
        alternatives = output_reqs_by_id[req_id]
        num_alternatives = len(alternatives)
        
        if num_alternatives != 5:
            all_have_5 = False
        
        # Get best pattern
        best = alternatives[0]
        config = best['configuration']
        coverage = best['coverage']
        
        pattern = config['workPattern']
        employees = config['employeesRequired']
        coverage_rate = coverage['expectedCoverageRate']
        
        # Extract shift types from pattern
        actual_shifts = set(pattern)
        
        # Check shift type filtering
        if actual_shifts != expected_shifts:
            shift_type_issues.append({
                'requirementId': req_id,
                'expected': sorted(expected_shifts),
                'actual': sorted(actual_shifts)
            })
        
        print(f"\n{req_id} ({req_name}):")
        print(f"  Alternatives: {num_alternatives} {'✓' if num_alternatives == 5 else '❌'}")
        print(f"  Best Pattern: {'-'.join(pattern)}")
        print(f"  Shift Types: {', '.join(sorted(actual_shifts))}")
        print(f"  Employee Count: {employees}")
        print(f"  Coverage Rate: {coverage_rate:.1f}%")
        
        # Show all alternatives
        if num_alternatives > 1:
            print(f"  All alternatives:")
            for i, alt in enumerate(alternatives, 1):
                alt_pattern = alt['configuration']['workPattern']
                alt_emp = alt['configuration']['employeesRequired']
                alt_cov = alt['coverage']['expectedCoverageRate']
                alt_shifts = set(alt_pattern)
                print(f"    #{i}: {'-'.join(alt_pattern)} | {alt_emp} emp | {alt_cov:.1f}% cov | Shifts: {','.join(sorted(alt_shifts))}")
    
    # 4. Validation: All have 5 alternatives
    print("\n" + "="*80)
    print("VALIDATION RESULTS")
    print("="*80)
    
    print(f"\n4. All requirements returned 5 alternatives: {'✓ YES' if all_have_5 else '❌ NO'}")
    if not all_have_5:
        print("   Issues:")
        for req_id, alternatives in output_reqs_by_id.items():
            if len(alternatives) != 5:
                print(f"   - {req_id}: {len(alternatives)} alternatives")
    
    # 5. Validation: Shift types filtering
    print(f"\n5. ShiftTypes filtering validation: {'✓ PASS' if not shift_type_issues else '❌ FAIL'}")
    
    if shift_type_issues:
        print("   Issues found:")
        for issue in shift_type_issues:
            print(f"   - {issue['requirementId']}: Expected {issue['expected']}, Got {issue['actual']}")
    else:
        print("   ✓ REQ_APO_DAY correctly filtered to D-only patterns")
        print("   ✓ Other requirements correctly filtered to N-only patterns")
    
    # Additional analysis
    print("\n" + "="*80)
    print("ADDITIONAL OBSERVATIONS")
    print("="*80)
    
    # Check if any CVSO requirements use wrong shift types
    for req in input_reqs:
        if 'CVSO' in req['id']:
            req_id = req['id']
            if req_id in output_reqs_by_id:
                alternatives = output_reqs_by_id[req_id]
                for alt in alternatives:
                    pattern = alt['configuration']['workPattern']
                    actual_shifts = set(pattern)
                    expected_shifts = set(req.get('shiftTypes', []))
                    if actual_shifts != expected_shifts:
                        print(f"\n⚠️  {req_id}: Shift type mismatch detected")
                        print(f"    Expected: {sorted(expected_shifts)}")
                        print(f"    Found patterns with: {sorted(actual_shifts)}")
                        break
    
    print("\n" + "="*80)

if __name__ == "__main__":
    analyze_results()
