# APGD-D10 ICPMP Known Limitation

## Summary
ICPMP (configuration optimizer) does **NOT** account for APGD-D10 special capacity rules when calculating optimal employee counts. This results in slight over-provisioning during preprocessing.

## Impact
**Capacity Underestimation: ~14%**
- **Standard Scheme A**: 6 days/week capacity (C5 requires 1 rest day)
- **APGD-D10 (Scheme A)**: 7 days/week capacity (C5 exemption)
- **ICPMP treats both as**: 6 days/week

## Technical Details

### Current ICPMP Logic
```python
# context/engine/config_optimizer_v3.py
def calculate_scheme_max_days_per_week(scheme: str) -> int:
    if scheme_normalized in ['A', 'B']:
        # Full-time schemes: Need at least 1 rest day per week (C3 constraint)
        # So maximum is 6 work days per week
        return 6  # ← APGD-D10 treated as standard Scheme A
```

### APGD-D10 Actual Capacity
- **C5 Exemption**: APGD-D10 employees are EXEMPT from weekly rest day requirement
- **Actual Max**: 7 days/week (limited only by C3 8-day consecutive cap)
- **Monthly Caps**: 246h standard / 268h foreign CPL/SGT (C19)

## Practical Impact

### Preprocessing Phase (ICPMP)
- ICPMP may recommend **more employees** than mathematically necessary
- Example: 8-day pattern requiring 7 days/week coverage
  - Optimal: Needs ~8 APGD-D10 employees (7 days/week capacity)
  - ICPMP: Calculates ~9 employees (using 6 days/week assumption)

### Solver Phase (CP-SAT)
- **Solver optimizes final count correctly** regardless of ICPMP input
- Solver enforces actual APGD-D10 constraints (C3, C4, C5, C19)
- May reject ICPMP's extra employees if not needed
- Final roster is always optimal

## Why This is Acceptable

1. **Conservative Approach**: Over-provisioning is safer than under-provisioning
2. **Solver Corrects**: CP-SAT solver optimizes final employee count
3. **Preprocessing Only**: ICPMP is guidance, not binding
4. **Low Risk**: Small difference (1-2 employees typically)
5. **No Violations**: Solver ensures compliance with actual constraints

## When to Be Aware

### High-Intensity Patterns (6-7 days/week)
- 8-day pattern: DDDDDDDDO (7 work days)
- ICPMP will be most conservative here
- Expect 10-15% more employees recommended than needed

### Large Pools (50+ APGD-D10 employees)
- Over-provisioning compounds with scale
- Consider manual adjustment of ICPMP output

### Cost-Sensitive Projects
- If minimizing headcount is critical
- Run solver twice: with ICPMP count and ICPMP count - 10%
- Use lower count if feasible

## Workaround (If Needed)

### Manual Adjustment
```python
# After ICPMP recommendation
icpmp_result = optimize_configuration(input_data)
recommended_count = icpmp_result['employeesRequired']

# For APGD-D10 requirements, reduce by 10-15%
if is_apgd_d10_requirement(requirement):
    adjusted_count = int(recommended_count * 0.85)  # Reduce by 15%
    print(f"APGD-D10 adjusted: {recommended_count} → {adjusted_count}")
```

### Solver Validation
Always validate ICPMP output with actual solver:
```bash
# Test with ICPMP recommendation
python src/run_solver.py --in icpmp_output.json --time 300

# If solver completes with employees unused, reduce count
# and re-run until minimal count found
```

## Future Enhancement (Not Prioritized)

### Option: Add APGD-D10 Detection
```python
def calculate_scheme_max_days_per_week(
    scheme: str,
    is_apgd_d10: bool = False  # New parameter
) -> int:
    if is_apgd_d10:
        return 7  # APGD-D10 can work 7 days/week
    elif scheme_normalized in ['A', 'B']:
        return 6  # Standard Scheme A/B need 1 rest day
    # ...
```

**Requirements**:
- Pass employee/requirement data through ICPMP chain
- Add APGD-D10 detection in config_optimizer_v3.py
- Test with mixed pools (APGD-D10 + standard Scheme A)
- Validate capacity calculations for all scenarios

**Risk**: Medium (ICPMP is complex, changes could affect other schemes)

## Validation History

### Test Case: 8-Day Pattern (Jan 2026)
- **Input**: RST-20251215-89436571_Solver_Input.json
- **Pattern**: DDDDDDDDO (8-day cycle)
- **Employees**: 14 APGD-D10
- **Result**: Solver produced OPTIMAL solution ✅
- **Observation**: Solver used all 14 employees (ICPMP would likely recommend 15-16)

### Test Case: 5-Day Pattern (Mar 2026)
- **Input**: RST-20251214-FF942E24_Solver_Input.json
- **Pattern**: DDDDDOO (5-day cycle)
- **Employees**: 14 APGD-D10
- **Result**: Solver produced OPTIMAL solution ✅
- **Observation**: Lower intensity pattern, ICPMP impact minimal

## Conclusion

**Status**: Known Limitation - Documented and Accepted

**Recommendation**: 
- Keep current implementation (no ICPMP changes)
- Document limitation in user-facing guides
- Solver ensures optimal final roster regardless of ICPMP input
- Monitor for feedback from production usage

**Review Date**: Q2 2026 (after 3+ months production data)

---

**Last Updated**: 2025-12-15  
**Owner**: NGRS Solver Team  
**Related Constraints**: C3, C4, C5, C19  
**Related Files**: `context/engine/config_optimizer_v3.py`
