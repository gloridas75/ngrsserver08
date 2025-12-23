# NGRS Solver: Scheme A, B, P Handling - Complete Workflow

**Date:** 2025-12-21  
**Version:** 0.95

---

## Executive Summary

The NGRS solver handles three employee schemes with **different daily working hour limits** mandated by Singapore's Ministry of Manpower (MOM):

| Scheme | Type | Daily Cap | Weekly Normal | Monthly OT | Used For |
|--------|------|-----------|---------------|------------|----------|
| **Scheme A** | Full-time | 14h | 44h | 72h | Regular security officers (CPL, SGT, SER) |
| **Scheme B** | Full-time | 13h | 44h | 72h | Full-time civilian staff |
| **Scheme P** | Part-time | 9h | 36h | 72h | Part-time officers (CVSO, AVSO, etc.) |

**Key Insight:** These schemes apply to **BOTH demandBased and outcomeBased** rosters, but the enforcement mechanisms differ.

---

## 1. Workflow Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        INPUT JSON (v0.95)                               │
│  - rosteringBasis: "demandBased" OR "outcomeBased"                     │
│  - employees[].scheme: "Scheme A" / "Scheme B" / "Scheme P"            │
│  - requirements[].scheme: "Global" (applies to all schemes)            │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    ROSTERING BASIS DETECTION                            │
│              (src/solver.py:250-352)                                    │
├─────────────────────────────────────────────────────────────────────────┤
│  IF rosteringBasis == "outcomeBased"                                    │
│    → Route to: TEMPLATE-BASED VALIDATION (Path A)                      │
│  ELSE (demandBased)                                                     │
│    → Route to: CP-SAT SOLVER (Path B)                                  │
└─────────────────────────────────────────────────────────────────────────┘
              │                                    │
              │ Path A                             │ Path B
              ▼                                    ▼
┌──────────────────────────────┐    ┌──────────────────────────────────┐
│  TEMPLATE-BASED VALIDATION   │    │   CP-SAT CONSTRAINT SOLVER       │
│  (outcomeBased)              │    │   (demandBased)                  │
│                              │    │                                  │
│  • Preset assignments        │    │  1. ICPMP Preprocessing          │
│  • Validate against MOM      │    │     - Filter compatible schemes  │
│  • Check daily hour caps     │    │     - Optimize employee count    │
│  • No optimization           │    │                                  │
│                              │    │  2. CP-SAT Model Building        │
│                              │    │     - Add scheme constraints     │
│                              │    │     - Enforce hour limits        │
│                              │    │                                  │
│                              │    │  3. Solve & Optimize             │
│                              │    │     - Find optimal assignments   │
└──────────────────────────────┘    └──────────────────────────────────┘
              │                                    │
              └────────────────┬───────────────────┘
                               ▼
                    ┌──────────────────────────┐
                    │  OUTPUT JSON (v0.95)     │
                    │  - Scheme-specific hours │
                    │  - MOM compliance data   │
                    └──────────────────────────┘
```

---

## 2. Path A: outcomeBased (Template Validation)

**Use Case:** Pre-planned rosters (e.g., monthly templates) that need validation against MOM rules.

### Workflow Steps

```
1. Input: Complete assignments with preset schedules
   └─> employees[].scheme: "Scheme A/B/P"
   └─> assignments[]: {employeeId, shiftCode, startDateTime, endDateTime}

2. Template Validator (src/roster_template_validator.py)
   ├─> Extract employee scheme
   ├─> Calculate shift hours (gross, lunch, normal, OT)
   ├─> Check against daily caps:
   │   • Scheme A: ≤ 14h per shift
   │   • Scheme B: ≤ 13h per shift
   │   • Scheme P: ≤ 9h per shift
   └─> Validate weekly 44h cap (normal hours only)

3. Output: FEASIBLE or INFEASIBLE + violation details
```

### Scheme-Specific Logic (Template Mode)

**File:** `src/roster_template_validator.py`

```python
# Daily hour cap check (Line 150-180)
SCHEME_DAILY_CAPS = {
    'A': 14.0,  # Scheme A: 14h max per shift
    'B': 13.0,  # Scheme B: 13h max per shift
    'P': 9.0    # Scheme P: 9h max per shift
}

emp_scheme = normalize_scheme(employee.get('scheme', 'A'))
daily_cap = SCHEME_DAILY_CAPS.get(emp_scheme, 14.0)

if gross_hours > daily_cap:
    violations.append({
        'type': 'DAILY_HOUR_LIMIT_EXCEEDED',
        'employeeId': emp_id,
        'scheme': emp_scheme,
        'limit': daily_cap,
        'actual': gross_hours,
        'date': date_str
    })
```

**Key Points:**
- ✅ **No optimization** - validates existing assignments
- ✅ **Fast** - no CP-SAT solving (< 1 second for 100 employees)
- ✅ **Strict** - any violation = INFEASIBLE
- ❌ **No employee selection** - uses all employees in input

---

## 3. Path B: demandBased (CP-SAT Solver)

**Use Case:** Optimize roster from demand requirements, selecting minimal employees while respecting MOM rules.

### Workflow Steps

```
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 1: ICPMP v3.0 PREPROCESSING                                       │
│ (src/preprocessing/icpmp_integration.py)                                │
├─────────────────────────────────────────────────────────────────────────┤
│  Purpose: Filter employees by scheme compatibility and optimize count   │
│                                                                         │
│  1.1 Scheme-Based Shift Compatibility Filter                          │
│      • Calculate max shift duration from demand                        │
│      • Filter employees whose scheme cap < shift duration              │
│      • Example: 12h shift → exclude Scheme P (9h cap)                 │
│                                                                         │
│  1.2 OT-Aware Employee Count Optimization (Scheme P only)             │
│      • Flag: enableOtAwareIcpmp (default: true)                       │
│      • Scheme P: Calculate capacity including OT (45h/week)           │
│      • Scheme A/B: Use pattern work days (e.g., 6 days = 6 days)     │
│      • Result: Minimal employee count respecting hour limits          │
│                                                                         │
│  1.3 Proportional Scheme Distribution                                 │
│      • Maintain input scheme ratios (e.g., 70% A, 20% B, 10% P)      │
│      • Select employees proportionally from each scheme group         │
│                                                                         │
│  Output: Filtered employee list (e.g., 86 → 23 employees)             │
└─────────────────────────────────────────────────────────────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 2: CP-SAT MODEL BUILDING                                          │
│ (context/engine/solver_engine.py)                                       │
├─────────────────────────────────────────────────────────────────────────┤
│  Purpose: Add hard constraints to enforce MOM rules per scheme         │
│                                                                         │
│  2.1 C2: Pattern-Aware Weekly/Monthly Hours                           │
│      (context/constraints/C2_mom_weekly_hours_pattern_aware.py)        │
│      • Weekly cap: Σ(normal_hours) ≤ 44h (ALL schemes)                │
│      • Monthly OT cap: Σ(ot_hours) ≤ 72h (ALL schemes)                │
│      • Normal hours calculation (pattern-aware):                       │
│        - 4 days/week: 11.0h normal per shift                          │
│        - 5 days/week: 8.8h normal per shift                           │
│        - 6 days/week: 8.8h for days 1-5, 0h for day 6 (rest day pay) │
│                                                                         │
│  2.2 C6: Daily Gross Hour Cap (Scheme-Specific)                       │
│      • Scheme A: model.Add(gross_hours ≤ 14.0)                        │
│      • Scheme B: model.Add(gross_hours ≤ 13.0)                        │
│      • Scheme P: model.Add(gross_hours ≤ 9.0)                         │
│                                                                         │
│  2.3 Special: APGD-D10 Exemption (Scheme A + APO only)               │
│      • Allows 6-7 days/week for Scheme A APO employees               │
│      • Exempt from weekly 44h cap (use monthly caps instead)          │
│      • Requires: scheme="A" + productTypeId="APO" + APGD flag        │
│                                                                         │
│  Output: CP-SAT model with 50,000+ constraints                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 3: SOLVE & OPTIMIZE                                               │
│ (context/engine/solver_engine.py:solve())                               │
├─────────────────────────────────────────────────────────────────────────┤
│  • CP-SAT finds assignments satisfying ALL hard constraints            │
│  • Parallelization: 1-16 workers based on problem size                 │
│  • Result: OPTIMAL, FEASIBLE, or INFEASIBLE                            │
│                                                                         │
│  Solve Time Examples:                                                  │
│  • 23 employees × 310 slots = 1.2 seconds (after ICPMP)               │
│  • 86 employees × 310 slots = 60-70 seconds (without ICPMP)           │
└─────────────────────────────────────────────────────────────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 4: OUTPUT BUILDING                                                │
│ (src/output_builder.py)                                                 │
├─────────────────────────────────────────────────────────────────────────┤
│  • Calculate MOM-compliant hours per assignment                        │
│  • Break down: gross, lunch, normal, OT, rest day pay                 │
│  • Aggregate weekly/monthly totals per employee                        │
│  • Include scheme info in output JSON                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Scheme-Specific Techniques & Approaches

### 4.1 Daily Hour Caps (All Modes)

**Location:** `src/preprocessing/icpmp_integration.py:425-475`

```python
# Shift compatibility filter
SCHEME_HOUR_LIMITS = {
    'A': 14,  # Full-time Scheme A
    'B': 13,  # Full-time Scheme B
    'P': 9    # Part-time Scheme P (MOM regulated)
}

# Filter logic
max_shift_hours = calculate_max_shift_duration(demand_item)
emp_scheme = emp.get('scheme', 'Unknown')
scheme_limit = SCHEME_HOUR_LIMITS.get(emp_scheme, 14)

if max_shift_hours > scheme_limit:
    # Employee filtered out - incompatible with shift duration
    continue
```

**Example:**
- Demand: 12h shifts (22:00-10:00)
- Scheme P employees (9h cap) → **FILTERED OUT** by ICPMP
- Scheme A/B employees (14h/13h caps) → Eligible ✅

**Applies to:** demandBased only (outcomeBased validates post-assignment)

---

### 4.2 OT-Aware ICPMP (Scheme P Optimization)

**Location:** `src/preprocessing/icpmp_integration.py:235-280`

**Problem:** Scheme P part-time employees have 9h daily cap but can work OT:
- Normal: 9h × 4 days = 36h/week
- With OT: 9h × 6 days = 54h/week (allows 18h OT within 72h monthly cap)

**Solution:** `enableOtAwareIcpmp` flag (default: TRUE)

```python
# ICPMP employee count calculation
if scheme == 'P' and enable_ot_aware_icpmp:
    # Calculate capacity including OT hours
    weekly_capacity = (normal_hours + ot_capacity) / shift_duration
    # Example: (36h + 18h) / 9h = 6 shifts/week = 5.25 "days"
else:
    # Use pattern work days directly
    weekly_capacity = work_days_in_pattern
    # Example: DDDDDDOO → 6 work days
```

**Impact:**
- Scheme P with OT-aware: **40% fewer employees** needed
- Scheme A/B: **No change** (uses pattern work days)

**Test Results:**
```
Scheme P 6-day pattern (DDDDDD00):
- OT-aware DISABLED: 19 employees (conservative)
- OT-aware ENABLED:  12 employees (optimal) ← 37% reduction
```

**Applies to:** demandBased only (ICPMP is not used for outcomeBased)

---

### 4.3 Pattern-Aware Normal Hours Calculation

**Location:** `context/constraints/C2_mom_weekly_hours_pattern_aware.py:70-100`

**MOM Rule:** Weekly normal hours depend on **work days per week**:

| Work Days/Week | Normal Hours/Shift | Weekly Total |
|----------------|-------------------|--------------|
| 4 days | 11.0h | 44h |
| 5 days | 8.8h | 44h |
| 6 days | Days 1-5: 8.8h<br>Day 6: 0h (rest day pay) | 44h + rest day pay |

**Implementation:**

```python
def calculate_pattern_aware_normal_hours(gross, lunch, work_pattern, pattern_day):
    work_days_per_week = get_work_days_per_week(work_pattern)
    
    if work_days_per_week <= 4.5:
        return min(11.0, gross - lunch)  # 4-day pattern
        
    elif work_days_per_week <= 5.5:
        return min(8.8, gross - lunch)  # 5-day pattern
        
    else:
        # 6-day pattern: Check consecutive position
        consecutive_position = get_consecutive_work_position(work_pattern, pattern_day)
        if consecutive_position >= 6:
            return 0.0  # 6th consecutive day: rest day pay
        else:
            return min(8.8, gross - lunch)  # First 5 days
```

**Example: Scheme P 6-Day Pattern**
- Pattern: `['D','D','D','D','D','D','O']`
- Shift: 9h gross (8h normal after lunch)
- Days 1-5: 8.8h normal, 0h OT (under 8.8h cap)
- Day 6: 0h normal, 8h rest day pay, 0h OT (rest day)
- **Weekly: 44h normal + 8h rest day pay** ✅

**Applies to:** BOTH modes (demandBased: constraint, outcomeBased: validation)

---

### 4.4 APGD-D10 Special Exemption (Scheme A Only)

**Location:** `context/engine/time_utils.py:75-120`

**What is APGD-D10?**
- MOM special approval for security industry
- Allows Scheme A APO employees to work **6-7 days/week**
- Exempts from weekly 44h cap (uses monthly caps instead)
- Requires: `enableAPGD-D10: true` in requirement

**Detection Logic:**

```python
def is_apgd_d10_employee(employee: dict, requirement: dict = None) -> bool:
    """Check if employee qualifies for APGD-D10 treatment."""
    
    # Must be Scheme A
    emp_scheme = normalize_scheme(employee.get('scheme', 'A'))
    if emp_scheme != 'A':
        return False
    
    # Must be APO product
    if employee.get('productTypeId') != 'APO':
        return False
    
    # Must have APGD-D10 enabled in requirement
    if requirement and not requirement.get('enableAPGD-D10', False):
        return False
    
    return True
```

**Hour Calculation (APGD-D10):**

```python
# 6-day pattern: 12h shifts
# Days 1-5: 8.8h normal + 2.2h OT = 11h paid (1h lunch)
# Day 6: 0h normal + 3h OT + 8h rest day pay = 11h paid (1h lunch)
# Total: 44h normal + 14h OT + 8h rest day pay = 66h paid
```

**Applies to:** BOTH modes (Scheme A + APO + APGD flag enabled)

---

### 4.5 Proportional Scheme Distribution (demandBased)

**Location:** `src/preprocessing/icpmp_integration.py:538-580`

**Problem:** When ICPMP reduces 86 → 23 employees, maintain scheme proportions.

**Implementation:**

```python
# Input: 86 employees (60 Scheme A, 20 Scheme B, 6 Scheme P)
# Target: 23 employees

# Calculate proportions
scheme_counts = {'A': 60, 'B': 20, 'P': 6}
total = 86
target = 23

# Allocate proportionally
allocated = {
    'A': round(60/86 * 23) = 16,
    'B': round(20/86 * 23) = 5,
    'P': round(6/86 * 23) = 2
}

# Select top-scoring employees from each scheme group
selected_A = select_top_n(scheme_A_employees, 16)
selected_B = select_top_n(scheme_B_employees, 5)
selected_P = select_top_n(scheme_P_employees, 2)
```

**Result:** Maintains ~70% A, ~22% B, ~8% P ratio

**Applies to:** demandBased only (outcomeBased uses all input employees)

---

## 5. Comparison Table: Schemes Across Modes

| Feature | Scheme A | Scheme B | Scheme P | Mode |
|---------|----------|----------|----------|------|
| **Daily Cap** | 14h | 13h | 9h | Both |
| **Weekly Normal Cap** | 44h | 44h | 36h (44h with OT) | Both |
| **Monthly OT Cap** | 72h | 72h | 72h | Both |
| **ICPMP Filtering** | ✅ Yes | ✅ Yes | ✅ Yes | demandBased |
| **OT-Aware ICPMP** | ❌ No (uses pattern days) | ❌ No (uses pattern days) | ✅ Yes (uses hour capacity) | demandBased |
| **APGD-D10 Eligible** | ✅ Yes (if APO + flag) | ❌ No | ❌ No | Both |
| **6-7 Day Patterns** | ✅ Yes (with APGD-D10) | ❌ No (max 5 days) | ❌ No (max 6 days with OT) | Both |
| **Typical Employees** | CPL, SGT, SER | CVSO, AVSO | Part-time CVSO | - |

---

## 6. Code Locations Reference

### ICPMP Preprocessing (demandBased only)
```
src/preprocessing/icpmp_integration.py
├─ Lines 425-475: Scheme compatibility filter
├─ Lines 235-280: OT-aware ICPMP (Scheme P)
└─ Lines 538-580: Proportional scheme distribution
```

### CP-SAT Constraints (demandBased only)
```
context/constraints/
├─ C2_mom_weekly_hours_pattern_aware.py: Weekly 44h + Monthly 72h OT caps
├─ C6_daily_hour_cap.py: Daily caps (14h/13h/9h by scheme)
└─ C17_apgd_d10_monthly_hours.py: APGD-D10 exemption (Scheme A only)
```

### Template Validation (outcomeBased only)
```
src/roster_template_validator.py
├─ Lines 150-180: Daily hour cap validation
├─ Lines 200-250: Weekly 44h cap validation
└─ Lines 300-350: Monthly 72h OT cap validation
```

### Hour Calculation Utilities (Both modes)
```
context/engine/time_utils.py
├─ Lines 1-50: normalize_scheme(), is_apgd_d10_employee()
├─ Lines 150-250: calculate_apgd_d10_hours()
└─ Lines 300-400: calculate_mom_compliant_hours()
```

### Output Building (Both modes)
```
src/output_builder.py
├─ Lines 750-800: Scheme detection and hour breakdown
└─ Lines 1000-1050: MOM compliance aggregation
```

---

## 7. Input JSON Examples

### Example 1: demandBased with Mixed Schemes

```json
{
  "schemaVersion": "0.95",
  "rosteringBasis": "demandBased",
  "employees": [
    {
      "employeeId": "00001",
      "scheme": "Scheme A",
      "productTypeId": "APO",
      "rankId": "SER"
    },
    {
      "employeeId": "00002",
      "scheme": "Scheme B",
      "productTypeId": "CVSO",
      "rankId": "CPL"
    },
    {
      "employeeId": "00003",
      "scheme": "Scheme P",
      "productTypeId": "AVSO",
      "rankId": "SER"
    }
  ],
  "demandItems": [
    {
      "requirements": [
        {
          "requirementId": "R1",
          "productTypeId": "APO",
          "rankIds": ["SER"],
          "scheme": "Global",
          "workPattern": ["D","D","D","D","D","D","O"],
          "enableOtAwareIcpmp": true,
          "enableAPGD-D10": true
        }
      ],
      "shifts": [
        {
          "shiftCode": "D",
          "startTime": "22:00",
          "endTime": "10:00"
        }
      ]
    }
  ]
}
```

**Result:**
- Scheme P employees **filtered out** (9h cap < 12h shift)
- ICPMP selects minimal Scheme A employees
- APGD-D10 enabled: allows 6-day patterns
- OT-aware ICPMP: optimizes employee count

### Example 2: outcomeBased Template Validation

```json
{
  "schemaVersion": "0.95",
  "rosteringBasis": "outcomeBased",
  "fixedRotationOffset": "ouOffsets",
  "ouOffsets": [0, 1, 2],
  "employees": [
    {
      "employeeId": "00001",
      "scheme": "Scheme P"
    }
  ],
  "demandItems": [
    {
      "assignments": [
        {
          "employeeId": "00001",
          "shiftCode": "D",
          "startDateTime": "2026-05-01T22:00:00",
          "endDateTime": "2026-05-02T10:00:00"
        }
      ]
    }
  ]
}
```

**Result:**
- **INFEASIBLE** - 12h shift exceeds Scheme P 9h cap
- Violation details returned in output
- No optimization performed

---

## 8. Key Takeaways

### Applicability Matrix

| Technique | demandBased | outcomeBased |
|-----------|-------------|--------------|
| **Daily Hour Caps** | ✅ Hard constraint (C6) | ✅ Validation check |
| **Weekly 44h Cap** | ✅ Hard constraint (C2) | ✅ Validation check |
| **Monthly 72h OT Cap** | ✅ Hard constraint (C2) | ✅ Validation check |
| **ICPMP Scheme Filter** | ✅ Preprocessing | ❌ N/A (uses all employees) |
| **OT-Aware ICPMP** | ✅ Scheme P only | ❌ N/A (no ICPMP) |
| **APGD-D10 Exemption** | ✅ Scheme A + APO | ✅ Scheme A + APO |
| **Proportional Distribution** | ✅ Maintains ratios | ❌ N/A (no selection) |
| **Pattern-Aware Hours** | ✅ Calculation logic | ✅ Calculation logic |

### Performance Impact

**demandBased (with ICPMP):**
- Scheme filtering: ~73% employee reduction typical
- Solve time: 60-70s → 1-2s (3.7x smaller problem)
- OT-aware ICPMP: ~40% fewer Scheme P employees

**outcomeBased (template):**
- No optimization: < 1 second validation
- All employees included: no filtering
- Strict validation: any violation = INFEASIBLE

### Recommended Practices

1. **Use demandBased** for:
   - Optimizing employee count
   - Mixed schemes requiring OT optimization
   - Large employee pools (50+ employees)

2. **Use outcomeBased** for:
   - Validating pre-planned templates
   - Fixed rosters with specific assignments
   - Quick MOM compliance checks

3. **Scheme Selection:**
   - Scheme A: Standard security officers (CPL, SGT, SER)
   - Scheme B: Full-time civilians (CVSO, AVSO with 13h cap)
   - Scheme P: Part-time staff (use OT-aware ICPMP for optimization)

4. **APGD-D10 Usage:**
   - Only for Scheme A + APO employees
   - Requires MOM approval in practice
   - Enable via `enableAPGD-D10: true` flag

---

## 9. Troubleshooting

### Issue: Scheme P employees not selected

**Cause:** Shift duration exceeds 9h cap  
**Solution:** 
- Check shift times (22:00-10:00 = 12h > 9h)
- Use shorter shifts for Scheme P (e.g., 22:00-07:00 = 9h)
- Or use Scheme A/B employees for 12h shifts

### Issue: Too many employees needed

**Cause:** OT-aware ICPMP disabled for Scheme P  
**Solution:**
- Set `enableOtAwareIcpmp: true` in requirement
- Reduces Scheme P count by ~40%

### Issue: APGD-D10 not working

**Cause:** Missing requirements  
**Solution:**
- Verify: `scheme: "Scheme A"` + `productTypeId: "APO"` + `enableAPGD-D10: true`
- Check employee meets all three criteria

### Issue: Scheme proportions not maintained

**Cause:** ICPMP proportional distribution disabled  
**Solution:**
- Ensure ICPMP is enabled (demandBased mode)
- Check sufficient employees in each scheme group
- Review ICPMP logs for distribution details

---

## 10. Future Enhancements

1. **Scheme-Specific Constraints:**
   - Custom weekly caps per scheme (not just 44h)
   - Part-time flexibility rules for Scheme P

2. **Multi-Scheme Requirements:**
   - Requirements accepting multiple schemes explicitly
   - Scheme preference weights in ICPMP scoring

3. **Dynamic Scheme Detection:**
   - Auto-detect scheme from employee properties
   - Validate scheme-product compatibility rules

4. **Enhanced APGD-D10:**
   - Automatic MOM approval tracking
   - APGD-D10 usage statistics and limits

---

**Last Updated:** 2025-12-21  
**Related Documents:**
- [DOUBLE_ROTATION_BUG_FIX_PERMANENT.md](DOUBLE_ROTATION_BUG_FIX_PERMANENT.md)
- [implementation_docs/WORKING_HOURS_MODEL.md](implementation_docs/WORKING_HOURS_MODEL.md)
- [context/glossary.md](context/glossary.md)
