import sys
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

# Read the solver_engine.py file
with open('context/engine/solver_engine.py', 'r') as f:
    content = f.read()

blockers = []

for i, constraint in enumerate(constraints, 1):
    # Enable constraints up to current one
    enabled = constraints[:i]
    
    # Create modified content
    modified = content.replace(
        '    return',
        f'    pass  # Testing {constraint}'
    ).replace(
        '    # Will re-enable one by one below',
        f'    # Testing: {", ".join(enabled)}'
    ).replace(
        '    test_order = [',
        f'    enabled_constraints = {enabled}\n    test_order = enabled_constraints\n    if False:  # Old list ['
    )
    
    # Write modified file
    with open('context/engine/solver_engine.py', 'w') as f:
        f.write(modified)
    
    # Run solver
    result = subprocess.run(
        ['python', 'src/run_solver.py', '--in', 'input/input_v0.7.json'],
        capture_output=True,
        text=True,
        timeout=30
    )
    
    # Check if assignments were made
    if '✓ Extracted 0 assigned slots' in result.stdout:
        print(f"❌ {constraint} BLOCKS assignments")
        blockers.append(constraint)
        break  # Found the blocker
    elif '✓ Extracted 54 assigned slots' in result.stdout or '✓ Extracted' in result.stdout:
        print(f"✅ {constraint} OK")
    else:
        print(f"⚠️  {constraint} unclear result")

# Restore original
with open('context/engine/solver_engine.py', 'w') as f:
    f.write(content)

if blockers:
    print(f"\n🎯 BLOCKER FOUND: {blockers[0]}")
else:
    print("\n✅ All constraints passed!")

