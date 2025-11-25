import subprocess

# Read the current solver_engine.py (C13 removed, constraints enabled)
with open('context/engine/solver_engine.py', 'r') as f:
    original_content = f.read()

# Test with all constraints (C1-C12 known good)
print("Testing C1-C12 (known good)...")
result = subprocess.run(
    ['python', 'src/run_solver.py', '--in', 'input/input_v0.7.json'],
    capture_output=True, text=True, timeout=30
)
if 'Extracted 54 assigned' in result.stdout + result.stderr:
    print("✅ C1-C12 still OK (54 assignments)\n")
else:
    print("❌ C1-C12 broken\n")

# Now test adding C15, C16, C17 one by one
remaining = ['C15_qualification_expiry_override', 'C16_no_overlap', 'C17_ot_monthly_cap']

for i, constraint in enumerate(remaining, 1):
    # Build enabled list
    enabled_list = [
        'C1_mom_daily_hours', 'C2_mom_weekly_hours', 'C3_consecutive_days',
        'C4_rest_period', 'C5_offday_rules', 'C6_parttimer_limits',
        'C7_license_validity', 'C8_provisional_license', 'C9_gender_balance',
        'C10_skill_role_match', 'C11_rank_product_match', 'C12_team_completeness'
    ] + remaining[:i]
    
    # Modify to load only these
    modified = original_content.replace(
        "    test_order = [",
        f"    test_order = {enabled_list}\n    old_list = ["
    )
    
    with open('context/engine/solver_engine.py', 'w') as f:
        f.write(modified)
    
    print(f"Testing with {constraint}...")
    result = subprocess.run(
        ['python', 'src/run_solver.py', '--in', 'input/input_v0.7.json'],
        capture_output=True, text=True, timeout=30
    )
    
    output = result.stdout + result.stderr
    if 'Extracted 54 assigned' in output:
        print(f"✅ {constraint} OK (54 assignments)\n")
    elif 'Extracted 0 assigned' in output:
        print(f"❌ {constraint} BLOCKS (0 assignments)")
        print(f"🎯 BLOCKER FOUND: {constraint}\n")
        break
    else:
        print(f"⚠️  {constraint} unclear output\n")

# Restore
with open('context/engine/solver_engine.py', 'w') as f:
    f.write(original_content)

print("Done! Restored original solver_engine.py")
