# Hour Calculation Methods Guide

## Overview

NGRS Solver supports three distinct methods for calculating normal hours and overtime hours for employees. Each method serves different employment scenarios and contractual arrangements.

Starting from **v0.98**, we've introduced clearer naming conventions while maintaining full backward compatibility with legacy names.

---

## Method Comparison

| Method | OT Calculation Logic | Best For | Currently Used By |
|--------|---------------------|----------|-------------------|
| **weeklyThreshold** | Fixed 44h/week cap | Standard workers, MOM compliance | **SO (Security Officer) - Scheme A**<br>• All employee types<br>• All ranks |
| **dailyProrated** | Daily threshold = contract ÷ work days | Fixed monthly contracts | **SO (Security Officer) - Scheme B**<br>• All employee types<br>• All ranks |
| **monthlyCumulative** | Bank hours until contract exhausted | APGD-D10, salaried staff | **APO (Auxiliary Police) - Scheme A**<br>• Both Local & Foreigner<br>• All ranks<br><br>**Default Rule** (standardMonthlyHours)<br>• Fallback for unconfigured combinations |

---

## 1. weeklyThreshold (Weekly Threshold Method)

**Legacy name**: `weekly44h`  
**New name**: `weeklyThreshold`

### How It Works

Uses a **fixed 44-hour weekly threshold** based on calendar weeks (Monday-Sunday). Any hours worked beyond 44 hours in a calendar week count as overtime.

### Calculation Formula

```
For each calendar week:
  If total_hours_in_week <= 44h:
    normal_hours = total_hours_in_week
    ot_hours = 0
  Else:
    normal_hours = 44h
    ot_hours = total_hours_in_week - 44h
```

### Example (March 2026, 31 days)

```
Week 1 (Mon-Sun):
├─ Mon-Fri: 12h × 5 days = 60h
│  ├─ Normal: 44h (capped at weekly threshold)
│  └─ OT: 16h (60h - 44h)
└─ Sat-Sun: Off

Week 2 (Mon-Sun):
├─ Mon-Wed: 12h × 3 days = 36h
│  ├─ Normal: 36h (under 44h threshold)
│  └─ OT: 0h
└─ Thu-Sun: Off

Month Total:
├─ Gross: 96h
├─ Normal: 80h (44h + 36h)
└─ OT: 16h
```

### When to Use

- **Standard security officers** on Scheme A
- **Part-time workers** with weekly hour thresholds
- Any role where **weekly overtime thresholds** apply regardless of monthly contract hours
- **MOM compliance** scenarios requiring weekly caps

### JSON Configuration

```json
{
  "id": "SO_A",
  "description": "Security Officer Scheme A",
  "hourCalculationMethod": "weeklyThreshold",
  "applicableTo": {
    "schemes": ["A"],
    "productTypeIds": ["SO"]
  },
  "valuesByMonthLength": {
    "31": {
      "minimumContractualHours": 195,
      "maxOvertimeHours": 72,
      "totalMaxHours": 267
    }
  }
}
```

---

## 2. dailyProrated (Daily Proration Method)

**Legacy name**: `dailyContractual`  
**New name**: `dailyProrated`

### How It Works

Calculates a **daily normal hour threshold** by dividing `minimumContractualHours` by the number of expected work days in the month. Each day, hours up to this threshold count as normal; any excess is overtime.

### Calculation Formula

```
Daily threshold = minimumContractualHours ÷ work_days_in_month

For each work day:
  net_hours = gross_hours - lunch_break
  If net_hours <= daily_threshold:
    normal_hours = net_hours
    ot_hours = 0
  Else:
    normal_hours = daily_threshold
    ot_hours = net_hours - daily_threshold
```

### Example (March 2026, 31 days, 27 expected work days)

```
Employee Configuration:
├─ minimumContractualHours: 231h
└─ Daily threshold: 231h ÷ 27 days = 8.56h per day

Day 1 (12h shift):
├─ Gross: 12.0h
├─ Lunch: 1.0h
├─ Net: 11.0h
├─ Normal: 8.56h (threshold)
└─ OT: 2.44h (11.0h - 8.56h)

Day 2 (12h shift):
├─ Same calculation
├─ Normal: 8.56h
└─ OT: 2.44h

Work 22 days × 12h = 264h total:
├─ Gross: 264h
├─ Lunch: 22h (1h per day)
├─ Net: 242h
├─ Normal: 22 × 8.56h = 188.32h
└─ OT: 22 × 2.44h = 53.68h
```

### When to Use

- Employees with **fixed monthly contracts** (e.g., 231 hours/month)
- Scenarios where **daily overtime** should be calculated based on average contractual hours per day
- **Security Officer Scheme B** configurations
- Jobs where monthly hours are clearly defined upfront

### JSON Configuration

```json
{
  "id": "SO_B",
  "description": "Security Officer Scheme B - Daily proration",
  "hourCalculationMethod": "dailyProrated",
  "applicableTo": {
    "schemes": ["B"],
    "productTypeIds": ["SO"]
  },
  "valuesByMonthLength": {
    "31": {
      "minimumContractualHours": 195,
      "maxOvertimeHours": 72,
      "totalMaxHours": 267
    }
  }
}
```

---

## 3. monthlyCumulative (Cumulative Monthly Method)

**Legacy name**: `monthlyContractual`  
**New name**: `monthlyCumulative`

### How It Works

Treats the first `minimumContractualHours` worked in the month as normal hours, then **everything after that as overtime**. This is a **banking system** where hours accumulate throughout the month.

**Key distinction**: Does NOT use daily thresholds. The monthly threshold applies cumulatively across all days.

### Calculation Formula

```
cumulative_normal = 0
For each work day in chronological order:
  net_hours = gross_hours - lunch_break
  
  remaining_normal_budget = minimumContractualHours - cumulative_normal
  
  If remaining_normal_budget > 0:
    normal_this_day = min(net_hours, remaining_normal_budget)
    ot_this_day = net_hours - normal_this_day
    cumulative_normal += normal_this_day
  Else:
    normal_this_day = 0
    ot_this_day = net_hours  # All OT (budget exhausted)
```

### Example (March 2026, 31 days, 27 expected work days)

```
Employee Configuration:
└─ minimumContractualHours: 231h (monthly threshold)

Days 1-20 (12h shifts):
├─ Day 1: 11h net → 11h normal, 0h OT (cumulative: 11h)
├─ Day 2: 11h net → 11h normal, 0h OT (cumulative: 22h)
├─ ...
├─ Day 20: 11h net → 11h normal, 0h OT (cumulative: 220h)
└─ Total: 220h normal, 0h OT

Day 21 (12h shift):
├─ 11h net
├─ Remaining budget: 231h - 220h = 11h
├─ Normal: 11h (exactly exhausts budget)
└─ OT: 0h

Day 22 (12h shift):
├─ 11h net
├─ Remaining budget: 231h - 231h = 0h
├─ Normal: 0h (budget exhausted)
└─ OT: 11h (all overtime)

Days 23-27 (12h shifts):
├─ All hours are OT (budget already exhausted)
└─ 5 days × 11h = 55h OT

Month Total (27 work days):
├─ Gross: 27 × 12h = 324h
├─ Lunch: 27 × 1h = 27h
├─ Net: 297h
├─ Normal: 231h (exactly minimumContractualHours)
└─ OT: 66h (297h - 231h)
```

### When to Use

- **APGD-D10 employees** (Auxiliary Police Officers)
- **Salaried staff** with fixed monthly hour commitments
- Roles where **monthly hour banking** is the contractual norm
- Scenarios requiring **cumulative tracking** of normal hours throughout the month

### JSON Configuration

```json
{
  "id": "APO_A",
  "description": "Auxiliary Police Officer Scheme A - APGD-D10",
  "hourCalculationMethod": "monthlyCumulative",
  "applicableTo": {
    "schemes": ["A"],
    "productTypeIds": ["APO"],
    "employeeType": "Local"
  },
  "valuesByMonthLength": {
    "31": {
      "minimumContractualHours": 246,
      "maxOvertimeHours": 72
    }
  }
}
```

---

## Comparison Example: Same Roster, Different Methods

### Scenario
- **Month**: March 2026 (31 days)
- **Expected work days**: 27 days
- **Actual work**: 22 days × 12h shifts
- **Gross hours**: 264h (22 days × 12h)
- **Lunch deduction**: 22h (1h per 12h shift)
- **Net hours**: 242h

### Results by Method

| Method | minimumContractualHours | Normal Hours | OT Hours | Logic |
|--------|------------------------|--------------|----------|-------|
| **weeklyThreshold** | 195h | ~176h | ~66h | Weekly 44h cap applied across 4-5 weeks |
| **dailyProrated** | 195h | ~163h | ~79h | 195h ÷ 27 days = 7.22h/day threshold |
| **monthlyCumulative** | 195h | 195h | 47h | First 195h = normal, rest = OT |

**Key Insight**: The same roster produces different normal/OT splits depending on the calculation method. Choose the method that aligns with your contractual obligations.

---

## Migration Guide (v0.97 → v0.98)

### Option 1: Use New Names (Recommended)

Update your `monthlyHourLimits` configurations:

```json
{
  "hourCalculationMethod": "weeklyThreshold",    // was: "weekly44h"
  "hourCalculationMethod": "dailyProrated",      // was: "dailyContractual"
  "hourCalculationMethod": "monthlyCumulative"   // was: "monthlyContractual"
}
```

### Option 2: Keep Legacy Names (Backward Compatible)

No changes required! The solver still accepts:
- `"weekly44h"`
- `"dailyContractual"`
- `"monthlyContractual"`

These are automatically mapped to the new canonical names internally.

---

## API Reference

### monthlyHourLimits Schema

```json
{
  "id": "string",
  "description": "string",
  "enforcement": "hard",
  "hourCalculationMethod": "weeklyThreshold | dailyProrated | monthlyCumulative",
  "applicableTo": {
    "employeeType": "All | Local | Foreigner",
    "rankIds": ["string"],
    "schemes": ["A" | "B" | "P"],
    "productTypeIds": ["SO" | "APO" | "string"]
  },
  "valuesByMonthLength": {
    "28": {
      "minimumContractualHours": 176,
      "maxOvertimeHours": 72,
      "totalMaxHours": 248
    },
    "29": { "..." },
    "30": { "..." },
    "31": { "..." }
  }
}
```

### Field Definitions

| Field | Type | Description |
|-------|------|-------------|
| `hourCalculationMethod` | string | Method for splitting normal/OT hours |
| `minimumContractualHours` | number | Monthly normal hour threshold (varies by method) |
| `maxOvertimeHours` | number | Optional: Max OT hours per month (default: 72) |
| `totalMaxHours` | number | Optional: Total work hours cap (normal + OT) |

---

## Troubleshooting

### Q: Which method should I use for my organization?

**A:** 
- **Security Officers (Scheme A)**: Use `weeklyThreshold` for MOM compliance
- **Security Officers (Scheme B)**: Use `dailyProrated` if contracts specify monthly hours
- **Auxiliary Police (APGD-D10)**: Use `monthlyCumulative` for hour banking
- **Part-time workers**: Use `weeklyThreshold` or consult Scheme P documentation

### Q: Can I mix methods within the same roster?

**A:** Yes! Different employee groups can use different methods. The solver matches employees to rules based on:
- `productTypeId` (SO, APO, etc.)
- `scheme` (A, B, P)
- `employeeType` (Local, Foreigner)
- `rankIds`

### Q: What happens if minimumContractualHours is not met?

**A:** The solver treats this as a constraint violation. Employees will be scheduled to work enough hours to meet their contract, subject to other constraints (daily caps, consecutive day limits, etc.).

### Q: How does totalMaxHours interact with the calculation method?

**A:** `totalMaxHours` is a **hard cap** applied AFTER normal/OT splitting:
```
normal_hours + ot_hours <= totalMaxHours
```
This prevents excessive overtime regardless of the calculation method.

---

## Related Documentation

- [C17 Constraint Implementation](../C17_TOTALMAXHOURS_IMPLEMENTATION.md) - totalMaxHours enforcement
- [MOM Compliance Guide](../context/domain/mom_compliance.md) - Singapore labor regulations
- [Scheme P Documentation](../context/domain/scheme_p.md) - Part-time worker calculations
- [Constraint Configuration](../CONSTRAINT_JSON_FORMAT_v098.md) - JSON schema reference

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v0.98 | 2026-02-27 | Introduced new naming convention (weeklyThreshold, dailyProrated, monthlyCumulative) with backward compatibility |
| v0.95 | 2026-01-15 | Added `hourCalculationMethod` field to monthlyHourLimits |
| v0.70 | 2025-12-01 | Initial implementation with `calculationMethod` (deprecated) |

---

**Last Updated**: 27 February 2026  
**Maintained By**: NGRS Solver Team
