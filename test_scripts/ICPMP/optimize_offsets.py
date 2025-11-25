#!/usr/bin/env python3
"""Automatic rotation offset optimization.

This script finds optimal rotationOffset values for employees to maximize slot coverage.

Strategy:
1. Group employees by (productType, scheme, workPattern)
2. For each group, try different offset combinations
3. Run solver for each combination
4. Select configuration with highest coverage (fewest unassigned slots)

Usage:
    python optimize_offsets.py --in input/input_v0.7.json --out input/input_optimized.json
"""

import sys
import json
import argparse
from itertools import product
from copy import deepcopy
from context.engine.data_loader import load_input
from context.engine.solver_engine import solve


def group_employees_by_pattern(ctx):
    """Group employees that should have coordinated offsets.
    
    Returns:
        dict: {group_key: [employee_ids]}
    """
    employees = ctx.get('employees', [])
    groups = {}
    
    for emp in employees:
        emp_id = emp.get('employeeId')
        product_type = emp.get('productTypeId', '')
        scheme = emp.get('scheme', '')
        
        # Group key: employees with same role/scheme should coordinate
        group_key = f"{product_type}_{scheme}"
        
        if group_key not in groups:
            groups[group_key] = []
        groups[group_key].append(emp_id)
    
    return groups


def try_offset_combination(ctx, group_offsets):
    """Run solver with specific offset combination.
    
    Args:
        ctx: Context dict
        group_offsets: dict mapping employee_id to offset value
    
    Returns:
        tuple: (unassigned_count, assignments)
    """
    # Create modified context with new offsets
    ctx_copy = deepcopy(ctx)
    
    for emp in ctx_copy['employees']:
        emp_id = emp.get('employeeId')
        if emp_id in group_offsets:
            emp['rotationOffset'] = group_offsets[emp_id]
    
    # Run solver
    try:
        status, result, assignments, violations = solve(ctx_copy)
        
        # Count unassigned slots
        unassigned = sum(1 for a in assignments if not a.get('employeeId'))
        
        return unassigned, result, assignments
    except Exception as e:
        print(f"  ⚠️  Solver failed with error: {e}")
        return float('inf'), None, []


def optimize_group_offsets(ctx, group_name, employee_ids, max_iterations=50):
    """Find optimal offsets for a group of employees.
    
    Strategy:
    - For small groups (≤4): Try all combinations
    - For larger groups: Use greedy/staggered approach
    
    Args:
        ctx: Context dict
        group_name: Name of employee group
        employee_ids: List of employee IDs in group
        max_iterations: Maximum solver runs to try
    
    Returns:
        dict: {employee_id: optimal_offset}
    """
    print(f"\n{'='*80}")
    print(f"Optimizing offsets for group: {group_name}")
    print(f"  Employees: {len(employee_ids)}")
    print(f"{'='*80}\n")
    
    # Get pattern length from first employee
    pattern_length = 6  # Default
    for emp in ctx.get('employees', []):
        if emp.get('employeeId') == employee_ids[0]:
            # Try to get pattern from demand requirements
            # For now, assume 6-day cycle
            break
    
    # Strategy depends on group size
    if len(employee_ids) <= 4:
        # EXHAUSTIVE: Try all combinations
        print(f"Strategy: Exhaustive search (all combinations)")
        print(f"  Total combinations: {pattern_length ** len(employee_ids)}")
        
        best_unassigned = float('inf')
        best_offsets = None
        best_result = None
        
        # Generate all offset combinations
        offset_ranges = [range(pattern_length) for _ in employee_ids]
        
        for iteration, offset_combo in enumerate(product(*offset_ranges)):
            if iteration >= max_iterations:
                print(f"  Reached max iterations ({max_iterations})")
                break
            
            # Map employee IDs to offsets
            group_offsets = {emp_id: offset for emp_id, offset in zip(employee_ids, offset_combo)}
            
            print(f"  Try {iteration+1}: offsets={list(offset_combo)}", end=" ")
            
            unassigned, result, assignments = try_offset_combination(ctx, group_offsets)
            
            print(f"→ {len([a for a in assignments if a.get('employeeId')])}/{len(assignments)} slots filled")
            
            if unassigned < best_unassigned:
                best_unassigned = unassigned
                best_offsets = group_offsets
                best_result = result
                print(f"    ✅ NEW BEST! ({len(assignments) - unassigned}/{len(assignments)} filled)")
            
            # Early exit if perfect solution found
            if unassigned == 0:
                print(f"    🎉 PERFECT SOLUTION FOUND!")
                break
        
        return best_offsets, best_result
    
    else:
        # GREEDY: Stagger offsets evenly
        print(f"Strategy: Greedy staggered offsets")
        
        # Start with evenly distributed offsets
        offsets = {}
        for i, emp_id in enumerate(employee_ids):
            offsets[emp_id] = i % pattern_length
        
        print(f"  Initial staggered offsets: {[offsets[emp_id] for emp_id in employee_ids]}")
        
        unassigned, result, assignments = try_offset_combination(ctx, offsets)
        print(f"  Result: {len(assignments) - unassigned}/{len(assignments)} slots filled\n")
        
        return offsets, result


def main():
    parser = argparse.ArgumentParser(description='Optimize rotation offsets for maximum coverage')
    parser.add_argument('--in', dest='input_file', required=True, help='Input JSON file')
    parser.add_argument('--out', dest='output_file', help='Output JSON file with optimized offsets')
    parser.add_argument('--max-iter', type=int, default=50, help='Max iterations per group (default: 50)')
    
    args = parser.parse_args()
    
    print(f"\n{'='*80}")
    print(f"ROTATION OFFSET OPTIMIZER")
    print(f"{'='*80}\n")
    print(f"Input: {args.input_file}")
    
    # Load input
    ctx = load_input(args.input_file)
    
    # Get baseline (current offsets)
    print(f"\n{'='*80}")
    print(f"BASELINE: Current Configuration")
    print(f"{'='*80}\n")
    
    baseline_status, baseline_result, baseline_assignments, _ = solve(ctx)
    baseline_unassigned = sum(1 for a in baseline_assignments if not a.get('employeeId'))
    baseline_filled = len(baseline_assignments) - baseline_unassigned
    
    print(f"\n✓ Baseline: {baseline_filled}/{len(baseline_assignments)} slots filled ({baseline_unassigned} unassigned)")
    
    # Group employees
    groups = group_employees_by_pattern(ctx)
    
    print(f"\n{'='*80}")
    print(f"Employee Groups:")
    print(f"{'='*80}")
    for group_name, emp_ids in groups.items():
        print(f"  {group_name}: {len(emp_ids)} employees")
    print()
    
    # Optimize each group
    all_optimized_offsets = {}
    
    for group_name, emp_ids in groups.items():
        if len(emp_ids) > 1:  # Only optimize groups with multiple employees
            optimized_offsets, result = optimize_group_offsets(ctx, group_name, emp_ids, args.max_iter)
            all_optimized_offsets.update(optimized_offsets)
    
    # Apply optimized offsets and run final solver
    print(f"\n{'='*80}")
    print(f"FINAL OPTIMIZATION")
    print(f"{'='*80}\n")
    
    for emp in ctx['employees']:
        emp_id = emp.get('employeeId')
        if emp_id in all_optimized_offsets:
            old_offset = emp.get('rotationOffset', 0)
            new_offset = all_optimized_offsets[emp_id]
            emp['rotationOffset'] = new_offset
            print(f"  {emp_id}: offset {old_offset} → {new_offset}")
    
    # Final solve
    print(f"\nRunning final solver with optimized offsets...")
    final_status, final_result, final_assignments, _ = solve(ctx)
    final_unassigned = sum(1 for a in final_assignments if not a.get('employeeId'))
    final_filled = len(final_assignments) - final_unassigned
    
    print(f"\n{'='*80}")
    print(f"RESULTS")
    print(f"{'='*80}")
    print(f"  Baseline: {baseline_filled}/{len(baseline_assignments)} slots filled")
    print(f"  Optimized: {final_filled}/{len(final_assignments)} slots filled")
    print(f"  Improvement: +{final_filled - baseline_filled} slots")
    print(f"{'='*80}\n")
    
    # Save optimized input if requested
    if args.output_file:
        # Load original input to preserve structure
        with open(args.input_file, 'r') as f:
            original_input = json.load(f)
        
        # Update only the rotationOffset values
        for emp in original_input.get('employees', []):
            emp_id = emp.get('employeeId')
            if emp_id in all_optimized_offsets:
                emp['rotationOffset'] = all_optimized_offsets[emp_id]
        
        # Save
        with open(args.output_file, 'w') as f:
            json.dump(original_input, f, indent=2)
        
        print(f"✓ Saved optimized input to: {args.output_file}\n")


if __name__ == '__main__':
    main()
