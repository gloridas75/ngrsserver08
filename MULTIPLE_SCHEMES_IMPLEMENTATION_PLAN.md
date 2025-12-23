# Multiple Schemes Support - Implementation Plan

**Date:** 2025-12-22  
**Status:** PROPOSAL

---

## 1. JSON Schema Changes (v0.96)

### Current Format (v0.95)
```json
{
  "requirements": [
    {
      "requirementId": "R1",
      "scheme": "Scheme A",     // Single scheme only
      // OR
      "scheme": "Global"        // All schemes
    }
  ]
}
```

### New Format (v0.96) - RECOMMENDED
```json
{
  "requirements": [
    {
      "requirementId": "R1",
      "schemes": ["Scheme A", "Scheme B"],  // Multiple schemes (NEW)
      
      // Special cases:
      "schemes": ["Any"],      // Accept all schemes (replaces "Global")
      "schemes": [],           // Empty array = accept all schemes
      
      // Backward compatibility:
      "scheme": "Scheme A"     // Still supported (converted to schemes: ["Scheme A"])
    }
  ]
}
```

### Priority Rules
1. If `schemes` (plural) exists → use it
2. Else if `scheme` (singular) exists → convert to `schemes: [scheme]`
3. If both exist → `schemes` takes precedence (ignore `scheme`)
4. "Global" → converted to `["Any"]` for backward compatibility

---

## 2. Code Changes Required

### File 1: Helper Function (context/engine/time_utils.py)

**NEW FUNCTION:**
```python
def normalize_schemes(requirement: dict) -> list:
    """
    Normalize scheme specification to list format.
    Handles backward compatibility with singular 'scheme'.
    
    Args:
        requirement: Requirement dictionary with 'schemes' or 'scheme' field
    
    Returns:
        List of normalized scheme codes: ['A', 'B', 'P'] or ['Any']
    
    Examples:
        schemes: ["Scheme A", "Scheme B"] → ['A', 'B']
        schemes: ["Any"] → ['Any']
        schemes: [] → ['Any']
        scheme: "Scheme A" → ['A']
        scheme: "Global" → ['Any']
        (missing) → ['Any']
    """
    from context.engine.time_utils import normalize_scheme
    
    # Priority 1: Check plural 'schemes'
    if 'schemes' in requirement:
        schemes_raw = requirement['schemes']
        
        # Empty array = accept all
        if not schemes_raw or len(schemes_raw) == 0:
            return ['Any']
        
        # Normalize each scheme
        normalized = []
        for s in schemes_raw:
            if s == 'Any' or s == 'any':
                return ['Any']  # Any overrides all others
            norm = normalize_scheme(s)
            if norm == 'A' or norm == 'B' or norm == 'P':
                normalized.append(norm)
        
        return normalized if normalized else ['Any']
    
    # Priority 2: Check singular 'scheme' (backward compatibility)
    if 'scheme' in requirement:
        scheme_raw = requirement['scheme']
        
        # "Global" → "Any"
        if scheme_raw == 'Global' or scheme_raw == 'global':
            return ['Any']
        
        # Normalize single scheme
        norm = normalize_scheme(scheme_raw)
        return [norm] if norm in ['A', 'B', 'P'] else ['Any']
    
    # Default: accept all schemes
    return ['Any']


def is_scheme_compatible(employee_scheme: str, requirement_schemes: list) -> bool:
    """
    Check if employee scheme matches any of the requirement schemes.
    
    Args:
        employee_scheme: Employee's scheme ('A', 'B', or 'P')
        requirement_schemes: List of accepted schemes (['A', 'B', 'P'] or ['Any'])
    
    Returns:
        True if compatible, False otherwise
    
    Examples:
        employee='A', requirement=['A', 'B'] → True
        employee='P', requirement=['A', 'B'] → False
        employee='A', requirement=['Any'] → True
    """
    # "Any" accepts all schemes
    if 'Any' in requirement_schemes:
        return True
    
    # Check if employee scheme is in the list
    return employee_scheme in requirement_schemes
```

### File 2: ICPMP Integration (src/preprocessing/icpmp_integration.py)

**CHANGES:**

**Line 423 - Replace scheme extraction:**
```python
# OLD:
scheme_req = requirement.get('scheme', 'Global')

# NEW:
from context.engine.time_utils import normalize_schemes
scheme_list = normalize_schemes(requirement)
```

**Line 478-480 - Replace scheme filter:**
```python
# OLD:
# Check scheme (if not Global)
if scheme_req != 'Global' and emp.get('scheme') != scheme_req:
    continue

# NEW:
# Check scheme compatibility
from context.engine.time_utils import normalize_scheme, is_scheme_compatible
emp_scheme = normalize_scheme(emp.get('scheme', 'A'))
if not is_scheme_compatible(emp_scheme, scheme_list):
    continue
```

**Line 527 - Replace diversity check:**
```python
# OLD:
if scheme_req == 'Global':
    # Maintain scheme diversity
    ...

# NEW:
if 'Any' in scheme_list or len(scheme_list) > 1:
    # Maintain scheme diversity for multiple schemes
    ...
```

### File 3: Feasibility Checker (src/feasibility_checker.py)

**Line 196 - Replace scheme extraction:**
```python
# OLD:
scheme_req_raw = requirement.get('Scheme', 'Global')

# NEW:
from context.engine.time_utils import normalize_schemes
scheme_list = normalize_schemes(requirement)
```

**Line 356-360 - Replace scheme check:**
```python
# OLD:
# Check scheme (if not Global)
scheme_req = normalize_scheme(scheme_req_raw)
if scheme_req != 'Global':
    if employee.get('scheme') != scheme_req:
        continue

# NEW:
from context.engine.time_utils import is_scheme_compatible, normalize_scheme
emp_scheme = normalize_scheme(employee.get('scheme', 'A'))
if not is_scheme_compatible(emp_scheme, scheme_list):
    continue
```

### File 4: Input Validator (src/input_validator.py)

**Line 442-461 - Add schemes validation:**
```python
# NEW: Support plural 'schemes' field
if 'schemes' in requirement:
    schemes_list = requirement['schemes']
    
    # Validate it's a list
    if not isinstance(schemes_list, list):
        result.add_error(f"requirements[].schemes", "INVALID_TYPE", 
                       "schemes must be an array")
        continue
    
    # Validate each scheme in the list
    for scheme in schemes_list:
        if scheme not in ['Any', 'any', 'Global', 'global']:
            # Check if scheme exists in schemeMap
            if scheme not in scheme_map.values() and scheme not in scheme_map.keys():
                result.add_error(f"requirements[].schemes", "INVALID_SCHEME", 
                               f"Scheme '{scheme}' not found in schemeMap")

# KEEP: Backward compatibility for singular 'scheme'
if 'scheme' in requirement:
    # Existing validation...
```

### File 5: Output Builder (src/output_builder.py)

**No changes needed** - uses employee scheme, not requirement scheme

### File 6: Template Validator (src/roster_template_validator.py)

**Line 150-180 - No changes needed** - uses employee scheme for caps

---

## 3. Example Use Cases

### Use Case 1: Single Scheme (Backward Compatible)
```json
{
  "requirements": [
    {
      "requirementId": "R1",
      "scheme": "Scheme A"
    }
  ]
}
```
**Result:** Only Scheme A employees selected

### Use Case 2: Multiple Schemes (NEW)
```json
{
  "requirements": [
    {
      "requirementId": "R1",
      "schemes": ["Scheme A", "Scheme B"]
    }
  ]
}
```
**Result:** Both Scheme A and Scheme B employees eligible

### Use Case 3: All Schemes
```json
{
  "requirements": [
    {
      "requirementId": "R1",
      "schemes": ["Any"]
    }
  ]
}
```
**Result:** All schemes (A, B, P) eligible

### Use Case 4: Shift-Specific Scheme Filter
```json
{
  "shifts": [
    {
      "shiftCode": "D",
      "startTime": "22:00",
      "endTime": "10:00",  // 12h shift
      "schemes": ["Scheme A", "Scheme B"]  // Exclude Scheme P (9h cap)
    }
  ]
}
```
**Result:** Scheme P automatically filtered (12h > 9h cap)

---

## 4. Migration Guide

### For Existing Inputs

**No changes required** - backward compatible!

Old inputs with `scheme: "Scheme A"` will continue to work.

### For New Inputs

**Recommended:** Use `schemes` (plural) for clarity:
```json
// Instead of:
"scheme": "Scheme A"

// Use:
"schemes": ["Scheme A"]

// Or for multiple:
"schemes": ["Scheme A", "Scheme B"]
```

### Deprecation Timeline

- **v0.96**: Introduce `schemes` (plural), keep `scheme` (singular)
- **v0.97**: Deprecate "Global" terminology (use "Any" instead)
- **v1.0**: Remove singular `scheme` support (breaking change)

---

## 5. Testing Requirements

### Test Cases

1. **Backward Compatibility:**
   - Input with `scheme: "Scheme A"` → works
   - Input with `scheme: "Global"` → converted to `["Any"]`

2. **Multiple Schemes:**
   - Input with `schemes: ["Scheme A", "Scheme B"]` → filters correctly
   - Input with `schemes: ["Any"]` → accepts all

3. **Priority Rules:**
   - Input with both `scheme` and `schemes` → `schemes` takes precedence

4. **ICPMP Filtering:**
   - 12h shift + `schemes: ["Scheme A", "Scheme B"]` → filters out Scheme P
   - 9h shift + `schemes: ["Any"]` → includes all schemes

5. **Proportional Distribution:**
   - `schemes: ["Scheme A", "Scheme B"]` → maintains A:B ratio
   - `schemes: ["Any"]` → maintains A:B:P ratio

### Test Files

```python
# tests/test_multiple_schemes.py

def test_single_scheme_backward_compatible():
    """Test singular 'scheme' still works"""
    input_data = {
        "requirements": [{"scheme": "Scheme A"}]
    }
    schemes = normalize_schemes(input_data['requirements'][0])
    assert schemes == ['A']

def test_multiple_schemes_new_format():
    """Test plural 'schemes' with multiple values"""
    input_data = {
        "requirements": [{"schemes": ["Scheme A", "Scheme B"]}]
    }
    schemes = normalize_schemes(input_data['requirements'][0])
    assert schemes == ['A', 'B']

def test_schemes_any_accepts_all():
    """Test 'Any' accepts all schemes"""
    input_data = {
        "requirements": [{"schemes": ["Any"]}]
    }
    schemes = normalize_schemes(input_data['requirements'][0])
    assert schemes == ['Any']
    
    # Test compatibility
    assert is_scheme_compatible('A', schemes) == True
    assert is_scheme_compatible('B', schemes) == True
    assert is_scheme_compatible('P', schemes) == True

def test_scheme_compatibility_filter():
    """Test employee filtering by scheme"""
    schemes = ['A', 'B']
    
    assert is_scheme_compatible('A', schemes) == True
    assert is_scheme_compatible('B', schemes) == True
    assert is_scheme_compatible('P', schemes) == False

def test_global_converts_to_any():
    """Test backward compatibility: 'Global' → ['Any']"""
    input_data = {
        "requirements": [{"scheme": "Global"}]
    }
    schemes = normalize_schemes(input_data['requirements'][0])
    assert schemes == ['Any']
```

---

## 6. Benefits Summary

### For Users

✅ **Flexibility:** Can specify multiple schemes per requirement  
✅ **Clarity:** `schemes: ["Scheme A", "Scheme B"]` is self-documenting  
✅ **Backward Compatible:** Existing inputs continue to work  
✅ **Simplified:** "Any" replaces confusing "Global" terminology

### For System

✅ **Consistent Logic:** Single code path for scheme filtering  
✅ **Better ICPMP:** Can optimize across multiple schemes  
✅ **Cleaner Code:** `is_scheme_compatible()` utility function  
✅ **Future-Proof:** Easy to add new schemes

---

## 7. Rollout Plan

### Phase 1: Add Helper Functions (Week 1)
- Add `normalize_schemes()` to time_utils.py
- Add `is_scheme_compatible()` to time_utils.py
- Add unit tests

### Phase 2: Update Core Components (Week 1)
- Update ICPMP integration
- Update feasibility checker
- Update input validator
- Add integration tests

### Phase 3: Documentation (Week 2)
- Update schema documentation
- Update API examples
- Update migration guide

### Phase 4: Deployment (Week 2)
- Deploy to staging
- Test with real inputs
- Deploy to production

---

## 8. Open Questions

1. **Scheme-Specific Shift Caps:**
   - Should shifts also have `schemes` field?
   - Example: Night shift only for Scheme A/B (exclude Scheme P)

2. **Mixed Scheme Teams:**
   - How to handle team composition requirements?
   - Example: "Must have at least 1 Scheme A supervisor per team"

3. **Scheme Distribution Ratios:**
   - Should user specify desired A:B:P ratio?
   - Or let ICPMP decide automatically?

---

**Recommendation:** APPROVE and implement in v0.96
