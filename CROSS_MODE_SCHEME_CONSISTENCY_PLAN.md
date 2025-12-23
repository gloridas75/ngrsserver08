# Cross-Mode Scheme Consistency - Implementation Plan

**Date:** 2025-12-22  
**Status:** VERIFICATION & ENHANCEMENT

---

## 1. Overview

**Goal:** Ensure all scheme-related aspects work consistently for both:
- **demandBased** rosters (CP-SAT constraint solving)
- **outcomeBased** rosters (template validation)

**Current Status:** Most scheme features already work for both modes, but with different implementations. This plan verifies consistency and addresses gaps.

---

## 2. Scheme Features Comparison

### Feature Matrix

| Feature | demandBased (CP-SAT) | outcomeBased (Template) | Consistent? |
|---------|---------------------|------------------------|-------------|
| Daily hour caps (14h/13h/9h) | ✅ Hard constraint (C1) | ✅ Validation check | ✅ YES |
| Weekly 44h cap | ✅ Hard constraint (C2) | ✅ Validation check | ✅ YES |
| Monthly OT cap (72h) | ✅ Hard constraint (C2) | ✅ Validation check | ✅ YES |
| APGD-D10 detection | ✅ Constraint (C17) | ✅ Hour calculation | ✅ YES |
| APGD-D10 monthly caps | ✅ Hard constraint (C17) | ✅ Validation check | ✅ YES |
| ICPMP scheme filtering | ✅ Preprocesses | ❌ Uses all employees | ❌ **GAP** |
| OT-aware config (Scheme P) | ✅ ICPMP optimizes | ❌ No optimization | ⚠️ **EXPECTED** |
| Multiple schemes (proposed) | ⏳ Will support | ⏳ Will support | ⏳ **PENDING** |

**Legend:**
- ✅ Fully implemented
- ❌ Gap/missing
- ⚠️ Expected difference (by design)
- ⏳ Planned for v0.96

---

## 3. Current Implementation Details

### 3.1 Daily Hour Caps (Scheme-Specific)

**demandBased Mode:**
```python
# context/constraints/C1_mom_daily_hours.py
def add_constraints(model, ctx):
    """
    Enforce scheme-specific daily hour caps:
    - Scheme A: 14h max
    - Scheme B: 13h max
    - Scheme P: 9h max
    """
    for slot in slots:
        for emp_id in employees:
            scheme = normalize_scheme(employee.get('scheme', 'A'))
            
            if scheme == 'A':
                max_hours = 14
            elif scheme == 'B':
                max_hours = 13
            elif scheme == 'P':
                max_hours = 9
            
            model.Add(shift_hours <= max_hours)
```

**outcomeBased Mode:**
```python
# src/roster_template_validator.py
def validate_daily_hours(assignment, employee):
    """
    Validate assignment respects scheme daily caps.
    """
    scheme = normalize_scheme(employee.get('scheme', 'A'))
    
    if scheme == 'A':
        max_hours = 14
    elif scheme == 'B':
        max_hours = 13
    elif scheme == 'P':
        max_hours = 9
    
    if assignment['hours'] > max_hours:
        raise ValidationError(f"Daily hours exceed {max_hours}h cap for Scheme {scheme}")
```

**Status:** ✅ **CONSISTENT** - Both modes enforce same caps

---

### 3.2 Weekly 44h Normal Hours Cap

**demandBased Mode:**
```python
# context/constraints/C2_mom_weekly_hours_pattern_aware.py
def add_constraints(model, ctx):
    """
    Enforce 44h weekly normal hours cap.
    APGD-D10 employees exempt (monthly caps instead).
    """
    for week in weeks:
        for emp_id in employees:
            if is_apgd_d10_employee(employee):
                continue  # Exempt from weekly cap
            
            model.Add(sum(normal_hours_in_week) <= 44)
```

**outcomeBased Mode:**
```python
# src/roster_template_validator.py
def validate_weekly_hours(assignments, employee):
    """
    Validate weekly normal hours ≤ 44h.
    APGD-D10 employees exempt.
    """
    if is_apgd_d10_employee(employee):
        return  # Exempt
    
    for week in weeks:
        normal_hours = sum(a['normalHours'] for a in week_assignments)
        if normal_hours > 44:
            raise ValidationError(f"Weekly normal hours {normal_hours}h exceed 44h cap")
```

**Status:** ✅ **CONSISTENT** - Both modes enforce same caps with APGD-D10 exemption

---

### 3.3 APGD-D10 Detection

**demandBased Mode:**
```python
# context/constraints/C17_apgd_d10_monthly_hours.py
def add_constraints(model, ctx):
    """
    Apply APGD-D10 monthly caps for Scheme A + APO employees.
    """
    from context.engine.time_utils import is_apgd_d10_employee
    
    for emp in employees:
        if is_apgd_d10_employee(emp):
            # Apply monthly caps: 192h normal, 72h OT
            model.Add(sum(monthly_normal_hours) <= 192)
            model.Add(sum(monthly_ot_hours) <= 72)
```

**outcomeBased Mode:**
```python
# src/output_builder.py (hour calculation)
from context.engine.time_utils import is_apgd_d10_employee

if is_apgd_d10_employee(employee):
    # Use APGD-D10 hour calculation (6-7 day patterns)
    hours = calculate_apgd_d10_hours(...)
else:
    # Use standard MOM calculation
    hours = calculate_mom_compliant_hours(...)
```

**Status:** ✅ **CONSISTENT** - Both modes use same detection function

---

### 3.4 ICPMP Scheme Filtering (⚠️ GAP IDENTIFIED)

**demandBased Mode:**
```python
# src/preprocessing/icpmp_integration.py
def filter_employees_by_requirement(employees, requirement):
    """
    Filter employees to match requirement's scheme.
    """
    scheme_req = requirement.get('scheme', 'Global')
    
    if scheme_req == 'Global':
        return employees  # Accept all schemes
    
    filtered = []
    for emp in employees:
        emp_scheme = normalize_scheme(emp.get('scheme', 'A'))
        if emp_scheme == normalize_scheme(scheme_req):
            filtered.append(emp)
    
    return filtered
```

**outcomeBased Mode:**
```python
# src/roster_template_validator.py
def validate_roster(roster, employees, requirements):
    """
    Validate roster template against requirements.
    Uses ALL employees regardless of scheme.
    """
    # NO scheme filtering!
    for assignment in roster:
        employee = find_employee(assignment['employeeId'], employees)
        validate_assignment(assignment, employee)  # Validates scheme caps
```

**Status:** ❌ **INCONSISTENT** - demandBased filters by scheme, outcomeBased uses all employees

**Impact:**
- demandBased: ICPMP only suggests employees matching requirement scheme
- outcomeBased: Template can assign any employee, validation only checks caps

**Proposed Fix:**
```python
# src/roster_template_validator.py - ADD scheme filtering

def validate_roster(roster, employees, requirements):
    """
    Validate roster template against requirements.
    NOW WITH SCHEME FILTERING.
    """
    # Group assignments by requirement
    assignments_by_req = group_by_requirement(roster)
    
    for req_id, assignments in assignments_by_req.items():
        requirement = find_requirement(req_id, requirements)
        scheme_req = requirement.get('scheme', 'Global')
        
        for assignment in assignments:
            employee = find_employee(assignment['employeeId'], employees)
            
            # NEW: Check scheme compatibility
            emp_scheme = normalize_scheme(employee.get('scheme', 'A'))
            if scheme_req != 'Global' and emp_scheme != normalize_scheme(scheme_req):
                raise ValidationError(
                    f"Employee {employee['employeeId']} (Scheme {emp_scheme}) "
                    f"cannot fulfill requirement {req_id} (Scheme {scheme_req})"
                )
            
            # Existing validation (caps, etc.)
            validate_assignment(assignment, employee)
```

---

### 3.5 OT-Aware ICPMP (Scheme P)

**demandBased Mode:**
```python
# src/preprocessing/icpmp_integration.py
def run_icpmp_for_requirement(requirement, employees):
    """
    ICPMP suggests work patterns optimized for employee schemes.
    
    Scheme P employees:
    - Daily cap: 9h (vs 14h/13h for A/B)
    - More OT per day (5h normal + 4h OT)
    - ICPMP suggests longer patterns (7-day cycles)
    """
    scheme = requirement.get('scheme', 'Global')
    
    if scheme == 'P':
        # Optimize for Scheme P: longer patterns, more OT
        recommended_pattern = ['D', 'D', 'D', 'D', 'D', 'D', 'D', 'O', 'O']
    else:
        # Standard patterns for A/B
        recommended_pattern = ['D', 'D', 'D', 'D', 'D', 'O', 'O']
    
    return recommended_pattern
```

**outcomeBased Mode:**
```python
# src/roster_template_validator.py
def validate_roster(roster, employees, requirements):
    """
    Validation only - no pattern optimization.
    Templates are user-provided, not optimized.
    """
    # No ICPMP optimization (templates already defined)
    for assignment in roster:
        validate_assignment(assignment, employee)  # Check caps only
```

**Status:** ⚠️ **EXPECTED DIFFERENCE** - demandBased optimizes, outcomeBased validates

**Rationale:** outcomeBased mode uses pre-defined templates, so ICPMP optimization doesn't apply. This is by design.

---

## 4. Multiple Schemes Support (v0.96)

### Proposed Changes for BOTH Modes

**demandBased Mode:**
```python
# src/preprocessing/icpmp_integration.py
from context.engine.time_utils import normalize_schemes, is_scheme_compatible

def filter_employees_by_requirement(employees, requirement):
    """
    Filter employees to match requirement's scheme(s).
    NOW SUPPORTS MULTIPLE SCHEMES.
    """
    scheme_list = normalize_schemes(requirement)  # Returns ['A', 'B'] or ['Any']
    
    if 'Any' in scheme_list:
        return employees  # Accept all schemes
    
    filtered = []
    for emp in employees:
        emp_scheme = normalize_scheme(emp.get('scheme', 'A'))
        if is_scheme_compatible(emp_scheme, scheme_list):
            filtered.append(emp)
    
    return filtered
```

**outcomeBased Mode:**
```python
# src/roster_template_validator.py
from context.engine.time_utils import normalize_schemes, is_scheme_compatible

def validate_roster(roster, employees, requirements):
    """
    Validate roster template against requirements.
    NOW SUPPORTS MULTIPLE SCHEMES.
    """
    assignments_by_req = group_by_requirement(roster)
    
    for req_id, assignments in assignments_by_req.items():
        requirement = find_requirement(req_id, requirements)
        scheme_list = normalize_schemes(requirement)  # Returns ['A', 'B'] or ['Any']
        
        for assignment in assignments:
            employee = find_employee(assignment['employeeId'], employees)
            emp_scheme = normalize_scheme(employee.get('scheme', 'A'))
            
            # Check scheme compatibility
            if not is_scheme_compatible(emp_scheme, scheme_list):
                raise ValidationError(
                    f"Employee {employee['employeeId']} (Scheme {emp_scheme}) "
                    f"cannot fulfill requirement {req_id} (Schemes: {scheme_list})"
                )
            
            validate_assignment(assignment, employee)
```

**Status:** ⏳ **PLANNED FOR v0.96** - Will be consistent after implementation

---

## 5. Code Changes Required

### Files to Modify

| File | Change | Impact |
|------|--------|--------|
| `src/roster_template_validator.py` | Add scheme filtering in `validate_roster()` | **NEW** - fixes inconsistency |
| `src/roster_template_validator.py` | Update to use `normalize_schemes()` | Multiple schemes support |
| `src/preprocessing/icpmp_integration.py` | Update to use `normalize_schemes()` | Multiple schemes support |
| `context/constraints/*.py` | No changes (already consistent) | Constraints already scheme-aware |

### New Code: src/roster_template_validator.py

```python
from context.engine.time_utils import normalize_scheme, normalize_schemes, is_scheme_compatible

def validate_roster(
    roster: list,
    employees: list,
    requirements: list,
    mode: str = 'outcomeBased'
) -> dict:
    """
    Validate roster template against requirements and MOM compliance.
    
    NEW IN v0.96:
    - Scheme filtering (match demandBased behavior)
    - Multiple schemes support
    
    Args:
        roster: List of assignments
        employees: List of employee dicts
        requirements: List of requirement dicts
        mode: 'outcomeBased' or 'demandBased'
    
    Returns:
        {
            'valid': True/False,
            'errors': [...],
            'warnings': [...]
        }
    """
    errors = []
    warnings = []
    
    # Group assignments by requirement
    assignments_by_req = {}
    for assignment in roster:
        req_id = assignment.get('requirementId')
        if req_id not in assignments_by_req:
            assignments_by_req[req_id] = []
        assignments_by_req[req_id].append(assignment)
    
    # Validate each requirement's assignments
    for req_id, assignments in assignments_by_req.items():
        requirement = next((r for r in requirements if r['requirementId'] == req_id), None)
        if not requirement:
            errors.append(f"Requirement {req_id} not found")
            continue
        
        # NEW: Get scheme list (v0.96)
        scheme_list = normalize_schemes(requirement)
        
        for assignment in assignments:
            emp_id = assignment['employeeId']
            employee = next((e for e in employees if e['employeeId'] == emp_id), None)
            if not employee:
                errors.append(f"Employee {emp_id} not found")
                continue
            
            # NEW: Validate scheme compatibility (v0.96)
            emp_scheme = normalize_scheme(employee.get('scheme', 'A'))
            if not is_scheme_compatible(emp_scheme, scheme_list):
                errors.append(
                    f"Employee {emp_id} (Scheme {emp_scheme}) "
                    f"cannot fulfill requirement {req_id} "
                    f"(requires Scheme: {', '.join(scheme_list)})"
                )
                continue
            
            # Existing validations (daily caps, weekly caps, etc.)
            validate_assignment_caps(assignment, employee, errors, warnings)
    
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings
    }

def validate_assignment_caps(assignment, employee, errors, warnings):
    """
    Validate assignment respects scheme-specific caps.
    """
    scheme = normalize_scheme(employee.get('scheme', 'A'))
    
    # Daily cap
    if scheme == 'A':
        max_daily = 14
    elif scheme == 'B':
        max_daily = 13
    elif scheme == 'P':
        max_daily = 9
    else:
        max_daily = 14  # Default
    
    if assignment['hours'] > max_daily:
        errors.append(
            f"Assignment {assignment['assignmentId']} exceeds "
            f"daily cap of {max_daily}h for Scheme {scheme}"
        )
    
    # Weekly cap (44h normal, APGD-D10 exempt)
    if not is_apgd_d10_employee(employee):
        # Check weekly normal hours ≤ 44h
        # (Implement week grouping logic here)
        pass
    
    # Monthly OT cap (72h)
    # (Implement month grouping logic here)
    pass
```

---

## 6. Testing Requirements

### Test Cases

1. **Scheme Filtering (NEW):**
   - outcomeBased roster with Scheme A employee → Scheme B requirement → ERROR ❌
   - outcomeBased roster with Scheme A employee → Scheme A requirement → OK ✅
   - outcomeBased roster with any employee → "Any" requirement → OK ✅

2. **Multiple Schemes (NEW):**
   - outcomeBased roster with Scheme A employee → ["Scheme A", "Scheme B"] requirement → OK ✅
   - outcomeBased roster with Scheme P employee → ["Scheme A", "Scheme B"] requirement → ERROR ❌

3. **Daily Caps (Existing - Verify):**
   - demandBased: Scheme A → 14h max ✅
   - outcomeBased: Scheme A → 14h max ✅

4. **APGD-D10 (Existing - Verify):**
   - demandBased: Scheme A + APO → 6-day pattern allowed ✅
   - outcomeBased: Scheme A + APO → 6-day pattern validated ✅

### Test Files

```python
# tests/test_cross_mode_scheme_consistency.py

def test_outcomeBased_scheme_filtering():
    """Test outcomeBased mode filters by scheme (NEW in v0.96)"""
    
    employees = [
        {'employeeId': 'E001', 'scheme': 'Scheme A'},
        {'employeeId': 'E002', 'scheme': 'Scheme B'}
    ]
    
    requirements = [
        {
            'requirementId': 'R1',
            'scheme': 'Scheme A'  # Only Scheme A employees
        }
    ]
    
    roster = [
        {'employeeId': 'E001', 'requirementId': 'R1'},  # OK
        {'employeeId': 'E002', 'requirementId': 'R1'}   # ERROR (Scheme B)
    ]
    
    result = validate_roster(roster, employees, requirements)
    
    assert result['valid'] == False
    assert 'Scheme B' in result['errors'][0]
    assert 'cannot fulfill' in result['errors'][0]

def test_multiple_schemes_both_modes():
    """Test multiple schemes work for both modes"""
    
    # demandBased mode
    result1 = solve_demand_based({
        'employees': [...],
        'requirements': [
            {
                'schemes': ['Scheme A', 'Scheme B']  # Accept A or B
            }
        ]
    })
    assert result1['status'] == 'OPTIMAL'
    
    # outcomeBased mode
    result2 = validate_roster({
        'roster': [...],
        'requirements': [
            {
                'schemes': ['Scheme A', 'Scheme B']
            }
        ]
    })
    assert result2['valid'] == True
```

---

## 7. Documentation Updates

### Files to Update

1. **SCHEME_HANDLING_WORKFLOW.md**
   - Update section 3.2 (outcomeBased validation) to reflect scheme filtering
   - Add note about consistency between modes
   - Update comparison table to show both modes have scheme filtering

2. **README.md**
   - Add section: "Scheme Consistency Across Modes"
   - Explain that all scheme features work for both modes

3. **API Documentation**
   - Document scheme filtering for outcomeBased mode
   - Show examples of validation errors when schemes don't match

---

## 8. Rollout Plan

### Phase 1: Fix Scheme Filtering Gap (Week 1)
- Add scheme filtering to `roster_template_validator.py`
- Add tests for scheme filtering in outcomeBased mode
- Verify existing demandBased behavior unchanged

### Phase 2: Multiple Schemes Support (Week 1-2)
- Update both modes to use `normalize_schemes()` and `is_scheme_compatible()`
- Add tests for multiple schemes in both modes
- Update documentation

### Phase 3: Comprehensive Testing (Week 2)
- Run all constraint tests for both modes
- Verify APGD-D10 works consistently
- Test all scheme caps (daily, weekly, monthly)

### Phase 4: Deployment (Week 2)
- Deploy to staging
- Run full regression tests
- Deploy to production

---

## 9. Benefits Summary

### For Users

✅ **Predictable Behavior:** Scheme features work the same way in both modes  
✅ **No Surprises:** outcomeBased validates scheme compatibility (matches demandBased)  
✅ **Flexible:** Multiple schemes supported in both modes  
✅ **Consistent:** Same caps, same rules, same logic

### For System

✅ **Code Reuse:** Both modes use same helper functions  
✅ **Maintainability:** Single source of truth for scheme logic  
✅ **Testability:** Consistent behavior easier to test  
✅ **Documentation:** Clearer for users (no mode-specific quirks)

---

## 10. Risk Assessment

### Low Risk

- Changes mostly additive (scheme filtering in outcomeBased)
- Existing constraint logic unchanged
- Helper functions already tested

### Potential Issues

1. **Breaking Change for outcomeBased:**
   - **Issue:** Some existing templates might violate scheme requirements
   - **Impact:** Validation will now fail (previously passed)
   - **Mitigation:** Add feature flag `STRICT_SCHEME_VALIDATION=true` (default false in v0.96, true in v1.0)

2. **Performance Impact:**
   - **Issue:** Additional scheme checks in validation
   - **Impact:** Negligible (O(n) checks, simple comparisons)
   - **Mitigation:** None needed

### Rollback Plan

If issues arise:
1. Add feature flag: `ENABLE_SCHEME_FILTERING_OUTCOMEBASED=false`
2. Revert to old behavior (no scheme filtering)
3. Deploy hotfix
4. Communicate to users

---

## 11. Summary

### Current State

| Feature | demandBased | outcomeBased | Status |
|---------|-------------|--------------|--------|
| Daily caps | ✅ | ✅ | Consistent |
| Weekly caps | ✅ | ✅ | Consistent |
| APGD-D10 | ✅ | ✅ | Consistent |
| Scheme filtering | ✅ | ❌ | **FIX NEEDED** |
| Multiple schemes | ⏳ | ⏳ | Planned v0.96 |

### After v0.96

| Feature | demandBased | outcomeBased | Status |
|---------|-------------|--------------|--------|
| Daily caps | ✅ | ✅ | Consistent |
| Weekly caps | ✅ | ✅ | Consistent |
| APGD-D10 | ✅ | ✅ | Consistent |
| Scheme filtering | ✅ | ✅ | **FIXED** ✅ |
| Multiple schemes | ✅ | ✅ | **IMPLEMENTED** ✅ |

---

**Recommendation:** APPROVE and implement alongside multiple schemes support in v0.96.
