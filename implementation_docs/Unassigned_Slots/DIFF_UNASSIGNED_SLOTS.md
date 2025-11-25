# Code Changes Diff - Unassigned Slots Implementation

## File: context/engine/solver_engine.py

### Change 1: Added Unassigned Slot Variables (Line ~70)

```diff
     print(f"[build_model] ✓ Created {len(x)} decision variables")
     
+    # ========== NEW: UNASSIGNED SLOT VARIABLES ==========
+    print(f"\n[build_model] Creating unassigned slot variables...")
+    unassigned = {}
+    for slot in slots:
+        unassigned[slot.slot_id] = model.NewBoolVar(f"unassigned_slot_{slot.slot_id}")
+    
+    print(f"  ✓ Created {len(unassigned)} unassigned slot variables")
+    
     # ========== CONSTRAINT 1: HEADCOUNT SATISFACTION ==========
```

---

### Change 2: Modified Headcount Constraints (Line ~78)

```diff
-    # ========== CONSTRAINT 1: HEADCOUNT SATISFACTION ==========
-    print(f"\n[build_model] Adding headcount constraints...")
+    # ========== CONSTRAINT 1: HEADCOUNT SATISFACTION (MODIFIED) ==========
+    print(f"\n[build_model] Adding headcount constraints (with unassigned option)...")
     headcount_constraints = 0
     for slot in slots:
-        # Sum assignments for this slot must equal headcount
+        # Sum assignments for this slot must equal headcount OR slot is marked unassigned
         # Only include employees that are whitelisted for this slot
         slot_assignments = [x[(slot.slot_id, emp.get('employeeId'))] 
                            for emp in employees 
                            if (slot.slot_id, emp.get('employeeId')) in x]
-        if slot_assignments:  # Only add constraint if there are valid employees
-            model.Add(sum(slot_assignments) == slot.headcount)
+        
+        if slot_assignments:  # Only add constraint if there are valid employees
+            # MODIFIED: Either meet headcount OR mark slot as unassigned
+            # sum(assignments) + unassigned[slot_id] == headcount
+            model.Add(sum(slot_assignments) + unassigned[slot.slot_id] == slot.headcount)
             headcount_constraints += 1
+        else:
+            # No valid employees for this slot - must be marked unassigned
+            model.Add(unassigned[slot.slot_id] == 1)
+            headcount_constraints += 1
     
-    print(f"  ✓ Added {headcount_constraints} headcount constraints\n")
+    print(f"  ✓ Added {headcount_constraints} headcount constraints (allowing unassigned)\n")
```

---

### Change 3: Added Total Unassigned Counter & Changed Objective (Line ~108)

```diff
     print(f"  ✓ Added {one_per_day_constraints} one-per-day constraints\n")
     
-    # ========== OBJECTIVE FUNCTION ==========
-    # Maximize total assignments (feasibility objective)
-    all_assignments = list(x.values())
-    if all_assignments:
-        model.Maximize(sum(all_assignments))
+    # ========== AGGREGATE UNASSIGNED SLOTS ==========
+    print(f"[build_model] Creating total unassigned counter...")
+    total_unassigned = model.NewIntVar(0, len(slots), "total_unassigned")
+    model.Add(total_unassigned == sum(unassigned[slot.slot_id] for slot in slots))
+    print(f"  ✓ Created total_unassigned variable (range: 0-{len(slots)})\n")
+    
+    # ========== OBJECTIVE FUNCTION (MODIFIED) ==========
+    # PRIMARY: Minimize unassigned slots
+    # SECONDARY: Soft constraints will be added by constraint modules
+    # Use a large multiplier to prioritize minimizing unassigned slots
+    BIG_MULTIPLIER = 1_000_000
+    
+    # For now, just minimize unassigned slots
+    # Soft constraints can be integrated later by adding their penalty terms
+    print(f"[build_model] Setting objective: Minimize unassigned slots")
+    model.Minimize(BIG_MULTIPLIER * total_unassigned)
+    print(f"  Priority: {BIG_MULTIPLIER:,} × unassigned_slots\n")
     
-    print(f"[build_model] ✓ Added objective: Maximize assignments\n")
-    
     # Store model artifacts in context for later extraction
     ctx['x'] = x
+    ctx['unassigned'] = unassigned
+    ctx['total_unassigned'] = total_unassigned
     ctx['model'] = model
     ctx['solver'] = None  # Will be set after solving
```

---

### Change 4: Enhanced Assignment Extraction (Line ~160)

```diff
 def extract_assignments(ctx, solver) -> list:
     """Extract assignments from solver solution.
     
     Args:
-        ctx: Context dict with slots, employees, x (decision variables)
+        ctx: Context dict with slots, employees, x (decision variables), unassigned variables
         solver: CpSolver instance after solving
     
     Returns:
-        List of assignment dicts in output format
+        List of assignment dicts in output format (includes both assigned and unassigned slots)
     """
     assignments = []
     x = ctx.get('x', {})
+    unassigned = ctx.get('unassigned', {})
     slots = ctx.get('slots', [])
     employees_map = {emp.get('employeeId'): emp for emp in ctx.get('employees', [])}
     
     print(f"[extract_assignments] Extracting assignments from solution...")
     
+    assigned_count = 0
+    unassigned_count = 0
+    
     for slot in slots:
+        slot_assigned = False
+        
+        # Check if any employee is assigned to this slot
         for emp_id, emp in employees_map.items():
             var_key = (slot.slot_id, emp_id)
             if var_key in x:
                 # Check if this variable is assigned in the solution
                 if solver.Value(x[var_key]) == 1:
                     assignment = {
                         "assignmentId": f"{slot.demandId}-{slot.date.isoformat()}-{slot.shiftCode}-{emp_id}",
                         "demandId": slot.demandId,
                         "date": slot.date.isoformat(),
                         "shiftId": slot.shiftCode,
                         "slotId": slot.slot_id,
                         "shiftCode": slot.shiftCode,
                         "startDateTime": slot.start.isoformat(),
                         "endDateTime": slot.end.isoformat(),
                         "employeeId": emp_id,
+                        "status": "ASSIGNED",
                         "constraintResults": {
                             "hard": [],
                             "soft": []
                         }
                     }
                     assignments.append(assignment)
+                    slot_assigned = True
+                    assigned_count += 1
+        
+        # Check if slot is marked as unassigned
+        if not slot_assigned and slot.slot_id in unassigned:
+            if solver.Value(unassigned[slot.slot_id]) == 1:
+                # Create unassigned slot entry
+                assignment = {
+                    "assignmentId": f"{slot.demandId}-{slot.date.isoformat()}-{slot.shiftCode}-UNASSIGNED",
+                    "demandId": slot.demandId,
+                    "date": slot.date.isoformat(),
+                    "shiftId": slot.shiftCode,
+                    "slotId": slot.slot_id,
+                    "shiftCode": slot.shiftCode,
+                    "startDateTime": slot.start.isoformat(),
+                    "endDateTime": slot.end.isoformat(),
+                    "employeeId": None,
+                    "status": "UNASSIGNED",
+                    "reason": "No employee could be assigned without violating hard constraints",
+                    "constraintResults": {
+                        "hard": [],
+                        "soft": []
+                    }
+                }
+                assignments.append(assignment)
+                unassigned_count += 1
     
-    print(f"  ✓ Extracted {len(assignments)} assignments\n")
+    print(f"  ✓ Extracted {assigned_count} assigned slots")
+    print(f"  ✓ Extracted {unassigned_count} unassigned slots")
+    print(f"  ✓ Total: {len(assignments)} entries\n")
     return assignments
```

---

### Change 5: Updated Score Calculation (Line ~280)

```diff
     print(f"[calculate_scores] Computing constraint violations...")
     
     # Initialize ScoreBook with solver config weights
     score_config = ctx.get('solverScoreConfig', {})
     score_book = ScoreBook(score_config)
     
+    # Count assigned vs unassigned slots
+    assigned_count = sum(1 for a in assignments if a.get('status') == 'ASSIGNED')
+    unassigned_count = sum(1 for a in assignments if a.get('status') == 'UNASSIGNED')
+    
+    print(f"  Assigned slots: {assigned_count}")
+    print(f"  Unassigned slots: {unassigned_count}")
+    
     if len(assignments) == 0:
         score_book.hard("assignment_empty", "No assignments generated")
+    
+    # Report unassigned slots as informational (not violations since this is now allowed)
+    if unassigned_count > 0:
+        print(f"  ℹ️  {unassigned_count} slots could not be filled without violating hard constraints")
+    
+    # Filter out unassigned slots for constraint checking (only check actual assignments)
+    assigned_slots = [a for a in assignments if a.get('status') == 'ASSIGNED']
     
     # ========== POST-SOLUTION CONSTRAINT VALIDATION ==========
     from context.engine.time_utils import split_shift_hours
     from collections import defaultdict
     from datetime import datetime
     
-    # Aggregate assignments by employee and date
+    # Aggregate assignments by employee and date (only assigned slots)
     emp_assignments_by_date = defaultdict(list)  # (emp_id, date) -> [assignments]
     emp_assignments_by_week = defaultdict(list)  # (emp_id, week) -> [assignments]
     emp_assignments_by_month = defaultdict(list)  # (emp_id, month) -> [assignments]
     
     employees = {emp.get('employeeId'): emp for emp in ctx.get('employees', [])}
     
-    for a in assignments:
+    for a in assigned_slots:
```

---

### Change 6: Updated All Constraint Checks (Line ~350+)

```diff
     # ========== C7 CHECK: License Validity on Shift Date ==========
-    for a in assignments:
+    for a in assigned_slots:
         emp_id = a.get('employeeId')
         
     # ========== C8 CHECK: Provisional License (PDL) Validity ==========
-    for a in assignments:
+    for a in assigned_slots:
         emp_id = a.get('employeeId')
         
     # ========== C9 CHECK: Gender Balance for Sensitive Roles ==========
-    for a in assignments:
+    for a in assigned_slots:
         emp_id = a.get('employeeId')
         
     # ========== C10 CHECK: Skill/Role Match ==========
-    for a in assignments:
+    for a in assigned_slots:
         emp_id = a.get('employeeId')
         
     # ========== C11 CHECK: Rank/Product Type Match ==========
-    for a in assignments:
+    for a in assigned_slots:
         emp_id = a.get('employeeId')
         
     # ========== C15 CHECK: Qualification Expiry Override Control ==========
-    for a in assignments:
+    for a in assigned_slots:
         emp_id = a.get('employeeId')
```

---

### Change 7: Updated Soft Constraint Scoring (Line ~480)

```diff
                 try:
                     mod = importlib.import_module(f"context.constraints.{mod_name}")
                     if hasattr(mod, "score_violations"):
-                        violations = mod.score_violations(ctx, assignments, score_book)
+                        # Pass assigned_slots only (not unassigned)
+                        violations = mod.score_violations(ctx, assigned_slots, score_book)
                         soft_constraints_scored += 1
```

---

### Change 8: Enhanced Score Breakdown (Line ~520)

```diff
     # ========== SUMMARY ==========
     hard_count = sum(1 for v in score_book.violations if v['type'] == 'hard')
     soft_count = sum(v.get('penalty', 0) for v in score_book.violations if v['type'] == 'soft')
     
+    # Add unassigned slot metadata to score breakdown
     score_breakdown = {
         "hard": {
             "violations": [v for v in score_book.violations if v['type'] == 'hard']
         },
         "soft": {
             "totalPenalty": soft_count,
             "details": [v for v in score_book.violations if v['type'] == 'soft']
-        }
+        },
+        "unassignedSlots": {
+            "count": unassigned_count,
+            "total": len(assignments),
+            "percentage": round(100 * unassigned_count / len(assignments), 2) if len(assignments) > 0 else 0,
+            "slots": [
+                {
+                    "slotId": a.get('slotId'),
+                    "demandId": a.get('demandId'),
+                    "date": a.get('date'),
+                    "shiftCode": a.get('shiftCode'),
+                    "reason": a.get('reason', 'No feasible assignment')
+                }
+                for a in assignments if a.get('status') == 'UNASSIGNED'
+            ]
+        }
     }
     
     print(f"  Hard violations: {hard_count}")
     print(f"  Soft penalties: {soft_count}")
+    print(f"  Unassigned slots: {unassigned_count}")
     print(f"  Total violations recorded: {len(score_book.violations)}\n")
```

---

## Summary of Changes

### Files Modified
- ✅ `context/engine/solver_engine.py` (1 file)

### Lines Changed
- **Added**: ~120 lines
- **Modified**: ~50 lines
- **Removed**: ~10 lines
- **Net Change**: +110 lines

### Functions Modified
1. ✅ `build_model(ctx)` - Core changes
2. ✅ `extract_assignments(ctx, solver)` - Enhanced extraction
3. ✅ `calculate_scores(ctx, assignments)` - Updated validation

### Key Variables Added
1. ✅ `unassigned` - Dict[slot_id, BoolVar]
2. ✅ `total_unassigned` - IntVar (0 to len(slots))
3. ✅ `BIG_MULTIPLIER` - Constant (1,000,000)

### Constraint Changes
- ✅ Headcount: Changed from `== headcount` to `+ unassigned == headcount`
- ✅ All other constraints: Unchanged (still strict)

### Objective Function
- ❌ Old: `Maximize(sum(assignments))`
- ✅ New: `Minimize(BIG_MULTIPLIER * total_unassigned)`

### Output Format
- ✅ Added `status` field ("ASSIGNED" or "UNASSIGNED")
- ✅ Added `reason` field for unassigned slots
- ✅ `employeeId` = null for unassigned slots
- ✅ New `unassignedSlots` section in scoreBreakdown

---

**Change Date**: November 15, 2025  
**Version**: 0.7.0  
**Status**: ✅ Implemented
