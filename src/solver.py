"""
Unified Solver Core Module

This module encapsulates ALL solver logic in one place:
- ICPMP preprocessing (employee filtering, pattern assignment)
- Offset staggering (when patterns exist but offsets not staggered)
- CP-SAT model building (slot generation, variables, constraints)
- Solving (CP-SAT execution)
- Output building (result formatting)

Both redis_worker.py (API) and run_solver.py (CLI) call solve_problem().
This ensures consistent behavior and eliminates code duplication.

CRITICAL: Preprocessing Strategy
- If employees have NO patterns → Run ICPMP (filters + assigns patterns/offsets)
- If employees have patterns → Stagger offsets only (no ICPMP needed)
- ICPMP assigns offsets itself, so no staggering needed after ICPMP

Architecture:
    redis_worker.py → solve_problem() → result
    run_solver.py → solve_problem() → result
"""

import time
import logging
from datetime import datetime
from typing import Dict, Any

from context.engine.data_loader import load_input
from context.engine.solver_engine import solve
from context.engine.template_roster import generate_template_validated_roster
from src.output_builder import build_output
from src.preprocessing.icpmp_integration import ICPMPPreprocessor
from src.offset_manager import ensure_staggered_offsets

logger = logging.getLogger(__name__)


def solve_problem(input_data: Dict[str, Any], log_prefix: str = "[SOLVER]") -> Dict[str, Any]:
    """
    Unified solver function - handles complete workflow from input to output.
    
    Workflow:
        1. Determine preprocessing strategy (ICPMP vs offset staggering)
        2. ICPMP: Filter employees (171→14) + assign patterns + offsets
           OR ensure_staggered_offsets: Fix offsets for existing patterns
        3. Load input into context dict
        4. Build CP-SAT model (includes slot generation via build_slots)
        5. Apply constraints (C1-C17 hard, S1-S18 soft)
        6. Solve with CP-SAT
        7. Build output with metadata
    
    Args:
        input_data: Input JSON as dict (employees, demands, constraints, etc.)
        log_prefix: Log prefix for identification (e.g., "[WORKER-1]", "[CLI]")
    
    Returns:
        Output JSON as dictionary with:
        - status: "OPTIMAL", "FEASIBLE", "INFEASIBLE", etc.
        - assignments: List of employee assignments
        - summary: Statistics about the solution
        - preprocessingMetadata: ICPMP filtering details (if ICPMP ran)
        - metadata: Solver timing and configuration
    """
    overall_start = time.time()
    
    # ═══════════════════════════════════════════════════════════
    # PHASE 1: PREPROCESSING STRATEGY DECISION
    # ═══════════════════════════════════════════════════════════
    
    employees = input_data.get('employees', [])
    employees_with_patterns = sum(1 for e in employees if e.get('workPattern'))
    
    # Check rosteringBasis from demandItems (new location) or root (backward compatibility)
    # IMPORTANT: Extract from RAW input_data before load_input() processing
    rostering_basis = None
    demand_items = input_data.get('demandItems', [])
    if demand_items and len(demand_items) > 0:
        rostering_basis = demand_items[0].get('rosteringBasis')
    if not rostering_basis:
        rostering_basis = input_data.get('rosteringBasis', 'demandBased')
    
    # Determine if ICPMP preprocessing is needed
    # - ICPMP runs ONLY for demandBased mode
    # - outcomeBased mode skips ICPMP entirely
    needs_icpmp = (
        rostering_basis == 'demandBased' and 
        employees_with_patterns == 0 and 
        len(employees) > 0
    )
    
    icpmp_metadata = None
    preprocessing_time = 0
    
    if rostering_basis == 'outcomeBased':
        # OUTCOME-BASED MODE: Skip ICPMP
        print(f"{log_prefix} ======================================================================")
        print(f"{log_prefix} OUTCOME-BASED ROSTERING MODE")
        print(f"{log_prefix} ======================================================================")
        print(f"{log_prefix} Skipping ICPMP preprocessing (outcomeBased mode)")
        print(f"{log_prefix} Using all {len(employees)} employees with OU-based rotation offsets")
        print()
    
    elif needs_icpmp:
        # SCENARIO A: DEMAND-BASED MODE with no patterns → Run ICPMP
        # - ICPMP filters employees (e.g., 171 → 14)
        # - ICPMP assigns rotation offsets (0, 1, 2, 3...)
        # - ICPMP assigns rotated work patterns
        # - NO need for ensure_staggered_offsets() afterward
        
        print(f"{log_prefix} ======================================================================")
        print(f"{log_prefix} ICPMP v3.0 PREPROCESSING (demandBased mode)")
        print(f"{log_prefix} ======================================================================")
        print(f"{log_prefix} Input: {len(employees)} employees, {employees_with_patterns} have patterns")
        
        preprocessing_start = time.time()
        
        try:
            preprocessor = ICPMPPreprocessor(input_data)
            preprocessing_result = preprocessor.preprocess_all_requirements()
            
            # Replace employee list with filtered, optimized employees
            input_data['employees'] = preprocessing_result['filtered_employees']
            
            preprocessing_time = time.time() - preprocessing_start
            
            print(f"{log_prefix} ✓ ICPMP preprocessing completed")
            print(f"{log_prefix} ✓ Filtered: {len(employees)} → {len(preprocessing_result['filtered_employees'])} employees")
            print(f"{log_prefix} ✓ Utilization: {preprocessing_result['summary']['utilization_rate']:.1%}")
            print(f"{log_prefix} ✓ Time: {preprocessing_time:.2f}s")
            print()
            
            # Store ICPMP metadata for output
            icpmp_metadata = {
                'enabled': True,
                'preprocessing_time_seconds': preprocessing_time,
                'original_employee_count': len(employees),
                'selected_employee_count': len(preprocessing_result['filtered_employees']),
                'utilization_percentage': preprocessing_result['summary']['utilization_rate'] * 100,
                'requirements': preprocessing_result['icpmp_metadata'],
                'warnings': preprocessing_result.get('warnings', [])
            }
            
        except Exception as preprocessing_error:
            # If preprocessing fails, log error and continue with original employee list
            print(f"{log_prefix} ❌ ICPMP preprocessing failed: {preprocessing_error}")
            print(f"{log_prefix} ⚠ Continuing with original employee list")
            print()
            
            icpmp_metadata = {
                'enabled': False,
                'warnings': [f"Preprocessing failed: {str(preprocessing_error)}"]
            }
        
        # Apply offset management after ICPMP based on mode
        fixed_rotation_offset_mode = input_data.get('fixedRotationOffset', 'auto')
        
        if fixed_rotation_offset_mode == 'auto':
            # AUTO MODE: Redistribute filtered employees across all offsets
            print(f"{log_prefix} ======================================================================")
            print(f"{log_prefix} APPLYING AUTO OFFSETS (after ICPMP)")
            print(f"{log_prefix} ======================================================================")
            input_data = ensure_staggered_offsets(input_data)
            print(f"{log_prefix} ✓ Auto offsets applied to {len(input_data.get('employees', []))} employees")
            print()
        elif fixed_rotation_offset_mode == 'ouOffsets':
            # OU OFFSETS MODE: Override ICPMP offsets with OU-specific offsets
            print(f"{log_prefix} ======================================================================")
            print(f"{log_prefix} APPLYING OU-BASED OFFSETS (after ICPMP)")
            print(f"{log_prefix} ======================================================================")
            input_data = ensure_staggered_offsets(input_data)
            print(f"{log_prefix} ✓ OU offsets applied")
            print()
    
    elif employees_with_patterns > 0:
        # SCENARIO B: DEMAND-BASED MODE with patterns → Check if offsets need staggering
        # - Employees already have work patterns
        # - May need to stagger offsets if all are 0
        # - NO ICPMP needed
        
        print(f"{log_prefix} ======================================================================")
        print(f"{log_prefix} OFFSET STAGGERING (demandBased mode)")
        print(f"{log_prefix} ======================================================================")
        print(f"{log_prefix} Employees have patterns, ensuring staggered offsets...")
        
        input_data = ensure_staggered_offsets(input_data)
        print(f"{log_prefix} ✓ Offsets staggered")
        print()
    
    else:
        print(f"{log_prefix} No employees in input, skipping preprocessing")
        print()
    
    # ═══════════════════════════════════════════════════════════
    # PHASE 2: LOAD INPUT & BUILD CONTEXT
    # ═══════════════════════════════════════════════════════════
    
    print(f"{log_prefix} Loading input into solver context...")
    ctx = load_input(input_data)
    ctx['timeLimit'] = input_data.get('solverRunTime', {}).get('maxSeconds', 15)
    
    # Apply OU offsets for outcomeBased mode (after load_input creates _ouOffsetMap)
    if rostering_basis == 'outcomeBased':
        employees = ctx.get('employees', [])
        ou_offset_map = ctx.get('_ouOffsetMap', {})
        if ou_offset_map:
            print(f"{log_prefix} Applying OU rotation offsets from {len(ou_offset_map)} organizational units")
            assigned_count = 0
            for emp in employees:
                ou_id = emp.get('ouId')
                if ou_id and ou_id in ou_offset_map:
                    emp['rotationOffset'] = ou_offset_map[ou_id]
                    assigned_count += 1
                elif 'rotationOffset' not in emp:
                    emp['rotationOffset'] = 0  # Default offset
            print(f"{log_prefix} ✓ Assigned rotation offsets to {assigned_count}/{len(employees)} employees")
        else:
            print(f"{log_prefix} ⚠️  WARNING: No ouOffsets found, defaulting all employees to offset=0")
            for emp in employees:
                if 'rotationOffset' not in emp:
                    emp['rotationOffset'] = 0
        
        # Calculate target employee count AFTER rank filtering (uses filtered count)
        demand_items = input_data.get('demandItems', [])
        if demand_items and len(demand_items) > 0:
            min_threshold = demand_items[0].get('minStaffThresholdPercentage', 100)
            # Use FILTERED employee count (after rank filtering in load_input)
            target_employee_count = int(len(employees) * min_threshold / 100)
            ctx['_targetEmployeeCount'] = target_employee_count
            print(f"{log_prefix} ✓ Target staffing: {min_threshold}% of {len(employees)} filtered employees = {target_employee_count} minimum")
    
    # Attach ICPMP metadata to context (build_output will include it)
    if icpmp_metadata:
        ctx['icpmp_preprocessing'] = icpmp_metadata
    
    # ═══════════════════════════════════════════════════════════
    # PHASE 3: ROSTER GENERATION (MODE-DEPENDENT)
    # ═══════════════════════════════════════════════════════════
    
    if rostering_basis == 'outcomeBased':
        # OUTCOME-BASED ROSTER GENERATION (Template Validation)
        print(f"{log_prefix} ======================================================================")
        print(f"{log_prefix} OUTCOME-BASED ROSTERING (TEMPLATE VALIDATION)")
        print(f"{log_prefix} ======================================================================")
        print(f"{log_prefix} Method: Generate template per OU → validate constraints → replicate")
        print(f"{log_prefix} Constraints: C1-C17 (core MOM regulatory constraints)")
        print()
        
        solver_start = time.time()
        start_timestamp = datetime.now().isoformat()
        
        # Get selected employees from ctx
        selected_emp_ids = ctx.get('_selectedEmployeeIds', set())
        if not selected_emp_ids:
            all_employees = ctx.get('employees', [])
            threshold = ctx.get('_targetEmployeeCount', len(all_employees))
            selected_employees = all_employees[:threshold]
        else:
            all_employees = ctx.get('employees', [])
            selected_employees = [emp for emp in all_employees if emp['employeeId'] in selected_emp_ids]
        
        # Get first requirement
        demand_items = input_data.get('demandItems', [])
        requirements = demand_items[0].get('requirements', []) if demand_items else []
        if not requirements:
            requirements = demand_items[0].get('shifts', [{}])[0].get('workRequirements', []) if demand_items else []
        
        requirement = requirements[0] if requirements else {}
        demand = demand_items[0] if demand_items else {}
        
        # Generate template-validated roster
        assignments, stats = generate_template_validated_roster(ctx, selected_employees, requirement, demand)
        
        solver_time = time.time() - solver_start
        end_timestamp = datetime.now().isoformat()
        stats['generation_time'] = solver_time
        
        # Set status based on results
        has_unassigned = any(a.get('status') == 'UNASSIGNED' for a in assignments)
        status_code = "FEASIBLE" if has_unassigned else "OPTIMAL"
        
        solver_result = {
            'status': status_code,
            'start_timestamp': start_timestamp,
            'end_timestamp': end_timestamp,
            'duration_seconds': solver_time,
            'scores': {'hard': stats.get('unassigned_count', 0), 'soft': 0, 'overall': stats.get('unassigned_count', 0)},
            'metadata': {
                'method': 'template_validation',
                'optimization': False,
                'constraints_validated': ['C1', 'C2', 'C3', 'C4', 'C5', 'C17'],
                'stats': stats
            }
        }
        violations = {}
        
        print(f"{log_prefix} ✓ Template roster generated in {solver_time:.2f}s")
        print(f"{log_prefix} Status: {status_code}")
        print(f"{log_prefix} Assignments: {stats['assigned_count']} assigned, {stats['unassigned_count']} unassigned")
        print(f"{log_prefix} Employees: {stats['employees_used']}/{stats['total_available_employees']}")
        print()
        
    else:
        # DEMAND-BASED ROSTERING (CP-SAT)
        print(f"{log_prefix} Starting CP-SAT solver...")
        solver_start = time.time()
        
        status_code, solver_result, assignments, violations = solve(ctx)
        
        solver_time = time.time() - solver_start
        print(f"{log_prefix} ✓ CP-SAT completed in {solver_time:.2f}s")
        print(f"{log_prefix} Status: {status_code}")
        print(f"{log_prefix} Assignments: {len(assignments)}")
        print()
    
    # ═══════════════════════════════════════════════════════════
    # PHASE 4: BUILD OUTPUT
    # ═══════════════════════════════════════════════════════════
    
    print(f"{log_prefix} Building output JSON...")
    result = build_output(
        input_data, ctx, status_code, solver_result, assignments, violations
    )
    
    total_time = time.time() - overall_start
    print(f"{log_prefix} ✓ Total time: {total_time:.2f}s (ICPMP: {preprocessing_time:.2f}s, Solve: {solver_time:.2f}s)")
    
    return result
