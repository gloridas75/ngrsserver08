import subprocess

constraints = [
    'C1_mom_daily_hours',
    'C2_mom_weekly_hours', 
    'C3_consecutive_days',
    'C4_rest_period',
    'C5_offday_rules',
    'C6_parttimer_limits',
    'C7_license_validity',
    'C8_provisional_license',
    'C9_gender_balance',
    'C10_skill_role_match',
    'C11_rank_product_match',
    'C12_team_completeness',
    'C13_regulatory_fee_capture',
    'C15_qualification_expiry_override',
    'C16_no_overlap',
    'C17_ot_monthly_cap'
]

# Read the original solver_engine.py
with open('context/engine/solver_engine.py', 'r') as f:
    original_content = f.read()

for i, constraint in enumerate(constraints, 1):
    enabled = constraints[:i]
    
    # Modify the file to enable only these constraints
    modified = original_content.replace(
        '    print(f"[apply_constraints] ALL CONSTRAINTS DISABLED - baseline test...")\n    print(f"  ⚠️  NO CUSTOM CONSTRAINTS LOADED\\n")\n    return',
        f'    print(f"[apply_constraints] Testing with: {enabled}\\n")'
    ).replace(
        '    test_order = [',
        f'    test_order = {enabled}\n    original_list = ['
    )
    
    with open('context/engine/solver_engine.py', 'w') as f:
        f.write(modified)
    
    # Run solver
    result = subprocess.run(
        ['python', 'src/run_solver.py', '--in', 'input/input_v0.7.json'],
        capture_output=True,
        text=True,
        timeout=30
    )
    
    # Check both stdout and stderr
    output = result.stdout + result.stderr
    
    # Count assignments
    if 'Extracted 54 assigned' in output:
        print(f"✅ {constraint} OK (54 assignments)")
    elif 'Extracted 0 assigned' in output:
        print(f"❌ {constraint} BLOCKS (0 assignments)")
        print(f"\n🎯 BLOCKER: {constraint}")
        # Restore and exit
        with open('context/engine/solver_engine.py', 'w') as f:
            f.write(original_content)
        break
    else:
        # Print what we got
        lines = [l for l in output.split('\n') if 'Extracted' in l or 'assigned' in l.lower()]
        print(f"⚠️  {constraint}: {lines[:2] if lines else 'no output'}")

# Restore original
with open('context/engine/solver_engine.py', 'w') as f:
    f.write(original_content)

