# Hour Calculation & Rest Day Pay Workflow

## Overview
This document explains how normal hours, overtime hours, and rest day pay are calculated, especially for APGD-D10 employees (Scheme A + APO + COR/SGT ranks).

---

## 1. Overall Workflow

```mermaid
flowchart TD
    Start([Assignment Created]) --> CheckScheme{Employee Scheme?}
    
    CheckScheme -->|Scheme A + APO| CheckAPGD{Is APGD-D10?}
    CheckScheme -->|Scheme P| SchemeP[Use Scheme P Rules]
    CheckScheme -->|Other| Standard[Use Standard MOM Rules]
    
    CheckAPGD -->|Yes| APGD[Calculate APGD-D10 Hours]
    CheckAPGD -->|No| Standard
    
    APGD --> Position[Determine Work Day Position]
    Position --> CalcHours[Calculate Hours Based on Position]
    CalcHours --> End([Return Hour Breakdown])
    
    SchemeP --> SchemeCalc[Calculate Scheme P Hours]
    SchemeCalc --> End
    
    Standard --> StdCalc[Calculate Standard Hours]
    StdCalc --> End
```

---

## 2. APGD-D10 Hour Calculation (Detailed)

```mermaid
flowchart TD
    Start([APGD-D10 Assignment]) --> GetBasics[Get Basic Info:<br/>• Start/End DateTime<br/>• Employee ID<br/>• Assignment Date]
    
    GetBasics --> CalcGross[Calculate Gross Hours<br/>gross = end_time - start_time]
    
    CalcGross --> CalcLunch{Gross >= 6h?}
    CalcLunch -->|Yes| Lunch1[Deduct 1h lunch]
    CalcLunch -->|No| NoLunch[No lunch deduction]
    
    Lunch1 --> NetHours[Net Hours = gross - lunch]
    NoLunch --> NetHours
    
    NetHours --> CountPos[Count Work Day Position<br/>in Calendar Week]
    
    CountPos --> Explain1[<b>Key Function:</b><br/>count_work_day_position_in_week]
    Explain1 --> Logic1[Looks at all assignments<br/>in same calendar week<br/>Mon-Sun]
    Logic1 --> Logic2[Counts work days BEFORE<br/>current date excluding OFF 'O']
    Logic2 --> Logic3[Position = count + 1]
    
    Logic3 --> CheckPos{Work Day Position?}
    
    CheckPos -->|Position 1-5| Days15[<b>Days 1-5:</b><br/>Normal Working Days]
    CheckPos -->|Position 6+| Days6Plus[<b>Day 6+:</b><br/>Rest Day Pay Triggered]
    
    Days15 --> Calc15Gross{Net Hours?}
    Calc15Gross -->|<= 8.8h| Norm15A[normal = net<br/>OT = 0]
    Calc15Gross -->|> 8.8h| Norm15B[normal = 8.8h<br/>OT = net - 8.8h]
    
    Norm15A --> RDP15[Rest Day Pay = 0]
    Norm15B --> RDP15
    
    Days6Plus --> Calc6Gross[<b>Rest Day Pay Logic:</b><br/>normal = 0.0h<br/>rest_day_pay = 1<br/>8h paid at normal rate]
    
    Calc6Gross --> Calc6OT{Net Hours?}
    Calc6OT -->|<= 8h| OT6A[OT = net - 8h]
    Calc6OT -->|> 8h| OT6B[OT = net - 8h]
    
    OT6A --> Result6[Return:<br/>• normal = 0h<br/>• OT = net - 8h<br/>• RDP = 1 8h]
    OT6B --> Result6
    
    RDP15 --> Result15[Return:<br/>• normal hours<br/>• OT hours<br/>• RDP = 0]
    
    Result15 --> End([Hour Breakdown Ready])
    Result6 --> End
```

---

## 3. Work Day Position Counting Logic

```mermaid
flowchart TD
    Start([count_work_day_position_in_week]) --> Input[Input:<br/>• employee_id<br/>• current_date<br/>• all_assignments]
    
    Input --> GetWeek[Determine Calendar Week<br/>Monday to Sunday]
    
    GetWeek --> Filter[Filter assignments:<br/>1. Same employee<br/>2. Same calendar week<br/>3. Status = ASSIGNED or OFF_DAY]
    
    Filter --> Loop{For each assignment<br/>in filtered list}
    
    Loop -->|Has date + shiftCode| CheckOff{shiftCode == 'O'?}
    Loop -->|End of list| Count[Count all work dates]
    
    CheckOff -->|Yes| Skip[Skip - OFF day]
    CheckOff -->|No| Add[Add to work_dates list]
    
    Skip --> Loop
    Add --> Loop
    
    Count --> Sort[Sort work_dates chronologically]
    
    Sort --> Find{Current date<br/>in work_dates?}
    
    Find -->|Yes| GetIndex[position = index + 1]
    Find -->|No| Default[position = 1<br/>default fallback]
    
    GetIndex --> Return([Return position 1-7])
    Default --> Return
```

---

## 4. Example Scenarios

### Scenario A: Standard 5-Day Week (Mon-Fri work, Sat-Sun OFF)

```
Week of Jan 5-11, 2026:

Mon Jan 5:  Position 1 → 8.8h normal + 2.2h OT + 0 RDP
Tue Jan 6:  Position 2 → 8.8h normal + 2.2h OT + 0 RDP
Wed Jan 7:  Position 3 → 8.8h normal + 2.2h OT + 0 RDP
Thu Jan 8:  Position 4 → 8.8h normal + 2.2h OT + 0 RDP
Fri Jan 9:  Position 5 → 8.8h normal + 2.2h OT + 0 RDP
Sat Jan 10: OFF_DAY (not counted)
Sun Jan 11: OFF_DAY (not counted)

Weekly Total: 44.0h normal + 11.0h OT
✅ MOM Compliant: 44h ≤ 44h cap
```

### Scenario B: 6-Day Week (Mon-Sat work, Sun OFF)

```
Week of Jan 5-11, 2026:

Mon Jan 5:  Position 1 → 8.8h normal + 2.2h OT + 0 RDP
Tue Jan 6:  Position 2 → 8.8h normal + 2.2h OT + 0 RDP
Wed Jan 7:  Position 3 → 8.8h normal + 2.2h OT + 0 RDP
Thu Jan 8:  Position 4 → 8.8h normal + 2.2h OT + 0 RDP
Fri Jan 9:  Position 5 → 8.8h normal + 2.2h OT + 0 RDP
Sat Jan 10: Position 6 → 0.0h normal + 3.0h OT + 1 RDP (8h)
Sun Jan 11: OFF_DAY (not counted)

Weekly Total: 44.0h normal + 14.0h OT + 8h RDP
✅ MOM Compliant: 44h ≤ 44h cap
✅ Day 6 gets Rest Day Pay instead of normal hours
```

### Scenario C: 7-Day Week (All days work, APGD-D10)

```
Week of Jan 5-11, 2026:

Mon Jan 5:  Position 1 → 8.8h normal + 2.2h OT + 0 RDP
Tue Jan 6:  Position 2 → 8.8h normal + 2.2h OT + 0 RDP
Wed Jan 7:  Position 3 → 8.8h normal + 2.2h OT + 0 RDP
Thu Jan 8:  Position 4 → 8.8h normal + 2.2h OT + 0 RDP
Fri Jan 9:  Position 5 → 8.8h normal + 2.2h OT + 0 RDP
Sat Jan 10: Position 6 → 0.0h normal + 3.0h OT + 1 RDP (8h)
Sun Jan 11: Position 7 → 0.0h normal + 3.0h OT + 1 RDP (8h)

Weekly Total: 44.0h normal + 17.0h OT + 16h RDP (2 days)
✅ MOM Compliant: 44h ≤ 44h cap
✅ Days 6-7 get Rest Day Pay
```

### Scenario D: 8 Consecutive Days (APGD-D10 Special Approval)

```
Week 1 (Jan 5-11, 2026):
Mon Jan 5:  Position 1 → 8.8h normal + 2.2h OT + 0 RDP
Tue Jan 6:  Position 2 → 8.8h normal + 2.2h OT + 0 RDP
Wed Jan 7:  Position 3 → 8.8h normal + 2.2h OT + 0 RDP
Thu Jan 8:  Position 4 → 8.8h normal + 2.2h OT + 0 RDP
Fri Jan 9:  Position 5 → 8.8h normal + 2.2h OT + 0 RDP
Sat Jan 10: Position 6 → 0.0h normal + 3.0h OT + 1 RDP (8h)
Sun Jan 11: Position 7 → 0.0h normal + 3.0h OT + 1 RDP (8h)

Week 1 Total: 44.0h normal + 17.0h OT + 16h RDP

Week 2 (Jan 12-18, 2026):
Mon Jan 12: Position 1 → 8.8h normal + 2.2h OT + 0 RDP  ← Day 8 consecutive!
Tue Jan 13: OFF_DAY (mandatory rest after 8 days)

This is the 8th consecutive day spanning two calendar weeks.
Weekly OFF requirement relaxed for APGD-D10.
```

---

## 5. Issue Found: Jan 1-4 Showing Incorrect Hours

### Problem
```
Jan 1-4 (Thu-Sun) showing:
  Each day: 11.0h normal + 0h OT

Expected for APGD-D10:
  Each day: 8.8h normal + 2.2h OT (for 12h gross shifts)
  OR if day 6+: 0h normal + 3h OT + 1 RDP
```

### Possible Causes

```mermaid
flowchart TD
    Issue([Jan 1-4: 11.0h normal, 0h OT]) --> Check1{Are these being<br/>calculated as APGD-D10?}
    
    Check1 -->|No| Cause1[Not detected as APGD-D10<br/>Using standard calculation]
    Check1 -->|Yes| Check2{Is position being<br/>counted correctly?}
    
    Check2 -->|No| Cause2[Position counting issue<br/>Missing OFF_DAY context]
    Check2 -->|Yes| Check3{Is it a partial week?}
    
    Check3 -->|Yes| Cause3[Partial week at start<br/>Different calculation logic?]
    Check3 -->|No| Cause4[Unknown calculation issue]
    
    Cause1 --> Fix1[Verify is_apgd_d10_employee<br/>detection in output_builder]
    Cause2 --> Fix2[Check all_assignments<br/>passed to hour calculation]
    Cause3 --> Fix3[Review partial week<br/>hour calculation logic]
    Cause4 --> Fix4[Debug calculate_apgd_d10_hours<br/>for these specific dates]
```

### Investigation Steps

1. **Check APGD-D10 Detection**:
   ```python
   # In output_builder.py
   is_apgd = is_apgd_d10_employee(employee, requirement)
   # Should be True for Scheme A + APO employees
   ```

2. **Check Assignment Context**:
   ```python
   # Hour calculation should receive all assignments
   hours_dict = calculate_apgd_d10_hours(
       start_dt=start_dt,
       end_dt=end_dt,
       employee_id=emp_id,
       assignment_date_obj=date_obj,
       all_assignments=assignments,  # ← Must include ALL assignments!
       employee_dict=employee
   )
   ```

3. **Check Partial Week Handling**:
   ```python
   # Jan 1-4 is a partial week (Thu-Sun, only 4 days)
   # Week starts Jan 1 (Thu), not a full Mon-Sun week
   # Position counting might be affected
   ```

4. **Verify Gross/Net Calculation**:
   ```python
   # For 12h shift (08:00-20:00):
   # gross = 12.0h
   # lunch = 1.0h (if gross >= 6h)
   # net = 11.0h
   # 
   # For APGD-D10 day 1-5:
   # normal = 8.8h (fixed cap)
   # OT = 11.0 - 8.8 = 2.2h
   ```

---

## 6. Constraint Logic Impact on Hours

### C2: Weekly Normal Hours Cap

```mermaid
flowchart LR
    C2[C2 Constraint] --> Logic{Pattern Length?}
    
    Logic -->|= 7| Weeks7[Use calendar weeks]
    Logic -->|≠ 7| Weeks6[Use calendar weeks]
    
    Weeks7 --> Count7[Days 1-5: Count toward 44h<br/>Days 6-7: Don't count 0h normal]
    Weeks6 --> Count6[Days 1-5: Count toward 44h<br/>Day 6+: Don't count 0h normal]
    
    Count7 --> Allow7[Allows 7 work days<br/>44h + RDP]
    Count6 --> Allow6[Allows 6 work days<br/>44h + RDP]
```

### C5: Minimum OFF Days Per Week

```mermaid
flowchart LR
    C5[C5 Constraint] --> Check{Is APGD-D10?}
    
    Check -->|Yes + 8-day approval| Window9[Use 9-day windows<br/>Max 8 work days]
    Check -->|No| Window7[Use 7-day windows<br/>Max 6 work days]
    
    Window9 --> Result9[Allows 8 consecutive<br/>across 2 weeks]
    Window7 --> Result7[Allows 6 consecutive<br/>within 1 week]
```

---

## 7. Key Functions Reference

| Function | Location | Purpose |
|----------|----------|---------|
| `calculate_apgd_d10_hours()` | `context/engine/time_utils.py` | Main APGD-D10 hour calculator |
| `count_work_day_position_in_week()` | `context/engine/time_utils.py` | Determines position (1-7) in calendar week |
| `is_apgd_d10_employee()` | `context/engine/time_utils.py` | Detects Scheme A + APO employees |
| `_group_dates_by_week()` | `context/engine/cpsat_template_generator.py` | Groups dates into Mon-Sun weeks |

---

## 8. Next Steps for Debugging Jan 1-4 Issue

1. **Add debug logging** to trace hour calculation for these dates
2. **Check if partial week** (4 days) triggers different logic
3. **Verify all_assignments** includes OFF_DAY entries for position counting
4. **Confirm APGD-D10 detection** is working in output builder
5. **Test with full week** starting Monday to compare behavior

---

## Appendix: APGD-D10 Rules Summary

| Aspect | Standard | APGD-D10 |
|--------|----------|----------|
| Max Consecutive Days | 12 | 8 |
| Weekly Normal Cap | 44h | 44h |
| Monthly OT Cap | 72h | 144h (foreign COR/SGT)<br/>246h total inc. normal |
| Days 1-5 Hours | 8.8h normal + OT | 8.8h normal + OT |
| Day 6+ Hours | Not typical | 0h normal + 8h RDP + OT |
| Weekly OFF | Required in 7 days | Flexible for 8 days |
| Schemes | All | Scheme A only |
| Products | All | APO only |
| Ranks | All | COR, SGT (foreign) |
