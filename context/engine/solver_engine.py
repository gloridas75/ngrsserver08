"""Solver Engine Entrypoint (skeleton).
- Initializes CP-SAT model.
- Loads constraints dynamically from constraints/ (add_constraints).
- Supports delta-solve (preserve published assignments).
"""
from ortools.sat.python import cp_model
import importlib, pkgutil
from datetime import datetime, date, timedelta
from typing import List, Optional
import time
import os
from collections import defaultdict
from .data_loader import load_input
from .score_helpers import ScoreBook
from .slot_builder import build_slots, normalize_scheme

# Optimization mode constants
OPTIMIZATION_MODE_BALANCE = "balanceWorkload"
OPTIMIZATION_MODE_MINIMIZE = "minimizeEmployeeCount"


def calculate_adaptive_time_limit(num_slots, num_employees, user_time_limit=None):
    """Calculate adaptive time limit based on problem complexity.
    
    Args:
        num_slots: Number of shift slots
        num_employees: Number of employees
        user_time_limit: User-specified time limit (takes precedence)
    
    Returns:
        Recommended time limit in seconds
    """
    if user_time_limit:
        return user_time_limit
    
    # Calculate complexity score
    complexity = (num_slots * num_employees) / 10000
    
    if complexity < 0.5:
        return 5  # Small problem: 5 seconds (< 5,000 variables)
    elif complexity < 2:
        return 10  # Medium problem: 10 seconds (5,000-20,000 variables)
    elif complexity < 5:
        return 20  # Medium-large: 20 seconds (20,000-50,000 variables)
    elif complexity < 15:
        return 40  # Large problem: 40 seconds (50,000-150,000 variables)
    else:
        return 60  # Very large problem: 60 seconds (>150,000 variables)


def calculate_num_search_workers(num_slots, num_employees, user_num_workers=None):
    """Calculate optimal number of parallel search workers for CP-SAT.
    
    CP-SAT can use multiple threads to explore the search space in parallel,
    which can significantly speed up solving for larger problems.
    
    Args:
        num_slots: Number of shift slots
        num_employees: Number of employees
        user_num_workers: User-specified number of workers (takes precedence)
    
    Returns:
        Recommended number of search workers (1-16)
    """
    if user_num_workers:
        return max(1, min(16, user_num_workers))
    
    # Calculate problem complexity
    complexity = (num_slots * num_employees) / 10000
    
    # For very small problems, parallelization overhead isn't worth it
    if complexity < 0.5:
        return 1
    
    # For small-medium problems, use 2-4 workers
    elif complexity < 2:
        return 2
    
    # For medium problems, use 4 workers
    elif complexity < 5:
        return 4
    
    # For large problems, use 8 workers
    elif complexity < 15:
        return 8
    
    # For very large problems, use maximum parallelization
    else:
        return 16


def build_model(ctx):
    """Build CP-SAT model with decision variables for slot-employee assignments.
    
    Decision variables:
    - x[(slot_id, emp_id)] ∈ {0, 1}: 1 if employee is assigned to slot, 0 otherwise
    
    Constraints applied:
    - Headcount: Each slot gets exactly as many assignments as headcount requires
    - One assignment per day per employee: No employee assigned to multiple slots on same day
    
    INCREMENTAL MODE SUPPORT (v0.80):
    - If ctx['_incremental'] exists, builds model only for solvable slots
    - Filters employee-slot pairs based on availability windows
    - Passes incremental context to constraints via ctx
    
    Args:
        ctx: Context dict containing demandItems, employees, etc.
    
    Returns:
        Tuple of (model, assignments_dict) where assignments_dict is x[(slot_id, emp_id)]
    """
    model = cp_model.CpModel()
    
    # Check for incremental mode
    incremental_ctx = ctx.get('_incremental')
    
    if incremental_ctx:
        # INCREMENTAL MODE: Use prebuilt solvable slots
        print(f"[build_model] INCREMENTAL MODE DETECTED")
        print(f"  Using {len(incremental_ctx.get('solvableSlots', []))} pre-classified solvable slots")
        print(f"  Locked context available: weekly hours, consecutive days")
        
        # For incremental mode, we need to reconstruct slot objects from the data
        # But to avoid Slot() constructor issues, let's use the regular flow
        # and filter slots based on solvable slot IDs
        
        # Build all slots first
        slots = build_slots(ctx)
        
        # Filter to only solvable slots by matching (date, demandId, shiftCode)
        # Cannot match by slotId since previous output slotIds differ from newly generated ones
        # Note: solvable slots have date as string, built slots have date as date object
        solvable_keys = {
            (s.get('date'), s.get('demandId'), s.get('shiftCode'))
            for s in incremental_ctx['solvableSlots']
        }
        print(f"[DEBUG] Solvable keys sample (first 3): {list(solvable_keys)[:3]}")
        original_count = len(slots)
        if slots:
            print(f"[DEBUG] Built slots sample (first 3): {[(s.date, s.demandId, s.shiftCode) for s in slots[:3]]}")
        
        # Convert slot dates to strings for matching
        slots = [
            s for s in slots 
            if (s.date.isoformat(), s.demandId, s.shiftCode) in solvable_keys
        ]
        
        print(f"  ✓ Filtered from {original_count} to {len(slots)} solvable slots")
    else:
        # REGULAR MODE: Build slots from demand items
        slots = build_slots(ctx)
    
    ctx['slots'] = slots  # Store in context for constraint use
    
    employees = ctx.get('employees', [])
    scheme_map = ctx.get('schemeMap', {})  # Load scheme mapping for normalization
    
    # Performance optimization: Create lookup caches
    ctx['employee_lookup'] = {emp.get('employeeId') or emp.get('id'): emp for emp in employees}
    ctx['slot_lookup'] = {slot.slot_id: slot for slot in slots}
    
    # Cache slots by date for efficient daily constraint checks
    slots_by_date = defaultdict(list)
    for slot in slots:
        slots_by_date[slot.date].append(slot)
    ctx['slots_by_date'] = dict(slots_by_date)
    
    print(f"[build_model] Creating decision variables...")
    print(f"  Slots: {len(slots)}")
    print(f"  Employees: {len(employees)}")
    print(f"  Cached: {len(ctx['employee_lookup'])} employees, {len(ctx['slots_by_date'])} dates")
    
    # v0.98: Check if outcomeBased mode has pre-selected employees
    selected_employee_ids = ctx.get('_selectedEmployeeIds', None)
    if selected_employee_ids:
        print(f"  outcomeBased mode: Using pre-selected {len(selected_employee_ids)} employees")
    
    # v0.70: Rotation info is now stored per requirement in slot.rotationSequence
    # No need for separate demand_rotations dictionary
    
    # Create decision variables: x[(slot_id, emp_id)] = 1 if assigned
    x = {}
    gender_filtered = 0
    scheme_filtered = 0
    product_filtered = 0
    rank_filtered = 0
    blacklist_filtered = 0
    ou_selection_filtered = 0  # v0.98: Track OU-based filtering
    
    for slot in slots:
        for emp in employees:
            emp_id = emp.get('employeeId')
            
            # v0.98: outcomeBased OU-based selection filter
            if selected_employee_ids and emp_id not in selected_employee_ids:
                ou_selection_filtered += 1
                continue
            
            # v0.70: Check product type requirement
            slot_product = slot.productTypeId
            emp_product = emp.get('productTypeId', '')
            if slot_product and emp_product != slot_product:
                product_filtered += 1
                continue
            
            # v0.95: Check rank requirement (supports multiple ranks - OR logic)
            slot_ranks = slot.rankIds  # Changed from rankId to rankIds
            emp_rank = emp.get('rankId', '')
            # Employee must match at least ONE of the acceptable ranks
            if slot_ranks and emp_rank not in slot_ranks:
                rank_filtered += 1
                continue
            
            # v0.70: Check gender requirement
            gender_req = slot.genderRequirement
            emp_gender = emp.get('gender', 'Unknown')
            gender_allowed = True
            
            if gender_req == 'M' and emp_gender != 'M':
                gender_allowed = False
                gender_filtered += 1
            elif gender_req == 'F' and emp_gender != 'F':
                gender_allowed = False
                gender_filtered += 1
            # Note: "Mix" and "Any" allow all genders at variable creation
            # Mix constraint will be handled separately to ensure at least 1M + 1F
            
            if not gender_allowed:
                continue            # v0.70: Check scheme requirement
            # Note: slot.schemeRequirement is already normalized to short code (A/B/P/Global) by slot_builder
            scheme_req = slot.schemeRequirement
            emp_scheme_raw = emp.get('scheme', '')
            emp_scheme = normalize_scheme(emp_scheme_raw, scheme_map)  # Normalize employee scheme too
            scheme_allowed = True
            
            # Both are now in short format, so direct comparison works
            if scheme_req != 'Global' and scheme_req != emp_scheme:
                scheme_allowed = False
                scheme_filtered += 1
            
            if not scheme_allowed:
                continue
            
            # v0.70: Check blacklist date ranges
            blacklist = slot.blacklist
            blacklist_allowed = True
            
            if blacklist and 'employeeIds' in blacklist:
                for bl_entry in blacklist['employeeIds']:
                    if bl_entry.get('employeeId') == emp_id:
                        # Check if slot date falls within blacklist range
                        bl_start = bl_entry.get('blacklistStartDate', '')
                        bl_end = bl_entry.get('blacklistEndDate', '')
                        
                        if bl_start and bl_end:
                            try:
                                from datetime import datetime as dt
                                start_date = dt.fromisoformat(bl_start).date()
                                end_date = dt.fromisoformat(bl_end).date()
                                
                                if start_date <= slot.date <= end_date:
                                    blacklist_allowed = False
                                    blacklist_filtered += 1
                                    break
                            except:
                                pass  # If date parsing fails, allow assignment
            
            if not blacklist_allowed:
                continue
            
            # INCREMENTAL MODE: Check employee availability windows
            if incremental_ctx:
                availability_allowed = True
                
                # Check if employee is new joiner with availableFrom constraint
                new_joiners = incremental_ctx.get('employeeChanges', {}).get('newJoiners', [])
                for joiner in new_joiners:
                    if joiner.get('employee', {}).get('employeeId') == emp_id:
                        from datetime import datetime as dt
                        available_from = dt.fromisoformat(joiner['availableFrom']).date()
                        if slot.date < available_from:
                            availability_allowed = False
                            break
                
                # Check if employee is on long leave during this slot
                long_leave_list = incremental_ctx.get('employeeChanges', {}).get('longLeave', [])
                for leave in long_leave_list:
                    if leave.get('employeeId') == emp_id:
                        from datetime import datetime as dt
                        leave_from = dt.fromisoformat(leave['leaveFrom']).date()
                        leave_to = dt.fromisoformat(leave['leaveTo']).date()
                        if leave_from <= slot.date <= leave_to:
                            availability_allowed = False
                            break
                
                if not availability_allowed:
                    continue
            
            # Check whitelist constraints
            whitelist = slot.whitelist
            is_whitelisted = True
            
            # If whitelist has constraints, check if employee passes
            if any(whitelist.get(k) for k in ['employeeIds', 'teamIds']):
                is_whitelisted = False
                
                # Check employee whitelist
                if whitelist.get('employeeIds') and emp_id in whitelist['employeeIds']:
                    is_whitelisted = True
                # Check team whitelist
                elif whitelist.get('teamIds') and emp.get('teamId') in whitelist['teamIds']:
                    is_whitelisted = True
            
            if not is_whitelisted:
                continue
            
            # Create decision variable for all whitelisted pairs
            # Pattern enforcement will be handled as hard constraints below
            var_name = f"x[{slot.slot_id}][{emp_id}]"
            x[(slot.slot_id, emp_id)] = model.NewBoolVar(var_name)
    
    print(f"[build_model] ✓ Created {len(x)} decision variables")
    if ou_selection_filtered > 0:
        print(f"  ℹ️  Filtered {ou_selection_filtered} employee-slot pairs by outcomeBased OU selection")
    if product_filtered > 0:
        print(f"  ℹ️  Filtered {product_filtered} employee-slot pairs based on product type requirement")
    if rank_filtered > 0:
        print(f"  ℹ️  Filtered {rank_filtered} employee-slot pairs based on rank requirement")
    if gender_filtered > 0:
        print(f"  ℹ️  Filtered {gender_filtered} employee-slot pairs based on gender requirement")
    if scheme_filtered > 0:
        print(f"  ℹ️  Filtered {scheme_filtered} employee-slot pairs based on scheme requirement")
    if blacklist_filtered > 0:
        print(f"  ℹ️  Filtered {blacklist_filtered} employee-slot pairs based on blacklist date ranges")
    print(f"  ℹ️  Work pattern enforcement will be handled as hard constraints")
    
    # ========== NEW: UNASSIGNED SLOT VARIABLES ==========
    print(f"\n[build_model] Creating unassigned slot variables...")
    unassigned = {}
    for slot in slots:
        unassigned[slot.slot_id] = model.NewBoolVar(f"unassigned_slot_{slot.slot_id}")
    
    print(f"  ✓ Created {len(unassigned)} unassigned slot variables")
    
    # ========== NEW: EMPLOYEE USAGE TRACKING (OUTCOME-BASED MODE) ==========
    # For outcomeBased mode, track which employees are used and enforce minimum threshold
    rostering_basis = ctx.get('_rosteringBasis', 'demandBased')
    if rostering_basis == 'outcomeBased':
        print(f"\n[build_model] Setting up employee usage tracking (outcomeBased mode)...")
        
        # Create binary variables: emp_used[emp_id] = 1 if employee assigned to any slot
        emp_used = {}
        for emp in employees:
            emp_id = emp.get('employeeId')
            emp_used[emp_id] = model.NewBoolVar(f"emp_used_{emp_id}")
        
        # Link emp_used to assignments: emp_used = 1 if sum(x[slot, emp_id]) > 0
        for emp in employees:
            emp_id = emp.get('employeeId')
            # Get all slots this employee could be assigned to
            emp_assignments = [x[(s.slot_id, emp_id)] for s in slots if (s.slot_id, emp_id) in x]
            
            if emp_assignments:
                # emp_used[emp_id] == 1 iff sum(assignments) > 0
                # We use: sum(assignments) >= emp_used (if used, must have >= 1 assignment)
                #         sum(assignments) <= BigM * emp_used (if not used, no assignments)
                # Simpler: max_assignments * emp_used >= sum(assignments) >= emp_used
                max_possible = len(emp_assignments)
                model.Add(sum(emp_assignments) >= emp_used[emp_id])
                model.Add(sum(emp_assignments) <= max_possible * emp_used[emp_id])
            else:
                # No valid slots for this employee - cannot be used
                model.Add(emp_used[emp_id] == 0)
        
        ctx['emp_used'] = emp_used
        print(f"  ✓ Created {len(emp_used)} employee usage tracking variables")
        
        # Add constraint: At least target_employee_count must be used
        target_employee_count = ctx.get('_targetEmployeeCount', len(employees))
        model.Add(sum(emp_used.values()) >= target_employee_count)
        print(f"  ✓ Added constraint: At least {target_employee_count} employees must be used")
        print()
    
    # ========== CONSTRAINT 1: HEADCOUNT SATISFACTION (MODIFIED) ==========
    print(f"\n[build_model] Adding headcount constraints (with unassigned option)...")
    headcount_constraints = 0
    for slot in slots:
        # v0.70: Each slot represents 1 position (headcount is implicit=1)
        # Sum assignments for this slot must equal 1 OR slot is marked unassigned
        # Only include employees that are whitelisted for this slot
        slot_assignments = [x[(slot.slot_id, emp.get('employeeId'))] 
                           for emp in employees 
                           if (slot.slot_id, emp.get('employeeId')) in x]
        
        if slot_assignments:  # Only add constraint if there are valid employees
            # MODIFIED: Either assign exactly 1 employee OR mark slot as unassigned
            # sum(assignments) + unassigned[slot_id] == 1
            model.Add(sum(slot_assignments) + unassigned[slot.slot_id] == 1)
            headcount_constraints += 1
        else:
            # No valid employees for this slot - must be marked unassigned
            model.Add(unassigned[slot.slot_id] == 1)
            headcount_constraints += 1
    
    print(f"  ✓ Added {headcount_constraints} headcount constraints (allowing unassigned)\n")
    
    # ========== CONSTRAINT 2: ONE ASSIGNMENT PER EMPLOYEE PER DAY ==========
    print(f"[build_model] Adding one-per-day constraints...")
    one_per_day_constraints = 0
    
    # Group slots by employee and date
    slots_by_emp_date = defaultdict(list)
    for slot in slots:
        for emp in employees:
            emp_id = emp.get('employeeId')
            slots_by_emp_date[(emp_id, slot.date)].append(slot)
    
    # For each employee-date pair, at most 1 assignment
    for (emp_id, date), date_slots in slots_by_emp_date.items():
        if len(date_slots) > 1:
            # Only include assignments that exist (were whitelisted)
            emp_date_assignments = [x[(slot.slot_id, emp_id)] for slot in date_slots 
                                   if (slot.slot_id, emp_id) in x]
            if emp_date_assignments:
                model.Add(sum(emp_date_assignments) <= 1)
                one_per_day_constraints += 1
    
    print(f"  ✓ Added {one_per_day_constraints} one-per-day constraints\n")
    
    # ========== AGGREGATE UNASSIGNED SLOTS ==========
    print(f"[build_model] Creating total unassigned counter...")
    total_unassigned = model.NewIntVar(0, len(slots), "total_unassigned")
    model.Add(total_unassigned == sum(unassigned[slot.slot_id] for slot in slots))
    print(f"  ✓ Created total_unassigned variable (range: 0-{len(slots)})\n")
    
    # ========== OPTIMIZATION MODE CONFIGURATION ==========
    # Get optimization mode from input (default: balanceWorkload)
    solver_config = ctx.get('solverConfig') or {}
    optimization_mode = solver_config.get('optimizationMode', OPTIMIZATION_MODE_BALANCE)
    max_employees_to_use = solver_config.get('maxEmployeesToUse', None)
    
    print(f"[build_model] Optimization Mode: {optimization_mode}")
    if max_employees_to_use:
        print(f"  Max employees to use: {max_employees_to_use}")
    
    # Create assignment count variable for each employee
    emp_assignment_counts = {}
    employee_used_vars = {}  # Binary: 1 if employee has any assignment
    
    for emp in employees:
        emp_id = emp.get('employeeId')
        # Count assignments for this employee across all slots
        emp_assignments = [x[(slot.slot_id, emp_id)] for slot in slots 
                          if (slot.slot_id, emp_id) in x]
        if emp_assignments:
            count_var = model.NewIntVar(0, len(slots), f"emp_{emp_id}_count")
            model.Add(count_var == sum(emp_assignments))
            emp_assignment_counts[emp_id] = count_var
            
            # Create binary variable: is employee used? (needed for continuous adherence)
            used_var = model.NewBoolVar(f"emp_used_{emp_id}")
            # Link: used_var = 1 iff employee has at least 1 assignment
            model.Add(count_var > 0).OnlyEnforceIf(used_var)
            model.Add(count_var == 0).OnlyEnforceIf(used_var.Not())
            employee_used_vars[emp_id] = used_var
    
    # Mode-specific objective components
    if optimization_mode == OPTIMIZATION_MODE_MINIMIZE:
        # Mode: Minimize number of employees used
        if employee_used_vars:
            total_employees_used = model.NewIntVar(0, len(employees), "total_employees_used")
            model.Add(total_employees_used == sum(employee_used_vars.values()))
            
            # Optional: hard constraint on max employees
            if max_employees_to_use:
                model.Add(total_employees_used <= max_employees_to_use)
                print(f"  ✓ Hard limit: Use at most {max_employees_to_use} employees")
            
            print(f"  ✓ Objective: Minimize employee count (use fewest employees)\n")
        else:
            total_employees_used = model.NewIntVar(0, 0, "total_employees_used_zero")
        
        # Set workload_imbalance to zero for compatibility
        workload_imbalance = model.NewIntVar(0, 0, "workload_imbalance_zero")
        
    else:
        # Mode: Balance workload (default behavior)
        if emp_assignment_counts:
            max_count = model.NewIntVar(0, len(slots), "max_assignments")
            min_count = model.NewIntVar(0, len(slots), "min_assignments")
            model.AddMaxEquality(max_count, list(emp_assignment_counts.values()))
            model.AddMinEquality(min_count, list(emp_assignment_counts.values()))
            workload_imbalance = model.NewIntVar(0, len(slots), "workload_imbalance")
            model.Add(workload_imbalance == max_count - min_count)
            print(f"  ✓ Objective: Balance workload across {len(emp_assignment_counts)} employees\n")
        else:
            workload_imbalance = model.NewIntVar(0, 0, "workload_imbalance_zero")
        
        # Set total_employees_used to zero for compatibility
        total_employees_used = model.NewIntVar(0, 0, "total_employees_used_zero")
    
    # Store in context for result reporting
    ctx['optimization_mode'] = optimization_mode
    ctx['employee_used_vars'] = employee_used_vars
    ctx['total_employees_used'] = total_employees_used
    
    # ========== ROTATION OFFSET OPTIMIZATION (OPTIONAL) ==========
    # Check if rotation offsets should be optimized by CP-SAT
    # Support both legacy boolean and new string values
    fixed_rotation_offset_raw = ctx.get('fixedRotationOffset', True)
    
    # Normalize to string for comparison
    if isinstance(fixed_rotation_offset_raw, bool):
        fixed_rotation_offset = "auto" if fixed_rotation_offset_raw else "solverOptimized"
    else:
        fixed_rotation_offset = fixed_rotation_offset_raw
    
    offset_vars = {}  # Will store offset decision variables if optimization enabled
    
    # INCREMENTAL MODE ENHANCEMENT: Auto-optimize offsets for new joiners
    new_joiner_ids = set()
    if incremental_ctx:
        new_joiners = incremental_ctx.get('employeeChanges', {}).get('newJoiners', [])
        new_joiner_ids = {nj['employee']['employeeId'] for nj in new_joiners}
        
        if new_joiner_ids:
            print(f"[build_model] INCREMENTAL MODE: Auto-optimizing offsets for {len(new_joiner_ids)} new joiners")
            print(f"  Existing employees will keep their fixed offsets")
    
    # Determine if solver should optimize offsets
    solver_optimizes_offsets = (fixed_rotation_offset == "solverOptimized") or new_joiner_ids
    
    if solver_optimizes_offsets:
        print(f"[build_model] Creating rotation offset decision variables...")
        if fixed_rotation_offset == "solverOptimized":
            print(f"  Mode: CP-SAT will optimize rotation offsets for ALL employees")
        
        # Create offset decision variables for each employee
        # Offset range: 0 to (pattern_length - 1)
        pattern_length = 6  # Default 6-day cycle
        
        for emp in employees:
            emp_id = emp.get('employeeId')
            
            # INCREMENTAL MODE: Only optimize new joiners if mode is "auto" or "ouOffsets"
            if fixed_rotation_offset in ["auto", "ouOffsets"] and emp_id not in new_joiner_ids:
                continue  # Skip existing employees, they keep fixed offsets
            
            # Try to get actual pattern length from slots this employee can work
            for slot in slots:
                if (slot.slot_id, emp_id) in x and slot.rotationSequence:
                    pattern_length = len(slot.rotationSequence)
                    break
            
            # Create integer decision variable for offset
            offset_vars[emp_id] = model.NewIntVar(0, pattern_length - 1, f"offset_{emp_id}")
        
        print(f"  ✓ Created {len(offset_vars)} offset decision variables (range: 0-{pattern_length-1})\n")
        ctx['offset_vars'] = offset_vars  # Store for extraction later
    else:
        print(f"  ✓ Using fixed rotation offsets from employee data\n")
    
    # ========== WORK PATTERN ENFORCEMENT (HARD CONSTRAINTS) ==========
    print(f"[build_model] Adding work pattern constraints...")
    pattern_constraints = 0
    
    # For each employee-slot pair, enforce pattern matching
    for slot in slots:
        rotation_seq = slot.rotationSequence
        if not rotation_seq:
            continue
            
        cycle_days = len(rotation_seq)
        base_date = slot.coverageAnchor
        
        if not base_date:
            continue
        
        # WEEK-ALIGNED PATTERN: Find Monday of the week containing coverageAnchor
        # This ensures pattern cycles align with calendar weeks (Mon-Sun)
        # Formula: base_date - (base_date.weekday() days) = Monday of that week
        # Example: If coverageAnchor = 2026-01-01 (Thu, weekday=3), 
        #          week_anchor = 2026-01-01 - 3 days = 2025-12-29 (Mon)
        week_anchor = base_date - timedelta(days=base_date.weekday())
        
        # Calculate which day in the cycle this slot represents (from Monday anchor)
        days_from_base = (slot.date - week_anchor).days
        
        for emp in employees:
            emp_id = emp.get('employeeId')
            
            # Skip if no decision variable exists for this pair
            if (slot.slot_id, emp_id) not in x:
                continue
            
            # Check if this employee has a variable offset or fixed offset
            has_variable_offset = emp_id in offset_vars
            
            if has_variable_offset:
                # MODE 2: Use CP-SAT offset decision variables (for new joiners or when fixedRotationOffset=false)
                offset_var = offset_vars[emp_id]
                
                # For each possible offset value (0 to cycle_days-1)
                for possible_offset in range(cycle_days):
                    # Calculate cycle day for this offset (offset = starting position in cycle)
                    emp_cycle_day = (days_from_base + possible_offset) % cycle_days
                    expected_shift = rotation_seq[emp_cycle_day]
                    
                    # Block assignment if shift doesn't match expected pattern
                    # This includes both 'O' (off days) and mismatched shift codes
                    if expected_shift == 'O' or slot.shiftCode != expected_shift:
                        # Create indicator: is_this_offset = 1 if offset_var == possible_offset
                        is_this_offset = model.NewBoolVar(f"offset_match_{slot.slot_id}_{emp_id}_{possible_offset}")
                        model.Add(offset_var == possible_offset).OnlyEnforceIf(is_this_offset)
                        model.Add(offset_var != possible_offset).OnlyEnforceIf(is_this_offset.Not())
                        
                        # If offset matches AND employee assigned, that's a violation
                        # Prevent: is_this_offset=1 AND x=1
                        model.Add(x[(slot.slot_id, emp_id)] == 0).OnlyEnforceIf(is_this_offset)
                        pattern_constraints += 1
            else:
                # MODE 1: Use fixed offset from employee data (for existing employees in incremental mode)
                emp_offset = emp.get('rotationOffset', 0)
                
                # SPECIAL HANDLING: offset=-1 means "truly flexible" employee from preprocessing
                # These employees can work ANY shift without pattern constraints
                if emp_offset == -1:
                    # No pattern constraint for flexible employees
                    # They can be assigned to any shift
                    continue
                
                emp_cycle_day = (days_from_base + emp_offset) % cycle_days
                expected_shift = rotation_seq[emp_cycle_day]
                
                # HARD CONSTRAINT: Employee can only work shifts matching their pattern position
                # Block if off-day ('O') OR if shift code doesn't match
                if expected_shift == 'O' or slot.shiftCode != expected_shift:
                    model.Add(x[(slot.slot_id, emp_id)] == 0)
                    pattern_constraints += 1
    
    if offset_vars:
        print(f"  ✓ Added {pattern_constraints} work pattern constraints ({len(offset_vars)} variable offsets, {len(employees) - len(offset_vars)} fixed)\n")
        
        # ========== OFFSET DIVERSITY CONSTRAINT ==========
        # Force offset diversity to prevent all employees clustering on one offset
        # This is critical for continuous adherence to work with pattern-based coverage
        print(f"[build_model] Adding offset diversity constraint...")
        
        # Get cycle length from first slot with rotation sequence
        cycle_length = 6  # Default for D-D-N-N-O-O pattern
        for slot in slots:
            if slot.rotationSequence:
                cycle_length = len(slot.rotationSequence)
                break
        
        diversity_constraints = 0
        for target_offset in range(cycle_length):
            # Count how many employees assigned this offset
            offset_indicators = []
            for emp_id, offset_var in offset_vars.items():
                indicator = model.NewBoolVar(f'emp_{emp_id}_offset_{target_offset}')
                model.Add(offset_var == target_offset).OnlyEnforceIf(indicator)
                model.Add(offset_var != target_offset).OnlyEnforceIf(indicator.Not())
                offset_indicators.append(indicator)
            
            # Require at least 1 employee per offset (to ensure coverage diversity)
            if offset_indicators:
                model.Add(sum(offset_indicators) >= 1)
                diversity_constraints += 1
        
        print(f"  ✓ Added {diversity_constraints} offset diversity constraints (min 1 employee per offset)\n")
    else:
        print(f"  ✓ Added {pattern_constraints} work pattern constraints (HARD, all fixed offsets)\n")
    
    # ========== HYBRID CONTINUOUS PATTERN ADHERENCE (REMOVED) ==========
    # REMOVED: This was causing infeasibility by forcing employees to work ALL pattern days
    # Work pattern constraints above are sufficient - they block off-days and wrong shifts
    print(f"[build_model] STRICT adherence constraints REMOVED - all employees flexible within pattern")
    print(f"  ℹ️  Employees can work any 'D' day that matches their rotation offset")
    print(f"  ℹ️  Weekly/monthly hour caps will naturally limit assignments\n")
    
    
    # ========== ROTATION CONTINUITY (DISABLED) ==========
    print(f"[build_model] TEMPORARILY DISABLED - testing without continuity constraints...")
    print(f"  ⚠️  CONTINUITY CONSTRAINTS DISABLED\n")
    
    # ========== ROTATION OFFSET ANCHOR PREFERENCE ==========
    print(f"[build_model] TEMPORARILY DISABLED - testing without anchor preferences...")
    anchor_penalties = []
    
    # TEMPORARILY DISABLED FOR DEBUGGING
    print(f"  ⚠️  ANCHOR PREFERENCES DISABLED\n")
    
    # Create total anchor penalty variable
    total_anchor_penalty = model.NewIntVar(0, 10000, 'total_anchor_penalty')
    if False:  # Disabled
        anchor_expr = sum(indicator * weight for indicator, weight in anchor_penalties)
        model.Add(total_anchor_penalty == anchor_expr)
        print(f"  ✓ Added {len(anchor_penalties)} rotation offset anchor preferences\n")
    else:
        model.Add(total_anchor_penalty == 0)
        print(f"  ✓ No anchor preferences needed\n")
    
    # ========== ROTATION PATTERN COMPLIANCE ==========
    print(f"[build_model] Adding rotation pattern compliance penalties...")
    rotation_violations = []
    demand_items = ctx.get('demandItems', [])
    planning_horizon = ctx.get('planningHorizon', {})
    
    for demand in demand_items:
        demand_id = demand.get('demandId')
        shift_start_date_str = demand.get('shiftStartDate', planning_horizon.get('startDate'))
        
        for shift_group in demand.get('shifts', []):
            rotation_seq = shift_group.get('rotationSequence', [])
            
            if rotation_seq and demand_id:
                try:
                    from datetime import datetime as dt
                    anchor_date = dt.fromisoformat(shift_start_date_str).date()
                    cycle_days = len(rotation_seq)
                    
                    # For each slot in this demand, check if it violates rotation
                    demand_slots = [s for s in slots if s.demandId == demand_id]
                    
                    for slot in demand_slots:
                        days_from_anchor = (slot.date - anchor_date).days
                        rotation_index = days_from_anchor % cycle_days
                        expected_shift = rotation_seq[rotation_index]
                        
                        # If slot shift doesn't match expected, any assignment violates rotation
                        if slot.shiftCode != expected_shift and slot.shiftCode != 'O':
                            # Create violation variable for this slot
                            violation_var = model.NewBoolVar(f"rotation_violation_{slot.slot_id}")
                            # If any employee assigned to this slot, it's a violation
                            slot_assignments = [x[(slot.slot_id, emp.get('employeeId'))] 
                                              for emp in employees 
                                              if (slot.slot_id, emp.get('employeeId')) in x]
                            if slot_assignments:
                                # violation_var = 1 if sum(assignments) > 0
                                model.Add(sum(slot_assignments) > 0).OnlyEnforceIf(violation_var)
                                model.Add(sum(slot_assignments) == 0).OnlyEnforceIf(violation_var.Not())
                                rotation_violations.append(violation_var)
                except:
                    pass
    
    total_rotation_violations = model.NewIntVar(0, len(slots), "total_rotation_violations")
    if rotation_violations:
        model.Add(total_rotation_violations == sum(rotation_violations))
        print(f"  ✓ Created {len(rotation_violations)} rotation compliance variables\n")
    else:
        model.Add(total_rotation_violations == 0)
        print(f"  ✓ No rotation violations detected\n")
    
    # ========== OBJECTIVE FUNCTION (ENHANCED) ==========
    # Priority levels:
    # 1. PRIMARY: Minimize unassigned slots (priority: 1,000,000)
    # 2. SECONDARY (mode-dependent):
    #    - minimizeEmployeeCount: Minimize employee count (priority: 100,000)
    #    - balanceWorkload: Minimize soft penalties (priority: 1,000)
    # 3. TERTIARY: Minimize soft penalties (priority: 1,000)
    # 4. QUATERNARY: Maximize total assignments (priority: 1)
    BIG_MULTIPLIER = 1_000_000
    MEDIUM_MULTIPLIER = 100_000
    SOFT_MULTIPLIER = 1_000
    
    # Calculate total assignments for tertiary optimization
    total_assignments = sum(x.values())
    
    print(f"[build_model] Setting objective: Multi-level optimization")
    print(f"  PRIORITY 1: Minimize unassigned slots ({BIG_MULTIPLIER:,}×)")
    
    if optimization_mode == OPTIMIZATION_MODE_MINIMIZE:
        print(f"  PRIORITY 2: Minimize employee count ({MEDIUM_MULTIPLIER:,}×)")
        print(f"  PRIORITY 3: Minimize soft penalties ({SOFT_MULTIPLIER:,}×)")
        print(f"    - Rotation violations")
        print(f"    - Anchor offset penalties")
        print(f"  PRIORITY 4: Maximize assignments (1×)")
        
        # Combined objective for minimizeEmployeeCount mode
        objective_expr = (
            BIG_MULTIPLIER * total_unassigned +
            MEDIUM_MULTIPLIER * total_employees_used +
            SOFT_MULTIPLIER * total_rotation_violations +
            SOFT_MULTIPLIER * total_anchor_penalty -
            total_assignments
        )
    else:
        print(f"  PRIORITY 2: Minimize soft penalties ({SOFT_MULTIPLIER:,}×)")
        print(f"    - Rotation violations")
        print(f"    - Anchor offset penalties")
        # print(f"    - Workload imbalance")  # DISABLED: Testing continuous adherence without workload balance
        print(f"  PRIORITY 3: Maximize assignments (1×)")
        
        # Combined objective for balanceWorkload mode
        objective_expr = (
            BIG_MULTIPLIER * total_unassigned +
            SOFT_MULTIPLIER * total_rotation_violations +
            SOFT_MULTIPLIER * total_anchor_penalty +
            # SOFT_MULTIPLIER * workload_imbalance -  # DISABLED: Testing continuous adherence
            0 -  # Placeholder
            total_assignments
        )
    
    model.Minimize(objective_expr)
    print(f"  ✓ Objective configured with multi-term optimization\n")
    
    # Store model artifacts in context for later extraction
    ctx['x'] = x
    ctx['unassigned'] = unassigned
    ctx['total_unassigned'] = total_unassigned
    ctx['model'] = model
    ctx['solver'] = None  # Will be set after solving
    
    return model


def apply_constraints(model, ctx):
    """Apply custom constraints from the constraints/ directory."""
    
    # Load all hard constraints (C13 permanently removed)
    hard_constraints = [
        'C1_mom_daily_hours',
        'C2_mom_weekly_hours_pattern_aware',  # Use pattern-aware version for correct 6-day handling
        'C3_consecutive_days',
        'C4_rest_period',
        'C5_offday_rules',
        'C6_parttimer_limits',
        'C7_license_validity',
        'C8_provisional_license',
        'C9_gender_balance',
        # 'C10_skill_role_match',  # TODO: Enable when input JSON includes role/skill requirements
        'C11_rank_product_match',
        'C12_team_completeness',
        'C15_qualification_expiry_override',
        'C16_no_overlap',
        'C17_ot_monthly_cap'
    ]
    
    # Load all soft constraints
    soft_constraints = [
        'S1_rotation_pattern',
        'S2_preferences',
        'S3_consistent_start',
        'S4_min_short_gaps',
        'S5_officer_continuity',
        'S6_minimize_shift_change_within_team',
        'S7_zone_preference',
        'S8_team_size_feasibility',
        'S9_travel_slack',
        'S10_fair_ot',
        'S11_public_holiday_coverage',
        'S12_allowance_optimization',
        'S13_substitute_logic',
        'S14_midmonth_insert',
        'S15_demand_coverage_score',
        'S16_whitelist_blacklist',
        'S18_minimize_gaps'
    ]
    
    all_constraints = hard_constraints + soft_constraints
    
    for mod_name in all_constraints:
        try:
            mod = importlib.import_module(f"context.constraints.{mod_name}")
            if hasattr(mod, "add_constraints"):
                mod.add_constraints(model, ctx)
        except Exception as e:
            print(f"  Warning: Could not load {mod_name}: {e}")
    
    print(f"  ✓ Loaded constraint modules\n")


def calculate_employee_work_pattern(base_pattern: list, offset: int) -> list:
    """Calculate employee's actual work pattern as it appears on the calendar.
    
    Args:
        base_pattern: Base rotation sequence (e.g., ['D', 'D', 'N', 'N', 'O', 'O'])
        offset: Employee's rotation offset (0 to pattern_length-1)
    
    Returns:
        Work pattern as it appears on the calendar (rotated LEFT by offset)
        
    Example:
        base_pattern = ['D', 'D', 'N', 'N', 'O', 'O']
        offset = 1
        Employee's work cycle starts at position 1 of base pattern.
        Their repeating 6-day cycle: ['D', 'N', 'N', 'O', 'O', 'D']
        This represents their personal rotation pattern (not calendar alignment).
    """
    if not base_pattern or offset == 0:
        return base_pattern
    
    pattern_length = len(base_pattern)
    offset = offset % pattern_length  # Ensure offset is within range
    
    # Rotate LEFT by offset positions to show employee's personal cycle pattern
    # This represents the employee's repeating work cycle (as shown in Excel)
    return base_pattern[offset:] + base_pattern[:offset]


def calculate_pattern_day(assignment_date: date, pattern_start_date: date, employee_offset: int, pattern_length: int, coverage_days: List[str] = None) -> int:
    """Calculate which day of the work pattern this assignment falls on.
    
    **CRITICAL**: Pattern cycles through COVERAGE DAYS ONLY, not calendar days.
    This ensures proper rotation for Mon-Fri patterns (ignoring Sat/Sun).
    
    Args:
        assignment_date: The date of this assignment
        pattern_start_date: The anchor date for the rotation pattern (shiftStartDate)
        employee_offset: Employee's rotation offset (0 to pattern_length-1)
        pattern_length: Length of the work pattern cycle
        coverage_days: List of day names covered (e.g., ['Monday', 'Tuesday', ...])
                      If None, counts all calendar days (legacy behavior)
    
    Returns:
        Integer from 0 to (pattern_length-1) indicating position in the pattern cycle
        
    Formula (coverage-aware):
        1. Build list of coverage dates between pattern_start_date and assignment_date
        2. Count only days matching coverage_days
        3. patternDay = (coverage_days_count + employee_offset) % pattern_length
        
    Example (Mon-Fri coverage):
        Pattern: ['D', 'D', 'D', 'D', 'O'] (length=5)
        Coverage: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        Start: 2025-12-01 (Monday)
        
        Employee offset: 0
        - Mon 12/01 (0 coverage days): (0 + 0) % 5 = 0 → 'D'
        - Tue 12/02 (1 coverage days): (1 + 0) % 5 = 1 → 'D'
        - Sat 12/06 (IGNORED - not in coverage)
        - Sun 12/07 (IGNORED - not in coverage)
        - Mon 12/08 (5 coverage days): (5 + 0) % 5 = 0 → 'D' (NEW CYCLE)
    """
    if coverage_days is None or len(coverage_days) == 0:
        # Legacy behavior: count all calendar days
        days_since_start = (assignment_date - pattern_start_date).days
        pattern_day = (days_since_start + employee_offset) % pattern_length
        return pattern_day
    
    # NEW: Coverage-aware counting
    # Map day names to weekday numbers
    day_name_mapping = {
        'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
        'Friday': 4, 'Saturday': 5, 'Sunday': 6,
        'Mon': 0, 'Tue': 1, 'Wed': 2, 'Thu': 3,
        'Fri': 4, 'Sat': 5, 'Sun': 6
    }
    
    # Build set of allowed weekdays
    allowed_weekdays = set()
    for day_name in coverage_days:
        if day_name in day_name_mapping:
            allowed_weekdays.add(day_name_mapping[day_name])
    
    if not allowed_weekdays:
        # Fallback to legacy if we couldn't parse coverage days
        days_since_start = (assignment_date - pattern_start_date).days
        pattern_day = (days_since_start + employee_offset) % pattern_length
        return pattern_day
    
    # Count coverage days between pattern_start_date and assignment_date
    coverage_day_count = 0
    current_date = pattern_start_date
    
    while current_date < assignment_date:
        if current_date.weekday() in allowed_weekdays:
            coverage_day_count += 1
        current_date += timedelta(days=1)
    
    # Calculate pattern position using coverage day count
    pattern_day = (coverage_day_count + employee_offset) % pattern_length
    return pattern_day


def extract_assignments(ctx, solver) -> list:
    """Extract assignments from solver solution.
    
    Args:
        ctx: Context dict with slots, employees, x (decision variables), unassigned variables
        solver: CpSolver instance after solving
    
    Returns:
        List of assignment dicts in output format (includes both assigned and unassigned slots)
    """
    assignments = []
    x = ctx.get('x', {})
    unassigned = ctx.get('unassigned', {})
    slots = ctx.get('slots', [])
    employees_map = {emp.get('employeeId'): emp for emp in ctx.get('employees', [])}
    optimized_offsets = ctx.get('optimized_offsets', {})
    
    print(f"[extract_assignments] Extracting assignments from solution...")
    
    assigned_count = 0
    unassigned_count = 0
    
    for slot in slots:
        slot_assigned = False
        
        # Check if any employee is assigned to this slot
        for emp_id, emp in employees_map.items():
            var_key = (slot.slot_id, emp_id)
            if var_key in x:
                # Check if this variable is assigned in the solution
                if solver.Value(x[var_key]) == 1:
                    # Get employee's rotation offset
                    emp_offset = optimized_offsets.get(emp_id, emp.get('rotationOffset', 0))
                    
                    # Calculate patternDay: which day in the rotation cycle this assignment falls on
                    pattern_length = len(slot.rotationSequence) if slot.rotationSequence else 1
                    pattern_day = calculate_pattern_day(
                        assignment_date=slot.date,
                        pattern_start_date=slot.patternStartDate,  # From slot (shiftStartDate)
                        employee_offset=emp_offset,
                        pattern_length=pattern_length,
                        coverage_days=slot.coverageDays  # CRITICAL: Pass coverage days for proper rotation
                    )
                    
                    assignment = {
                        "assignmentId": f"{slot.demandId}-{slot.date.isoformat()}-{slot.shiftCode}-{emp_id}",
                        "demandId": slot.demandId,
                        "requirementId": slot.requirementId,
                        "date": slot.date.isoformat(),
                        "slotId": slot.slot_id,
                        "shiftCode": slot.shiftCode,
                        "patternDay": pattern_day,
                        "startDateTime": slot.start.isoformat(),
                        "endDateTime": slot.end.isoformat(),
                        "employeeId": emp_id,
                        "newRotationOffset": emp_offset,
                        "status": "ASSIGNED"
                    }
                    assignments.append(assignment)
                    slot_assigned = True
                    assigned_count += 1
        
        # Check if slot is marked as unassigned
        if not slot_assigned and slot.slot_id in unassigned:
            if solver.Value(unassigned[slot.slot_id]) == 1:
                # Create unassigned slot entry
                assignment = {
                    "assignmentId": f"{slot.demandId}-{slot.date.isoformat()}-{slot.shiftCode}-UNASSIGNED",
                    "demandId": slot.demandId,
                    "requirementId": slot.requirementId,
                    "date": slot.date.isoformat(),
                    "slotId": slot.slot_id,
                    "shiftCode": slot.shiftCode,
                    "patternDay": None,
                    "startDateTime": slot.start.isoformat(),
                    "endDateTime": slot.end.isoformat(),
                    "employeeId": None,
                    "status": "UNASSIGNED",
                    "reason": "No employee could be assigned without violating hard constraints"
                }
                assignments.append(assignment)
                unassigned_count += 1
    
    print(f"  ✓ Extracted {assigned_count} assigned slots")
    print(f"  ✓ Extracted {unassigned_count} unassigned slots")
    print(f"  ✓ Total: {len(assignments)} entries\n")
    return assignments


def calculate_scores(ctx, assignments) -> tuple:
    """Calculate hard and soft constraint violation scores.
    
    Post-solution validation: Check assignments against known constraints.
    
    Args:
        ctx: Context dict with input configuration
        assignments: List of extracted assignments
    
    Returns:
        Tuple of (hard_score, soft_score, violations_list, score_breakdown)
    """
    print(f"[calculate_scores] Computing constraint violations...")
    
    # Initialize ScoreBook with solver config weights
    score_config = ctx.get('solverScoreConfig', {})
    score_book = ScoreBook(score_config)
    
    # Count assigned vs unassigned slots
    assigned_count = sum(1 for a in assignments if a.get('status') == 'ASSIGNED')
    unassigned_count = sum(1 for a in assignments if a.get('status') == 'UNASSIGNED')
    
    print(f"  Assigned slots: {assigned_count}")
    print(f"  Unassigned slots: {unassigned_count}")
    
    if len(assignments) == 0:
        score_book.hard("assignment_empty", "No assignments generated")
    
    # Count unassigned slots as hard violations (unfilled demand)
    # Analyze which constraints blocked each unassigned slot
    if unassigned_count > 0:
        print(f"  ℹ️  {unassigned_count} slots could not be filled without violating hard constraints")
        
        # Build lookup structures
        employees_list = ctx.get('employees', [])
        slots_list = ctx.get('slots', [])
        slots_dict = {s.slot_id: s for s in slots_list}
        
        for a in assignments:
            if a.get('status') == 'UNASSIGNED':
                slot_id = a.get('slotId')
                slot = slots_dict.get(slot_id)
                
                # Determine blocking constraint(s)
                blocking_reasons = []
                
                if slot:
                    slot_ranks = getattr(slot, 'rankIds', [])  # Changed from rankId to rankIds
                    slot_scheme = getattr(slot, 'schemeRequirement', 'Global')
                    slot_duration = (slot.end - slot.start).total_seconds() / 3600.0
                    slot_gender = getattr(slot, 'genderRequirement', None)
                    
                    # Build detailed blocking analysis
                    blocking_reasons = []
                    detailed_reasons = []
                    
                    # Build employee capabilities lookup
                    employee_ranks = {emp.get('employeeId'): emp.get('rankId') for emp in employees_list}
                    employee_schemes = {emp.get('employeeId'): emp.get('scheme', 'A') for emp in employees_list}
                    employee_genders = {emp.get('employeeId'): emp.get('gender') for emp in employees_list}
                    employee_types = {emp.get('employeeId'): emp.get('employmentType') for emp in employees_list}
                    
                    # Check C11: Rank mismatch - no employees with required ranks
                    if slot_ranks:
                        matching_ranks = [emp_id for emp_id, rank in employee_ranks.items() if rank in slot_ranks]
                        if not matching_ranks:
                            blocking_reasons.append('C11_rank_mismatch')
                            detailed_reasons.append(f"Required ranks {slot_ranks} not available in any employee")
                    
                    # Check C9: Gender requirement - no employees with required gender
                    # Note: "Any" means no gender restriction, so skip checking
                    if slot_gender and slot_gender not in ['Any', 'any', None]:
                        matching_genders = [emp_id for emp_id, gender in employee_genders.items() if gender == slot_gender]
                        if not matching_genders:
                            blocking_reasons.append('C9_gender_balance')
                            detailed_reasons.append(f"Required gender '{slot_gender}' not available")
                    
                    # Check C1: Scheme daily hours - shift too long for employee schemes
                    scheme_compatible = []
                    for emp_id, scheme in employee_schemes.items():
                        max_hours = {'P': 9.0, 'B': 13.0, 'A': 14.0}.get(scheme, 14.0)
                        if slot_duration <= max_hours:
                            scheme_compatible.append(emp_id)
                    
                    if not scheme_compatible:
                        blocking_reasons.append('C1_scheme_hours')
                        detailed_reasons.append(f"Shift {slot_duration:.1f}h exceeds all scheme limits (P:9h, B:13h, A:14h)")
                    
                    # Check for pattern-based issues
                    if hasattr(slot, 'position_index') and hasattr(slot, 'shiftPatternId'):
                        employee_patterns = {emp.get('employeeId'): emp.get('workPattern', '') for emp in employees_list}
                        compatible_patterns = [e for e, p in employee_patterns.items() if p]
                        if not compatible_patterns:
                            blocking_reasons.append('S1_rotation_pattern')
                            detailed_reasons.append(f"Pattern-based slot but no employees have work patterns")
                    
                    # If no specific reasons found, provide general analysis
                    if not blocking_reasons:
                        blocking_reasons.append('constraint_combination')
                        detailed_reasons.append(
                            f"Multiple hard constraints (work pattern, consecutive days, rest periods, "
                            f"weekly hours, or other MOM rules) prevented all employees from being assigned"
                        )
                
                # Record violation with detailed constraint info
                constraint_id = blocking_reasons[0] if blocking_reasons else 'unknown'
                reason_text = '; '.join(detailed_reasons) if detailed_reasons else 'Unknown constraint violation'
                
                score_book.hard(
                    f"hard_{constraint_id}",
                    f"Slot {slot_id} on {a.get('date')} unassigned - {reason_text}"
                )
    
    # Filter out unassigned slots for constraint checking (only check actual assignments)
    assigned_slots = [a for a in assignments if a.get('status') == 'ASSIGNED']
    
    # Filter out unassigned slots for constraint checking (only check actual assignments)
    assigned_slots = [a for a in assignments if a.get('status') == 'ASSIGNED']
    
    # ========== POST-SOLUTION CONSTRAINT VALIDATION ==========
    from context.engine.time_utils import split_shift_hours
    from collections import defaultdict
    from datetime import datetime
    
    # Aggregate assignments by employee and date (only assigned slots)
    emp_assignments_by_date = defaultdict(list)  # (emp_id, date) -> [assignments]
    emp_assignments_by_week = defaultdict(list)  # (emp_id, week) -> [assignments]
    emp_assignments_by_month = defaultdict(list)  # (emp_id, month) -> [assignments]
    
    employees = {emp.get('employeeId'): emp for emp in ctx.get('employees', [])}
    
    for a in assigned_slots:
        emp_id = a.get('employeeId')
        date_str = a.get('date')
        
        try:
            date_obj = datetime.fromisoformat(date_str).date()
            iso_year, iso_week, _ = date_obj.isocalendar()
            
            week_key = (emp_id, f"{iso_year}-W{iso_week:02d}")
            month_key = (emp_id, f"{iso_year}-{date_obj.month:02d}")
            date_key = (emp_id, date_str)
            
            emp_assignments_by_date[date_key].append(a)
            emp_assignments_by_week[week_key].append(a)
            emp_assignments_by_month[month_key].append(a)
        except:
            pass
    
    # ========== C1 CHECK: Daily Gross Hours by Scheme ==========
    max_gross_by_scheme = {'A': 14, 'B': 13, 'P': 9}
    for (emp_id, date_str), day_assignments in emp_assignments_by_date.items():
        emp = employees.get(emp_id, {})
        scheme = emp.get('scheme', 'A')
        max_gross = max_gross_by_scheme.get(scheme, 14)
        
        daily_gross = 0
        for a in day_assignments:
            start = datetime.fromisoformat(a.get('startDateTime'))
            end = datetime.fromisoformat(a.get('endDateTime'))
            hours_dict = split_shift_hours(start, end)
            daily_gross += hours_dict['gross']
        
        if daily_gross > max_gross:
            score_book.hard(
                "C1",
                f"{emp_id} on {date_str}: {daily_gross}h exceeds scheme {scheme} limit ({max_gross}h)"
            )
    
    # ========== C2a CHECK: Weekly Normal Hours (44h cap) ==========
    for (emp_id, week_key), week_assignments in emp_assignments_by_week.items():
        weekly_normal = 0
        for a in week_assignments:
            start = datetime.fromisoformat(a.get('startDateTime'))
            end = datetime.fromisoformat(a.get('endDateTime'))
            hours_dict = split_shift_hours(start, end)
            weekly_normal += hours_dict['normal']
        
        if weekly_normal > 44.0:
            score_book.hard(
                "C2",
                f"{emp_id} in {week_key}: {weekly_normal:.1f}h exceeds 44h weekly normal cap"
            )
    
    # ========== C17 CHECK: Monthly OT Hours (72h cap) ==========
    for (emp_id, month_key), month_assignments in emp_assignments_by_month.items():
        monthly_ot = 0
        for a in month_assignments:
            start = datetime.fromisoformat(a.get('startDateTime'))
            end = datetime.fromisoformat(a.get('endDateTime'))
            hours_dict = split_shift_hours(start, end)
            monthly_ot += hours_dict['ot']
        
        if monthly_ot > 72.0:
            score_book.hard(
                "C17",
                f"{emp_id} in {month_key}: {monthly_ot:.1f}h OT exceeds 72h monthly cap"
            )
    
    # ========== C3 CHECK: Max Consecutive Working Days (≤12) ==========
    planning_horizon = ctx.get('planningHorizon', {})
    try:
        start_date = datetime.fromisoformat(planning_horizon.get('startDate', '') + "T00:00:00").date()
        end_date = datetime.fromisoformat(planning_horizon.get('endDate', '') + "T23:59:59").date()
        
        for emp_id in employees.keys():
            # Get all working days for this employee
            working_dates = set()
            for (e_id, date_str), _ in emp_assignments_by_date.items():
                if e_id == emp_id:
                    try:
                        working_dates.add(datetime.fromisoformat(date_str).date())
                    except:
                        pass
            
            if not working_dates:
                continue
            
            # Find consecutive day sequences
            sorted_dates = sorted(working_dates)
            current_seq = [sorted_dates[0]]
            
            for i in range(1, len(sorted_dates)):
                days_diff = (sorted_dates[i] - sorted_dates[i-1]).days
                if days_diff == 1:
                    current_seq.append(sorted_dates[i])
                else:
                    # Sequence broken
                    if len(current_seq) > 12:
                        score_book.hard(
                            "C3",
                            f"{emp_id}: {len(current_seq)} consecutive days ({current_seq[0]} to {current_seq[-1]}) exceeds max 12"
                        )
                    current_seq = [sorted_dates[i]]
            
            # Check final sequence
            if len(current_seq) > 12:
                score_book.hard(
                    "C3",
                    f"{emp_id}: {len(current_seq)} consecutive days ({current_seq[0]} to {current_seq[-1]}) exceeds max 12"
                )
    except Exception as e:
        pass
    
    # ========== C5 CHECK: Minimum Off-Days Per Week (≥1 day off per 7 days) ==========
    try:
        for emp_id in employees.keys():
            # Get all working dates
            working_dates = set()
            for (e_id, date_str), _ in emp_assignments_by_date.items():
                if e_id == emp_id:
                    try:
                        working_dates.add(datetime.fromisoformat(date_str).date())
                    except:
                        pass
            
            if not working_dates:
                continue
            
            sorted_dates = sorted(working_dates)
            
            # Check 7-day rolling windows
            for i in range(len(sorted_dates) - 6):
                # 7-day window starting from sorted_dates[i]
                window_start = sorted_dates[i]
                window_end = sorted_dates[i] + __import__('datetime').timedelta(days=6)
                
                days_in_window = sum(1 for d in sorted_dates if window_start <= d <= window_end)
                
                if days_in_window == 7:
                    # Worked all 7 days - violation
                    score_book.hard(
                        "C5",
                        f"{emp_id}: Worked 7/7 days in period {window_start} to {window_end} (no off-days)"
                    )
    except Exception as e:
        pass
    
    # ========== C6 CHECK: Part-Timer Weekly Limits ==========
    part_timer_limits = {'≤4_days': 34.98, '>4_days': 29.98}
    for (emp_id, week_key), week_assignments in emp_assignments_by_week.items():
        emp = employees.get(emp_id, {})
        scheme = emp.get('scheme', 'A')
        
        # Only check part-timers (scheme P)
        if scheme != 'P':
            continue
        
        # Count working days in week
        working_days = len(set((a.get('date') for a in week_assignments)))
        
        # Calculate normal hours
        weekly_normal = 0
        for a in week_assignments:
            start = datetime.fromisoformat(a.get('startDateTime'))
            end = datetime.fromisoformat(a.get('endDateTime'))
            hours_dict = split_shift_hours(start, end)
            weekly_normal += hours_dict['normal']
        
        limit = 34.98 if working_days <= 4 else 29.98
        if weekly_normal > limit:
            score_book.hard(
                "C6",
                f"{emp_id} (scheme P) in {week_key}: {weekly_normal:.1f}h exceeds limit {limit}h for {working_days} days"
            )
    
    # ========== C7 CHECK: License Validity on Shift Date ==========
    for a in assigned_slots:
        emp_id = a.get('employeeId')
        emp = employees.get(emp_id, {})
        assignment_date = a.get('date')
        
        # Get required qualifications from demand
        demand_id = a.get('demandId')
        demand_items = ctx.get('demandItems', [])
        required_quals = set()
        for d in demand_items:
            if d.get('demandId') == demand_id:
                for shift in d.get('shifts', []):
                    required_quals.update(shift.get('requiredQualifications', []))
        
        if not required_quals:
            continue
        
        # Check if employee has valid licenses
        emp_licenses = {lic.get('code'): lic for lic in emp.get('licenses', [])}
        
        for req_qual in required_quals:
            if req_qual not in emp_licenses:
                score_book.hard(
                    "C7",
                    f"{emp_id} assigned on {assignment_date} lacks required qualification {req_qual}"
                )
            else:
                # Check expiry date
                lic = emp_licenses[req_qual]
                expiry = lic.get('expiryDate')
                if expiry:
                    try:
                        expiry_date = datetime.fromisoformat(expiry).date()
                        assign_date = datetime.fromisoformat(assignment_date).date()
                        if assign_date > expiry_date:
                            score_book.hard(
                                "C7",
                                f"{emp_id} on {assignment_date}: {req_qual} expired on {expiry_date}"
                            )
                    except:
                        pass
    
    # ========== C8 CHECK: Provisional License (PDL) Validity ==========
    for a in assigned_slots:
        emp_id = a.get('employeeId')
        emp = employees.get(emp_id, {})
        assignment_date = a.get('date')
        
        # Check for provisional licenses
        for lic in emp.get('licenses', []):
            if 'provisional' in lic.get('type', '').lower() or lic.get('type') == 'PDL':
                expiry = lic.get('expiryDate')
                if expiry:
                    try:
                        expiry_date = datetime.fromisoformat(expiry).date()
                        assign_date = datetime.fromisoformat(assignment_date).date()
                        if assign_date > expiry_date:
                            score_book.hard(
                                "C8",
                                f"{emp_id} on {assignment_date}: PDL expired on {expiry_date}"
                            )
                    except:
                        pass
    
    # ========== C9 CHECK: Gender Balance for Sensitive Roles ==========
    for a in assigned_slots:
        emp_id = a.get('employeeId')
        emp = employees.get(emp_id, {})
        date_str = a.get('date')
        demand_id = a.get('demandId')
        
        # Check if this demand has gender mix requirements
        demand_items = ctx.get('demandItems', [])
        requires_gender_check = False
        for d in demand_items:
            if d.get('demandId') == demand_id:
                for shift in d.get('shifts', []):
                    if shift.get('slotConstraints', {}).get('genderMix'):
                        requires_gender_check = True
                        break
        
        if requires_gender_check:
            # For now, just log that gender checking would happen here
            # Full implementation would aggregate all assignments for that demand on that date
            pass
    
    # ========== C10 CHECK: Skill/Role Match ==========
    for a in assigned_slots:
        emp_id = a.get('employeeId')
        emp = employees.get(emp_id, {})
        emp_skills = set(emp.get('skills', []))
        
        demand_id = a.get('demandId')
        demand_items = ctx.get('demandItems', [])
        required_skills = set()
        
        for d in demand_items:
            if d.get('demandId') == demand_id:
                for shift in d.get('shifts', []):
                    required_skills.update(shift.get('requiredSkills', []))
        
        if required_skills and not required_skills.issubset(emp_skills):
            missing_skills = required_skills - emp_skills
            score_book.hard(
                "C10",
                f"{emp_id} lacks required skills: {', '.join(missing_skills)}"
            )
    
    # ========== C11 CHECK: Rank/Product Type Match ==========
    # v0.95: rankIds (plural) supports multiple acceptable ranks - OR logic
    slots_dict = {s.slot_id: s for s in ctx.get('slots', [])}
    for a in assigned_slots:
        emp_id = a.get('employeeId')
        emp = employees.get(emp_id, {})
        emp_rank = emp.get('rankId', 'UNKNOWN')
        
        slot_id = a.get('slotId')
        slot = slots_dict.get(slot_id)
        
        if slot:
            slot_ranks = getattr(slot, 'rankIds', [])  # Changed from rankId to rankIds
            # Employee must match at least ONE of the acceptable ranks
            if slot_ranks and emp_rank not in slot_ranks:
                score_book.hard(
                    "C11",
                    f"{emp_id} rank {emp_rank} not in allowed ranks {slot_ranks}"
                )
    
    # ========== C15 CHECK: Qualification Expiry Override Control ==========
    for a in assigned_slots:
        emp_id = a.get('employeeId')
        emp = employees.get(emp_id, {})
        assignment_date = a.get('date')
        
        # Check for expired qualifications without valid temporary approval
        demand_id = a.get('demandId')
        demand_items = ctx.get('demandItems', [])
        required_quals = set()
        for d in demand_items:
            if d.get('demandId') == demand_id:
                for shift in d.get('shifts', []):
                    required_quals.update(shift.get('requiredQualifications', []))
        
        for req_qual in required_quals:
            # Find license
            for lic in emp.get('licenses', []):
                if lic.get('code') == req_qual:
                    expiry = lic.get('expiryDate')
                    if expiry:
                        try:
                            expiry_date = datetime.fromisoformat(expiry).date()
                            assign_date = datetime.fromisoformat(assignment_date).date()
                            if assign_date > expiry_date:
                                # Check if temporary approval exists
                                approval = lic.get('approvalCode') or lic.get('temporaryApproval')
                                if not approval:
                                    score_book.hard(
                                        "C15",
                                        f"{emp_id} on {assignment_date}: {req_qual} expired ({expiry_date}) with no approval override"
                                    )
                        except:
                            pass
    
    # ========== SOFT CONSTRAINT SCORING (S1-S16) ==========
    print(f"[calculate_scores] Evaluating soft constraints...")
    soft_constraints_scored = 0
    
    try:
        import os
        import importlib
        constraints_path = os.path.join(os.path.dirname(__file__), '..', 'constraints')
        
        # Get all S*.py files (soft constraints)
        for filename in sorted(os.listdir(constraints_path)):
            if filename.startswith('S') and filename.endswith('.py') and filename != '__init__.py':
                mod_name = filename[:-3]
                try:
                    mod = importlib.import_module(f"context.constraints.{mod_name}")
                    if hasattr(mod, "score_violations"):
                        # Pass assigned_slots only (not unassigned)
                        violations = mod.score_violations(ctx, assigned_slots, score_book)
                        soft_constraints_scored += 1
                        if violations > 0:
                            print(f"  {mod_name}: {violations} violations")
                except Exception as e:
                    print(f"  Warning: Could not score {mod_name}: {e}")
    except Exception as e:
        print(f"  Warning: Error loading soft constraints: {e}")
    
    print(f"  ✓ Scored {soft_constraints_scored} soft constraint modules\n")
    
    # ========== SUMMARY ==========
    hard_count = sum(1 for v in score_book.violations if v['type'] == 'hard')
    soft_count = sum(v.get('penalty', 0) for v in score_book.violations if v['type'] == 'soft')
    
    # Add unassigned slot metadata to score breakdown
    score_breakdown = {
        "hard": {
            "violations": [v for v in score_book.violations if v['type'] == 'hard']
        },
        "soft": {
            "totalPenalty": soft_count,
            "details": [v for v in score_book.violations if v['type'] == 'soft']
        },
        "unassignedSlots": {
            "count": unassigned_count,
            "total": len(assignments),
            "percentage": round(100 * unassigned_count / len(assignments), 2) if len(assignments) > 0 else 0,
            "slots": [
                {
                    "slotId": a.get('slotId'),
                    "demandId": a.get('demandId'),
                    "date": a.get('date'),
                    "shiftCode": a.get('shiftCode'),
                    "reason": a.get('reason', 'No feasible assignment')
                }
                for a in assignments if a.get('status') == 'UNASSIGNED'
            ]
        }
    }
    
    print(f"  Hard violations: {hard_count}")
    print(f"  Soft penalties: {soft_count}")
    print(f"  Unassigned slots: {unassigned_count}")
    print(f"  Total violations recorded: {len(score_book.violations)}\n")
    
    return hard_count, soft_count, score_book.violations, score_breakdown


def solve(ctx):
    """
    Main solver function.
    
    Process:
    1. Build model with decision variables and basic constraints
    2. Apply custom constraints from constraints/ directory
    3. Solve using CP-SAT solver
    4. Extract assignments from solution
    5. Calculate hard and soft scores
    6. Return status and results
    
    Returns:
        Tuple of (status_code, solver_result_dict, assignments_list, scores_dict)
    """
    start_time = time.time()
    start_timestamp = datetime.now().isoformat()
    
    print(f"\n{'='*80}")
    print(f"[SOLVER STARTING]")
    print(f"{'='*80}\n")
    
    model = build_model(ctx)
    apply_constraints(model, ctx)
    
    # ========== ADD GAP PENALTIES TO OBJECTIVE (S18) ==========
    # S18 creates gap tracking variables during add_constraints()
    # Now we need to incorporate them into the CP-SAT objective
    gap_penalty_vars = ctx.get('gap_penalty_vars', [])
    if gap_penalty_vars:
        # Get current objective expression components from ctx
        total_unassigned = ctx.get('total_unassigned')
        x = ctx.get('x', {})
        
        # Gap penalty weight (align with soft constraint priority)
        GAP_MULTIPLIER = 1_000  # Same as SOFT_MULTIPLIER
        
        # Calculate total gap penalty
        total_gap_penalty = sum(gap_penalty_vars)
        
        # Rebuild objective including gap penalties
        # Get optimization mode
        solver_config = ctx.get('solverConfig', {})
        optimization_mode = solver_config.get('optimizationMode', OPTIMIZATION_MODE_BALANCE)
        
        BIG_MULTIPLIER = 1_000_000
        MEDIUM_MULTIPLIER = 100_000
        SOFT_MULTIPLIER = 1_000
        
        total_assignments = sum(x.values())
        
        # Get existing penalty terms
        total_rotation_violations = ctx.get('total_rotation_violations', 0)
        total_anchor_penalty = ctx.get('total_anchor_penalty', 0)
        total_employees_used = ctx.get('total_employees_used', 0)
        
        print(f"[build_model] Updating objective with S18 gap penalties...")
        print(f"  Gap penalty variables: {len(gap_penalty_vars)}")
        print(f"  Gap penalty weight: {GAP_MULTIPLIER:,}×")
        
        if optimization_mode == OPTIMIZATION_MODE_MINIMIZE:
            objective_expr = (
                BIG_MULTIPLIER * total_unassigned +
                MEDIUM_MULTIPLIER * total_employees_used +
                SOFT_MULTIPLIER * total_rotation_violations +
                SOFT_MULTIPLIER * total_anchor_penalty +
                GAP_MULTIPLIER * total_gap_penalty -  # NEW: Gap penalties
                total_assignments
            )
        else:
            objective_expr = (
                BIG_MULTIPLIER * total_unassigned +
                SOFT_MULTIPLIER * total_rotation_violations +
                SOFT_MULTIPLIER * total_anchor_penalty +
                GAP_MULTIPLIER * total_gap_penalty -  # NEW: Gap penalties
                total_assignments
            )
        
        model.Minimize(objective_expr)
        print(f"  ✓ Objective updated with gap minimization\n")
    
    # Solve with adaptive time limit
    num_slots = len(ctx.get('slots', []))
    num_employees = len(ctx.get('employees', []))
    user_time_limit = ctx.get("timeLimit")
    time_limit = calculate_adaptive_time_limit(num_slots, num_employees, user_time_limit)
    
    # Configure CP-SAT parallelization
    user_num_workers = None
    cpsat_env = os.getenv("CPSAT_NUM_THREADS")
    if cpsat_env:
        try:
            user_num_workers = int(cpsat_env)
        except ValueError:
            pass
    
    num_search_workers = calculate_num_search_workers(num_slots, num_employees, user_num_workers)
    
    print(f"[solve] Running CP-SAT solver...")
    print(f"  Problem size: {num_slots} slots × {num_employees} employees")
    print(f"  Time limit: {time_limit}s{' (user-specified)' if user_time_limit else ' (adaptive)'}")
    print(f"  Parallel search workers: {num_search_workers}{' (env)' if user_num_workers else ' (adaptive)'}")
    
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = num_search_workers
    status = solver.Solve(model)
    
    print(f"[solve] Raw status code: {status} (OPTIMAL={cp_model.OPTIMAL}, FEASIBLE={cp_model.FEASIBLE}, INFEASIBLE={cp_model.INFEASIBLE}, MODEL_INVALID={cp_model.MODEL_INVALID})")
    
    # Extract optimized rotation offsets FIRST (before extracting assignments)
    # so they're available when building assignment records
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        if not ctx.get('fixedRotationOffset', True) and 'offset_vars' in ctx:
            print(f"[solve] Extracting optimized rotation offsets...")
            offset_vars = ctx['offset_vars']
            optimized_offsets = {}
            
            for emp_id, offset_var in offset_vars.items():
                optimized_offset = solver.Value(offset_var)
                optimized_offsets[emp_id] = optimized_offset
                print(f"  {emp_id}: offset = {optimized_offset}")
            
            # Store in ctx for extract_assignments to use
            ctx['optimized_offsets'] = optimized_offsets
            print(f"  ✓ Extracted {len(optimized_offsets)} optimized offsets\n")
    
    # Extract assignments
    assignments = []
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        assignments = extract_assignments(ctx, solver)
        print(f"[solve] Solution found with {len(assignments)} assignments")
    
    # Calculate scores with lazy evaluation
    # Only calculate soft scores if we have a feasible solution
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE] and assignments:
        hard_score, soft_score, violations, score_breakdown = calculate_scores(ctx, assignments)
    else:
        # Skip expensive soft constraint calculations for infeasible solutions
        hard_score = float('inf') if status == cp_model.INFEASIBLE else 0
        soft_score = 0
        violations = {}
        score_breakdown = {
            'hard': {'unassignedSlots': len(ctx.get('slots', []))},
            'soft': {}
        }
        print(f"[solve] Skipping soft constraint evaluation (status: {status})")
    
    end_time = time.time()
    end_timestamp = datetime.now().isoformat()
    duration_seconds = end_time - start_time
    
    # Map CP-SAT status to solver status string
    # Note: cp_model constants are: OPTIMAL=4, FEASIBLE=2, INFEASIBLE=3, MODEL_INVALID=1
    status_map = {
        1: "MODEL_INVALID",
        2: "FEASIBLE",
        3: "INFEASIBLE",
        4: "OPTIMAL"
    }
    solver_status = status_map.get(status, "UNKNOWN")  # type: ignore[arg-type]
    
    # Override status based on hard constraint violations
    # If there are unassigned slots (hard_score > 0), the solution is INFEASIBLE
    # regardless of what CP-SAT reports (CP-SAT allows unassigned via soft minimization)
    if hard_score > 0:
        solver_status = "INFEASIBLE"
        prev_status = status_map.get(status, "UNKNOWN")  # type: ignore[arg-type]
        print(f"[solve] Status override: {prev_status} → INFEASIBLE (hard_score={hard_score})")
    
    print(f"[solve] Status: {solver_status}")
    print(f"{'='*80}\n")
    
    # Calculate employee utilization statistics
    employees = ctx.get('employees', [])
    total_employees = len(employees)
    
    # Count employees by rotation offset type
    strict_adherence = 0
    flexible_employees = 0
    for emp in employees:
        offset = emp.get('rotationOffset', 0)
        if offset == -1:
            flexible_employees += 1
        else:
            strict_adherence += 1
    
    # Count employees who were actually assigned
    assigned_employee_ids = set()
    for assignment in assignments:
        if assignment.get('employeeId'):
            assigned_employee_ids.add(assignment['employeeId'])
    
    employees_assigned = len(assigned_employee_ids)
    employees_not_assigned = total_employees - employees_assigned
    
    employee_utilization = {
        "totalEmployees": total_employees,
        "strictAdherence": strict_adherence,
        "flexiblePattern": flexible_employees,
        "employeesAssigned": employees_assigned,
        "employeesNotAssigned": employees_not_assigned,
        "utilizationPercentage": round((employees_assigned / total_employees * 100), 1) if total_employees > 0 else 0
    }
    
    # Build solver result dict with scores
    solver_result = {
        "status_code": status,
        "status": solver_status,
        "start_timestamp": start_timestamp,
        "end_timestamp": end_timestamp,
        "duration_seconds": round(duration_seconds, 3),
        "scores": {
            "hard": hard_score,
            "soft": soft_score,
            "overall": hard_score + soft_score
        },
        "scoreBreakdown": score_breakdown,
        "employeeUtilization": employee_utilization
    }
    
    # Add optimized offsets to result if they were computed
    if 'optimized_offsets' in ctx:
        solver_result['optimizedRotationOffsets'] = ctx['optimized_offsets']
    
    return status, solver_result, assignments, violations

if __name__ == "__main__":
    ctx = load_input("../samples/input.sample.json")
    status, result, assignments, violations = solve(ctx)
    print("Solve status:", result['status'])
    print("Assignments:", len(assignments))
    print("Hard score:", result['scores']['hard'])
    print("Soft score:", result['scores']['soft'])
