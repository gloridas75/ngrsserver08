import subprocess

soft_constraints = [
    'S1_rotation_pattern',
    'S2_preferences',
    'S3_consistent_start',
    'S4_min_short_gaps',
    'S5_officer_continuity',
    'S6_minimize_shift_change_within_team',
    'S7_zone_preference',
    'S8_team_size_feasibility',
    'S9_travel_slack',
    'S10_fair_ot',
    'S11_public_holiday_coverage',
    'S12_allowance_optimization',
    'S13_substitute_logic',
    'S14_midmonth_insert',
    'S15_demand_coverage_score',
    'S16_whitelist_blacklist'
]

# Read current solver_engine.py
with open('context/engine/solver_engine.py', 'r') as f:
    original = f.read()

# Build the full list (all hard + soft)
hard_constraints = [
    'C1_mom_daily_hours', 'C2_mom_weekly_hours', 'C3_consecutive_days',
    'C4_rest_period', 'C5_offday_rules', 'C6_parttimer_limits',
    'C7_license_validity', 'C8_provisional_license', 'C9_gender_balance',
    'C10_skill_role_match', 'C11_rank_product_match', 'C12_team_completeness',
    'C15_qualification_expiry_override', 'C16_no_overlap', 'C17_ot_monthly_cap'
]

print("Testing soft constraints one by one...\n")

for i, constraint in enumerate(soft_constraints, 1):
    enabled_list = hard_constraints + soft_constraints[:i]
    
    # Modify file
    modified = original.replace(
        "    test_order = [",
        f"    test_order = {enabled_list}\n    old = ["
    )
    
    with open('context/engine/solver_engine.py', 'w') as f:
        f.write(modified)
    
    print(f"[{i}/16] Testing {constraint}...")
    result = subprocess.run(
        ['python', 'src/run_solver.py', '--in', 'input/input_v0.7.json'],
        capture_output=True, text=True, timeout=30
    )
    
    output = result.stdout + result.stderr
    if 'Extracted 54 assigned' in output:
        print(f"     ✅ OK (54 assignments)\n")
    elif 'Extracted 0 assigned' in output:
        print(f"     ❌ BLOCKS (0 assignments)")
        print(f"     🎯 BLOCKER: {constraint}\n")
        break
    else:
        print(f"     ⚠️  Unclear output\n")

# Restore
with open('context/engine/solver_engine.py', 'w') as f:
    f.write(original)

print("✓ Restored solver_engine.py")
