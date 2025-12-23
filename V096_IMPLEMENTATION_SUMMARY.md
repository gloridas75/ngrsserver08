# v0.96 Implementation Summary - Three Critical Changes

**Date:** 2025-12-22  
**Status:** PROPOSAL - Awaiting Approval  
**Target Version:** v0.96

---

## Executive Summary

This document summarizes three important architectural improvements proposed for v0.96:

1. **Multiple Schemes Support** - Accept array of schemes per requirement
2. **APGD-D10 Automatic Detection** - Remove redundant flag, auto-enable for Scheme A + APO
3. **Cross-Mode Scheme Consistency** - Ensure all scheme features work for both roster types

All three changes are **backward compatible** and can be implemented together in v0.96.

---

## Change #1: Multiple Schemes Support

### Problem
- Current: Can only specify ONE scheme per requirement
- No way to say "Accept Scheme A OR Scheme B" (without accepting all via "Global")
- "Global" terminology is confusing

### Solution

**Old Format (v0.95):**
```json
{
  "scheme": "Scheme A"  // Singular - only one scheme
}
```

**New Format (v0.96):**
```json
{
  "schemes": ["Scheme A", "Scheme B"]  // Plural - multiple schemes
}

// Special cases:
{
  "schemes": ["Any"]  // Accept all schemes (replaces "Global")
}

{
  "schemes": []  // Empty = accept all schemes
}
```

**Backward Compatibility:**
- Both singular `scheme` and plural `schemes` supported
- Priority: plural > singular
- "Global" → "Any" automatic conversion

### Implementation Details

**New Helper Functions:**
```python
# context/engine/time_utils.py

def normalize_schemes(requirement: dict) -> list:
    """
    Convert singular/plural scheme to normalized list.
    Returns: ['A', 'B', 'P'] or ['Any']
    """
    # Priority 1: schemes (plural)
    # Priority 2: scheme (singular) - backward compatible
    # Default: ['Any']

def is_scheme_compatible(employee_scheme: str, requirement_schemes: list) -> bool:
    """
    Check if employee matches any requirement scheme.
    Returns: True if compatible
    """
    if 'Any' in requirement_schemes:
        return True
    return employee_scheme in requirement_schemes
```

**Files to Modify:**
- `context/engine/time_utils.py` - Add 2 helper functions
- `src/preprocessing/icpmp_integration.py` - Update 3 locations
- `src/feasibility_checker.py` - Update 2 locations
- `src/input_validator.py` - Update validation
- `src/roster_template_validator.py` - Update validation

**Testing:**
- 5 test cases covering backward compatibility, multiple schemes, "Any" keyword

**Full Details:** See [MULTIPLE_SCHEMES_IMPLEMENTATION_PLAN.md](MULTIPLE_SCHEMES_IMPLEMENTATION_PLAN.md)

---

## Change #2: APGD-D10 Automatic Detection

### Problem
- Current: Requires explicit `enableAPGD-D10: true` flag in input JSON
- Flag is redundant - if employee is Scheme A + APO, should auto-enable
- Users must remember to set flag (error-prone)

### Solution

**Old Format (v0.95):**
```json
{
  "requirements": [
    {
      "productTypeId": "APO",
      "scheme": "Scheme A",
      "enableAPGD-D10": true  // ← REQUIRED FLAG
    }
  ]
}
```

**New Format (v0.96):**
```json
{
  "requirements": [
    {
      "productTypeId": "APO",
      "scheme": "Scheme A"
      // NO enableAPGD-D10 field needed! (automatic)
    }
  ]
}
```

**Detection Logic:**
```python
def is_apgd_d10_employee(employee: dict, requirement: dict = None) -> bool:
    """
    APGD-D10 automatically enabled for all Scheme A + APO employees.
    No flag needed.
    """
    emp_scheme = normalize_scheme(employee.get('scheme', 'A'))
    
    if emp_scheme != 'A':
        return False
    
    if employee.get('productTypeId') != 'APO':
        return False
    
    # APGD-D10 automatic for Scheme A + APO
    return True
```

### Implementation Details

**Files to Modify:**
- `context/engine/time_utils.py` - Simplify `is_apgd_d10_employee()` (remove flag check)
- `context/constraints/C2_mom_weekly_hours_pattern_aware.py` - Update docstring
- `context/constraints/C17_apgd_d10_monthly_hours.py` - Update detection
- `src/output_builder.py` - Update detection
- `src/input_validator.py` - Add deprecation warning (optional)

**Backward Compatibility:**
- Old inputs with `enableAPGD-D10` flag still work (flag ignored)
- **Breaking behavior:** `enableAPGD-D10: false` will now ENABLE APGD-D10 anyway

**Testing:**
- 4 test cases covering automatic detection, flag ignored, constraint application

**Full Details:** See [APGD_D10_AUTOMATIC_IMPLEMENTATION_PLAN.md](APGD_D10_AUTOMATIC_IMPLEMENTATION_PLAN.md)

---

## Change #3: Cross-Mode Scheme Consistency

### Problem
- Some scheme features work differently in demandBased vs outcomeBased modes
- Gap identified: outcomeBased doesn't filter by scheme (demandBased does)
- Need to ensure consistent behavior across both modes

### Current State

| Feature | demandBased | outcomeBased | Status |
|---------|-------------|--------------|--------|
| Daily caps (14h/13h/9h) | ✅ Constraint | ✅ Validation | ✅ Consistent |
| Weekly 44h cap | ✅ Constraint | ✅ Validation | ✅ Consistent |
| APGD-D10 detection | ✅ Constraint | ✅ Validation | ✅ Consistent |
| **Scheme filtering** | ✅ ICPMP filters | ❌ Uses all employees | ❌ **GAP** |
| Multiple schemes | ⏳ Planned | ⏳ Planned | ⏳ Pending |

### Solution

**Add Scheme Filtering to outcomeBased:**
```python
# src/roster_template_validator.py

def validate_roster(roster, employees, requirements):
    """
    Validate roster template against requirements.
    NOW WITH SCHEME FILTERING (matches demandBased behavior).
    """
    for req_id, assignments in assignments_by_req.items():
        requirement = find_requirement(req_id, requirements)
        scheme_list = normalize_schemes(requirement)  # NEW
        
        for assignment in assignments:
            employee = find_employee(assignment['employeeId'], employees)
            emp_scheme = normalize_scheme(employee.get('scheme', 'A'))
            
            # NEW: Check scheme compatibility
            if not is_scheme_compatible(emp_scheme, scheme_list):
                raise ValidationError(
                    f"Employee {emp_id} (Scheme {emp_scheme}) "
                    f"cannot fulfill requirement {req_id} "
                    f"(requires Scheme: {', '.join(scheme_list)})"
                )
```

### Implementation Details

**Files to Modify:**
- `src/roster_template_validator.py` - Add scheme filtering (NEW)
- `src/roster_template_validator.py` - Update to use `normalize_schemes()` (multiple schemes)

**Testing:**
- 4 test cases covering scheme filtering, multiple schemes in both modes

**Full Details:** See [CROSS_MODE_SCHEME_CONSISTENCY_PLAN.md](CROSS_MODE_SCHEME_CONSISTENCY_PLAN.md)

---

## Implementation Timeline

### Week 1: Core Implementation
**Days 1-2: Helper Functions + Tests**
- Implement `normalize_schemes()` in time_utils.py
- Implement `is_scheme_compatible()` in time_utils.py
- Write unit tests for helper functions
- Verify backward compatibility

**Days 3-4: Multiple Schemes Support**
- Update icpmp_integration.py (3 locations)
- Update feasibility_checker.py (2 locations)
- Update input_validator.py (validation)
- Update roster_template_validator.py (validation + filtering)
- Write integration tests

**Day 5: APGD-D10 Automatic**
- Simplify `is_apgd_d10_employee()` (remove flag check)
- Update constraint files (C2, C17)
- Update output builder
- Write tests for automatic detection

### Week 2: Testing + Deployment
**Days 1-2: Documentation**
- Update SCHEME_HANDLING_WORKFLOW.md
- Update README.md
- Create migration guide (v0.95 → v0.96)
- Update API documentation

**Days 3-4: Testing**
- Run all unit tests (100+ tests)
- Run integration tests (ICPMP, constraints, validation)
- Test with real production inputs
- Verify backward compatibility

**Day 5: Deployment**
- Deploy to staging
- Run smoke tests
- Deploy to production
- Monitor for issues

---

## Code Changes Summary

### Files to Create
- [ ] `tests/test_multiple_schemes.py` - Multiple schemes test suite
- [ ] `tests/test_apgd_d10_automatic.py` - APGD-D10 automatic tests
- [ ] `tests/test_cross_mode_scheme_consistency.py` - Cross-mode tests

### Files to Modify

| File | Change #1 (Multiple Schemes) | Change #2 (APGD-D10) | Change #3 (Cross-Mode) |
|------|------------------------------|----------------------|------------------------|
| `context/engine/time_utils.py` | ✅ Add 2 helper functions | ✅ Simplify detection | - |
| `src/preprocessing/icpmp_integration.py` | ✅ Update 3 locations | - | ✅ Use helpers |
| `src/feasibility_checker.py` | ✅ Update 2 locations | - | - |
| `src/input_validator.py` | ✅ Update validation | ⚠️ Add warning (optional) | - |
| `src/roster_template_validator.py` | ✅ Update validation | - | ✅ Add filtering |
| `context/constraints/C2_mom_weekly_hours_pattern_aware.py` | - | ✅ Update detection | - |
| `context/constraints/C17_apgd_d10_monthly_hours.py` | - | ✅ Update detection | - |
| `src/output_builder.py` | - | ✅ Update detection | - |

---

## Testing Strategy

### Unit Tests (New)
- `test_normalize_schemes()` - 5 test cases
- `test_is_scheme_compatible()` - 5 test cases
- `test_apgd_d10_automatic()` - 4 test cases

### Integration Tests (New)
- `test_multiple_schemes_icpmp()` - ICPMP filtering with multiple schemes
- `test_multiple_schemes_validation()` - Validation with multiple schemes
- `test_scheme_filtering_outcomeBased()` - Scheme filtering in outcomeBased mode

### Regression Tests (Existing)
- All existing constraint tests must pass ✅
- All existing ICPMP tests must pass ✅
- Backward compatibility: old inputs must still work ✅

---

## Backward Compatibility

### v0.95 Inputs (Old Format)

**Example 1: Singular scheme**
```json
{
  "requirements": [
    {
      "scheme": "Scheme A",  // ← OLD FORMAT (singular)
      "enableAPGD-D10": true  // ← OLD FLAG (ignored)
    }
  ]
}
```
**Result:** ✅ Still works (backward compatible)

**Example 2: "Global" scheme**
```json
{
  "requirements": [
    {
      "scheme": "Global"  // ← OLD KEYWORD
    }
  ]
}
```
**Result:** ✅ Automatically converts to `["Any"]`

### v0.96 Inputs (New Format)

**Example 1: Multiple schemes**
```json
{
  "requirements": [
    {
      "schemes": ["Scheme A", "Scheme B"]  // ← NEW FORMAT (plural)
      // NO enableAPGD-D10 flag needed
    }
  ]
}
```
**Result:** ✅ Accepts Scheme A or B employees, APGD-D10 automatic

**Example 2: "Any" scheme**
```json
{
  "requirements": [
    {
      "schemes": ["Any"]  // ← NEW KEYWORD (clearer than "Global")
    }
  ]
}
```
**Result:** ✅ Accepts all schemes (A, B, P)

---

## Migration Guide

### For Users

**Step 1: Update scheme field (optional, recommended)**
```json
// OLD (v0.95):
"scheme": "Scheme A"

// NEW (v0.96):
"schemes": ["Scheme A"]
```

**Step 2: Remove enableAPGD-D10 flag (optional, recommended)**
```json
// OLD (v0.95):
"enableAPGD-D10": true  // ← REMOVE THIS

// NEW (v0.96):
// (No flag needed, automatic for Scheme A + APO)
```

**Step 3: Use "Any" instead of "Global" (optional, recommended)**
```json
// OLD (v0.95):
"scheme": "Global"

// NEW (v0.96):
"schemes": ["Any"]
```

### Deprecation Timeline

- **v0.96**: Add plural `schemes`, support both formats, APGD-D10 automatic
- **v0.97**: Deprecate "Global" keyword (add warning)
- **v1.0**: Remove singular `scheme` (breaking change)

---

## Benefits Summary

### For Users

✅ **More Flexible** - Specify multiple schemes per requirement  
✅ **Less Configuration** - APGD-D10 automatic, no flag needed  
✅ **More Consistent** - Same scheme behavior in both roster types  
✅ **Clearer Intent** - "Any" is clearer than "Global"  
✅ **Backward Compatible** - Existing inputs continue working  
✅ **Fewer Errors** - Can't forget to enable APGD-D10

### For System

✅ **Better ICPMP** - More precise employee filtering  
✅ **Cleaner Code** - Reusable helper functions  
✅ **Single Source of Truth** - Consistent scheme logic  
✅ **Maintainability** - Easier to extend with new schemes  
✅ **Testability** - Consistent behavior easier to test

---

## Risk Assessment

### Low Risk Changes
- Multiple schemes: Purely additive, backward compatible
- APGD-D10: Aligns with business logic, automatic detection
- Cross-mode: Fixes inconsistency, improves validation

### Potential Issues

1. **APGD-D10 Breaking Behavior:**
   - **Issue:** Users with `enableAPGD-D10: false` will now have APGD-D10 enabled
   - **Impact:** Low (unlikely users explicitly disable it)
   - **Mitigation:** Add warning in release notes

2. **outcomeBased Scheme Filtering:**
   - **Issue:** Some existing templates might violate scheme requirements
   - **Impact:** Medium (validation will now fail)
   - **Mitigation:** Add feature flag `STRICT_SCHEME_VALIDATION=false` in v0.96, true in v1.0

### Rollback Plan

If issues arise:
1. Add feature flags to disable new behaviors
2. Revert to old logic
3. Deploy hotfix
4. Communicate to users

---

## Success Criteria

- [ ] All 5 multiple schemes tests pass
- [ ] All 4 APGD-D10 automatic tests pass
- [ ] All 4 cross-mode consistency tests pass
- [ ] All existing tests continue passing (backward compatibility)
- [ ] ICPMP correctly filters by multiple schemes
- [ ] "Global" inputs automatically convert to "Any"
- [ ] APGD-D10 automatically enabled for Scheme A + APO
- [ ] outcomeBased validates scheme compatibility (matches demandBased)
- [ ] Documentation updated and clear
- [ ] Zero production issues in Week 2

---

## Open Questions

1. **Scheme Terminology:**
   - Should we use "Any" or "All" for accepting all schemes?
   - Recommendation: "Any" (matches programming conventions)

2. **APGD-D10 Scope:**
   - Should APGD-D10 apply to other product types besides APO?
   - Recommendation: APO only (matches MOM approval scope)

3. **Empty Schemes Array:**
   - Should `"schemes": []` mean "Any" or error?
   - Recommendation: "Any" (permissive, user-friendly)

4. **Feature Flag Timeline:**
   - Should `STRICT_SCHEME_VALIDATION` default to false or true in v0.96?
   - Recommendation: false (avoid breaking existing templates)

---

## Next Steps

1. **User Review & Approval:**
   - Review this summary and the three detailed implementation plans
   - Approve changes or request modifications
   - Confirm timeline (2 weeks feasible?)

2. **Implementation:**
   - Week 1: Core implementation (helper functions, file updates, tests)
   - Week 2: Documentation, testing, deployment

3. **Communication:**
   - Release notes for v0.96
   - Migration guide for users
   - API documentation updates

---

## Related Documents

- [MULTIPLE_SCHEMES_IMPLEMENTATION_PLAN.md](MULTIPLE_SCHEMES_IMPLEMENTATION_PLAN.md) - Detailed plan for Change #1
- [APGD_D10_AUTOMATIC_IMPLEMENTATION_PLAN.md](APGD_D10_AUTOMATIC_IMPLEMENTATION_PLAN.md) - Detailed plan for Change #2
- [CROSS_MODE_SCHEME_CONSISTENCY_PLAN.md](CROSS_MODE_SCHEME_CONSISTENCY_PLAN.md) - Detailed plan for Change #3
- [SCHEME_HANDLING_WORKFLOW.md](SCHEME_HANDLING_WORKFLOW.md) - Comprehensive scheme documentation

---

**Ready to proceed?** Please review and approve these changes so we can start implementation.
