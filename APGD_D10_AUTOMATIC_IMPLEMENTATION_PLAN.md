# APGD-D10 Default Behavior - Implementation Plan

**Date:** 2025-12-22  
**Status:** PROPOSAL

---

## 1. Current Behavior (v0.95)

### Input JSON Requirement
```json
{
  "requirements": [
    {
      "requirementId": "R1",
      "productTypeId": "APO",
      "scheme": "Scheme A",
      "enableAPGD-D10": true  // ← REQUIRED FIELD
    }
  ]
}
```

### Detection Logic
```python
def is_apgd_d10_employee(employee: dict, requirement: dict = None) -> bool:
    # Must be Scheme A
    if normalize_scheme(employee.get('scheme')) != 'A':
        return False
    
    # Must be APO product
    if employee.get('productTypeId') != 'APO':
        return False
    
    # Must have enableAPGD-D10 flag  ← REQUIRES FLAG
    if requirement and not requirement.get('enableAPGD-D10', False):
        return False
    
    return True
```

**Problem:** Users must remember to set `enableAPGD-D10: true` for every APO Scheme A requirement.

---

## 2. New Behavior (v0.96) - DEFAULT ENABLED

### Input JSON - No Flag Needed
```json
{
  "requirements": [
    {
      "requirementId": "R1",
      "productTypeId": "APO",
      "scheme": "Scheme A"
      // NO enableAPGD-D10 field needed!
    }
  ]
}
```

### Detection Logic - Automatic
```python
def is_apgd_d10_employee(employee: dict, requirement: dict = None) -> bool:
    """
    Check if employee qualifies for APGD-D10 treatment.
    
    APGD-D10 is AUTOMATICALLY ENABLED for all Scheme A + APO employees.
    This reflects MOM's blanket approval for the security industry.
    
    Detection Criteria:
    - Scheme: A (normalized)
    - Product: APO
    
    No explicit flag needed in input JSON.
    """
    # Must be Scheme A
    emp_scheme = normalize_scheme(employee.get('scheme', 'A'))
    if emp_scheme != 'A':
        return False
    
    # Must be APO product
    if employee.get('productTypeId') != 'APO':
        return False
    
    # APGD-D10 is automatically enabled for all Scheme A + APO
    return True
```

**Benefit:** Simpler inputs, automatic compliance for security industry.

---

## 3. Code Changes Required

### File 1: context/engine/time_utils.py

**Line 75-120 - Simplify APGD-D10 detection:**

```python
def is_apgd_d10_employee(employee: dict, requirement: dict = None) -> bool:
    """
    Check if employee qualifies for APGD-D10 treatment.
    
    APGD-D10 (MOM Approval for Security Industry):
    - Allows Scheme A APO employees to work 6-7 days/week
    - Exempts from weekly 44h cap (uses monthly caps instead)
    - Automatically enabled for all Scheme A + APO employees
    
    Detection Criteria:
    - Scheme: A (normalized from 'Scheme A', 'A', etc.)
    - Product Type: APO
    
    Args:
        employee: Employee dictionary with 'scheme' and 'productTypeId'
        requirement: Requirement dictionary (IGNORED for v0.96+)
    
    Returns:
        True if employee qualifies for APGD-D10, False otherwise
    
    Examples:
        Scheme A + APO → True (APGD-D10 enabled)
        Scheme A + CVSO → False (not APO)
        Scheme B + APO → False (not Scheme A)
        Scheme P + APO → False (not Scheme A)
    
    Note: The 'requirement' parameter is kept for backward compatibility
          but is no longer used. APGD-D10 is now automatic for Scheme A + APO.
    """
    # Normalize scheme to single letter code
    emp_scheme = normalize_scheme(employee.get('scheme', 'A'))
    
    # Must be Scheme A
    if emp_scheme != 'A':
        return False
    
    # Must be APO product
    if employee.get('productTypeId') != 'APO':
        return False
    
    # APGD-D10 automatically enabled for all Scheme A + APO
    return True
```

**Line 150-250 - Update docstring:**

```python
def calculate_apgd_d10_hours(...) -> dict:
    """
    Calculate APGD-D10 compliant work hours with rest day pay.
    
    APGD-D10 Rules (AUTOMATIC for Scheme A + APO):
    - Weekly normal cap: 44h (same as Scheme A)
    - Work patterns: 4-7 days/week allowed
    - Rest day pay: 1 RDP (8h) for 6th day, 2 RDP (16h) for 7th day in same week
    
    ...
```

### File 2: context/constraints/C2_mom_weekly_hours_pattern_aware.py

**Line 140-150 - Update APGD-D10 detection:**

```python
def add_constraints(model, ctx):
    """
    Enforce weekly normal-hours cap (44h) and monthly OT cap (72h).
    
    APGD-D10 EXEMPTION (AUTOMATIC for Scheme A + APO):
    APGD-D10 employees are exempt from weekly 44h cap (use monthly caps instead).
    Detection is automatic - no flag needed in input.
    """
    from context.engine.time_utils import is_apgd_d10_employee
    
    # Identify APGD-D10 employees (automatic for Scheme A + APO)
    apgd_employees = set()
    for emp in employees:
        emp_id = emp.get('employeeId')
        if is_apgd_d10_employee(emp):  # No requirement parameter needed
            apgd_employees.add(emp_id)
            print(f"[C2] APGD-D10 employee detected: {emp_id} (Scheme A + APO)")
```

### File 3: context/constraints/C17_apgd_d10_monthly_hours.py

**Line 1-50 - Update docstring:**

```python
"""C17: APGD-D10 Monthly Hour Caps (Scheme A + APO employees only).

APGD-D10 (MOM Approval - AUTOMATIC for Scheme A + APO):
- Allows 6-7 day work patterns
- Exempt from weekly 44h cap
- Must comply with monthly limits:
  - Normal hours: ≤192h per month (44h/week average)
  - OT hours: ≤72h per month (MOM standard)

Detection: Automatic for all employees with:
- scheme: "Scheme A"
- productTypeId: "APO"

No input flag needed (changed in v0.96).
"""
```

**Line 50-80 - Update employee detection:**

```python
def add_constraints(model, ctx):
    """
    Enforce monthly hour caps for APGD-D10 employees.
    
    APGD-D10 automatically applies to Scheme A + APO employees.
    """
    from context.engine.time_utils import is_apgd_d10_employee
    
    employees = ctx.get('employees', [])
    
    # Filter to APGD-D10 employees only (automatic detection)
    apgd_employees = []
    for emp in employees:
        if is_apgd_d10_employee(emp):
            apgd_employees.append(emp)
            emp_id = emp.get('employeeId')
            print(f"[C17] APGD-D10 monthly caps applied: {emp_id} (Scheme A + APO)")
    
    if not apgd_employees:
        print(f"[C17] No APGD-D10 employees found (Scheme A + APO)")
        return
```

### File 4: src/output_builder.py

**Line 750-800 - Update APGD-D10 detection:**

```python
# Detect APGD-D10 employees (automatic for Scheme A + APO)
from context.engine.time_utils import is_apgd_d10_employee

if is_apgd_d10_employee(employee):
    # Use APGD-D10 hour calculation (6-7 day patterns allowed)
    hours = calculate_apgd_d10_hours(...)
    print(f"[Output] APGD-D10 hours applied: {emp_id} (Scheme A + APO)")
else:
    # Use standard MOM hour calculation
    hours = calculate_mom_compliant_hours(...)
```

### File 5: src/input_validator.py

**Line 300-350 - OPTIONAL: Add deprecation warning:**

```python
# Validate requirements
for requirement in requirements:
    # DEPRECATED: Warn about enableAPGD-D10 flag
    if 'enableAPGD-D10' in requirement:
        result.add_warning(
            "requirements[].enableAPGD-D10",
            "DEPRECATED_FIELD",
            "enableAPGD-D10 flag is no longer needed. "
            "APGD-D10 is now automatically enabled for all Scheme A + APO employees. "
            "This field will be ignored."
        )
```

---

## 4. Backward Compatibility

### Old Inputs Still Work

**Input with flag:**
```json
{
  "enableAPGD-D10": true  // ← IGNORED (but harmless)
}
```
**Result:** APGD-D10 still applied (based on Scheme A + APO detection)

**Input with flag disabled:**
```json
{
  "enableAPGD-D10": false  // ← IGNORED (APGD-D10 still applied!)
}
```
**Result:** APGD-D10 STILL applied (flag ignored, automatic detection)

**Warning:** Users explicitly setting `enableAPGD-D10: false` will now have APGD-D10 enabled anyway. This is a **behavioral change**.

### Migration Strategy

**Option 1: Hard Break (Recommended)**
- Remove flag support completely
- APGD-D10 always automatic for Scheme A + APO
- Add deprecation warning in validator

**Option 2: Soft Break**
- Keep flag for backward compatibility
- Add warning: "Flag ignored, APGD-D10 automatic"
- Remove flag in v1.0

**Recommendation:** Option 1 (hard break) - cleaner and aligns with business logic.

---

## 5. Testing Requirements

### Test Cases

1. **Automatic Detection:**
   - Scheme A + APO → APGD-D10 enabled ✅
   - Scheme A + CVSO → APGD-D10 disabled ✅
   - Scheme B + APO → APGD-D10 disabled ✅

2. **Flag Ignored:**
   - `enableAPGD-D10: true` → APGD-D10 enabled (ignored)
   - `enableAPGD-D10: false` → APGD-D10 STILL enabled (ignored)
   - Flag missing → APGD-D10 enabled (automatic)

3. **Constraint Application:**
   - APGD-D10 employee → exempt from weekly 44h cap ✅
   - APGD-D10 employee → 6-7 day patterns allowed ✅
   - Non-APGD-D10 → weekly 44h cap enforced ✅

4. **Hour Calculations:**
   - APGD-D10 6-day pattern → correct rest day pay ✅
   - APGD-D10 7-day pattern → correct rest day pay ✅
   - Non-APGD-D10 → standard MOM hours ✅

### Test Files

```python
# tests/test_apgd_d10_automatic.py

def test_apgd_d10_automatic_detection():
    """Test APGD-D10 is automatically enabled for Scheme A + APO"""
    
    # Scheme A + APO → APGD-D10
    emp1 = {'scheme': 'Scheme A', 'productTypeId': 'APO'}
    assert is_apgd_d10_employee(emp1) == True
    
    # Scheme A + CVSO → Not APGD-D10
    emp2 = {'scheme': 'Scheme A', 'productTypeId': 'CVSO'}
    assert is_apgd_d10_employee(emp2) == False
    
    # Scheme B + APO → Not APGD-D10
    emp3 = {'scheme': 'Scheme B', 'productTypeId': 'APO'}
    assert is_apgd_d10_employee(emp3) == False

def test_apgd_d10_flag_ignored():
    """Test enableAPGD-D10 flag is ignored"""
    
    emp = {'scheme': 'Scheme A', 'productTypeId': 'APO'}
    
    # Flag = true (ignored)
    req1 = {'enableAPGD-D10': True}
    assert is_apgd_d10_employee(emp, req1) == True
    
    # Flag = false (STILL APGD-D10!)
    req2 = {'enableAPGD-D10': False}
    assert is_apgd_d10_employee(emp, req2) == True
    
    # No flag (automatic)
    req3 = {}
    assert is_apgd_d10_employee(emp, req3) == True

def test_apgd_d10_weekly_cap_exemption():
    """Test APGD-D10 employees exempt from weekly 44h cap"""
    
    input_data = {
        "employees": [
            {
                "employeeId": "E001",
                "scheme": "Scheme A",
                "productTypeId": "APO"
            }
        ],
        "demandItems": [
            {
                "requirements": [
                    {
                        "workPattern": ["D","D","D","D","D","D","O"]  # 6-day pattern
                    }
                ]
            }
        ]
    }
    
    result = solve(input_data)
    
    # Should be OPTIMAL (6-day pattern allowed)
    assert result['status'] == 'OPTIMAL'
    
    # Check employee is APGD-D10
    employee_roster = result['employeeRoster'][0]
    assert employee_roster['isAPGD-D10'] == True  # NEW field in output
```

---

## 6. Output Format Changes (Optional)

### Add APGD-D10 Indicator to Output

```json
{
  "employeeRoster": [
    {
      "employeeId": "00001",
      "scheme": "Scheme A",
      "productTypeId": "APO",
      "isAPGD-D10": true,  // ← NEW FIELD (optional)
      "exemptions": ["WEEKLY_44H_CAP"],  // ← NEW FIELD (optional)
      "workDays": 21,
      "offDays": 10
    }
  ]
}
```

**Benefits:**
- Transparency for users
- Easy audit of APGD-D10 application
- Helps debugging

---

## 7. Documentation Updates

### Files to Update

1. **SCHEME_HANDLING_WORKFLOW.md**
   - Update APGD-D10 section to reflect automatic behavior
   - Remove references to `enableAPGD-D10` flag

2. **API Documentation**
   - Remove `enableAPGD-D10` from requirement schema
   - Add note: "APGD-D10 automatic for Scheme A + APO"

3. **Input Schema (context/schemas/)**
   - Remove `enableAPGD-D10` field
   - Update requirement schema to v0.96

4. **Migration Guide**
   - Add note: "enableAPGD-D10 flag no longer needed"
   - Warn: "Flag will be ignored if present"

---

## 8. Rollout Plan

### Phase 1: Code Changes (Week 1)
- Update `is_apgd_d10_employee()` to remove flag check
- Update all constraint files (C2, C17, etc.)
- Update output builder
- Add unit tests

### Phase 2: Validation Updates (Week 1)
- Add deprecation warning in input validator
- Update schema documentation
- Test with real inputs

### Phase 3: Documentation (Week 2)
- Update all docs to remove flag references
- Update API examples
- Create migration guide

### Phase 4: Deployment (Week 2)
- Deploy to staging
- Notify users of automatic APGD-D10
- Deploy to production

---

## 9. Benefits Summary

### For Users

✅ **Simpler Inputs:** No need to remember `enableAPGD-D10` flag  
✅ **Automatic Compliance:** APGD-D10 applied correctly by default  
✅ **Less Errors:** Can't forget to enable APGD-D10 for APO Scheme A  
✅ **Cleaner JSON:** One less field to maintain

### For System

✅ **Consistent Logic:** APGD-D10 always applied correctly  
✅ **Fewer Bugs:** No user error from missing flag  
✅ **Simpler Code:** Remove flag checking logic  
✅ **Better UX:** System is smarter, requires less configuration

---

## 10. Risk Assessment

### Low Risk
- Change aligns with business logic (APO Scheme A always uses APGD-D10)
- Backward compatible (flag ignored if present)
- Well-defined detection criteria (Scheme A + APO)

### Potential Issues

1. **Users explicitly disabling APGD-D10:**
   - **Issue:** Some users might have set `enableAPGD-D10: false`
   - **Impact:** APGD-D10 will now be enabled anyway
   - **Mitigation:** Add warning in validator, document change clearly

2. **Non-APO Scheme A employees:**
   - **Issue:** APGD-D10 only applies to APO, not CVSO/AVSO
   - **Impact:** None - detection checks productTypeId
   - **Mitigation:** Clear documentation of detection criteria

### Rollback Plan

If issues arise:
1. Add feature flag: `USE_AUTOMATIC_APGD_D10=false`
2. Revert to old behavior (check enableAPGD-D10 flag)
3. Deploy hotfix
4. Communicate to users

---

## 11. Open Questions

1. **Other Product Types:**
   - Should APGD-D10 apply to other security products?
   - Or strictly APO only?

2. **Scheme B/P APO:**
   - Can Scheme B or P employees be APO?
   - If yes, should they get APGD-D10?

3. **MOM Approval Tracking:**
   - Should system track actual MOM approval status?
   - Or assume all Scheme A + APO have approval?

---

**Recommendation:** APPROVE and implement in v0.96 alongside multiple schemes support.
