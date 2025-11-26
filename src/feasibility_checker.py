"""
Fast Pre-Flight Feasibility Checker for NGRS Solver

Performs quick mathematical validation WITHOUT running CP-SAT solver.
Helps identify obvious infeasibility issues before expensive solver execution.

Uses config_optimizer logic for fast employee count estimation.
"""
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from collections import defaultdict
from math import ceil

from context.engine.coverage_simulator import calculate_min_employees


def quick_feasibility_check(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fast pre-flight feasibility check without running solver.
    
    Performs:
    1. Employee count validation (math-based, < 100ms)
    2. Role/rank matching (filtering)
    3. Gender/scheme matching (filtering)
    4. Basic demand coverage analysis
    
    Args:
        input_data: Full NGRS input JSON
        
    Returns:
        {
            "likely_feasible": bool,
            "confidence": "high" | "medium" | "low",
            "analysis": {
                "employees_provided": int,
                "employees_required_estimate": int,
                "shortfall": int,
                "by_requirement": [...]
            },
            "warnings": List[str],
            "recommendations": List[str]
        }
    """
    
    # Extract data
    employees = input_data.get('employees', [])
    demand_items = input_data.get('demandItems', [])
    planning_horizon = input_data.get('planningHorizon', {})
    constraint_list = input_data.get('constraintList', [])
    
    # Calculate planning days
    try:
        start_date = datetime.fromisoformat(planning_horizon.get('startDate', ''))
        end_date = datetime.fromisoformat(planning_horizon.get('endDate', ''))
        days_in_horizon = (end_date - start_date).days + 1
    except:
        days_in_horizon = 30  # Default assumption
    
    # Extract constraints
    constraints = _extract_constraints(constraint_list)
    
    # Analyze each requirement
    requirement_analysis = []
    total_required_min = 0
    total_required_max = 0
    warnings = []
    recommendations = []
    issues = []
    
    for demand in demand_items:
        for requirement in demand.get('requirements', []):
            analysis = _analyze_requirement(
                requirement, 
                demand, 
                employees, 
                days_in_horizon,
                constraints
            )
            requirement_analysis.append(analysis)
            total_required_min += analysis['employees_required_min']
            total_required_max += analysis['employees_required_max']
            
            if analysis['issues']:
                issues.extend(analysis['issues'])
    
    # Overall employee count check
    employees_provided = len(employees)
    shortfall_min = max(0, total_required_min - employees_provided)
    shortfall_max = max(0, total_required_max - employees_provided)
    
    # Determine feasibility
    likely_feasible = True
    confidence = "high"
    
    if shortfall_min > 0:
        likely_feasible = False
        confidence = "high"
        warnings.append(
            f"Insufficient employees: Need {total_required_min}-{total_required_max} but only {employees_provided} provided"
        )
        recommendations.append(
            f"Add {shortfall_min}-{shortfall_max} more employees matching required roles"
        )
    elif employees_provided < total_required_max * 1.1:
        # Within 10% of upper estimate - may work but tight
        confidence = "medium"
        warnings.append(
            f"Tight employee count: {employees_provided} provided, estimate needs {total_required_min}-{total_required_max}"
        )
        warnings.append("Solver may find solution but with limited flexibility")
    else:
        confidence = "high"
    
    # Add specific issues
    if issues:
        likely_feasible = False
        warnings.extend(issues[:3])  # Show top 3 issues
        
        if len(issues) > 3:
            warnings.append(f"...and {len(issues) - 3} more issues")
    
    # Generate recommendations based on issues
    if "No matching employees" in str(issues):
        recommendations.append("Check that employee productTypeId/rankId matches demand requirements")
    
    if "gender" in str(issues).lower():
        recommendations.append("Add employees of required gender for gender-specific demands")
    
    if "scheme" in str(issues).lower():
        recommendations.append("Add employees with matching scheme (A/B/P) for scheme-specific requirements")
    
    return {
        "likely_feasible": likely_feasible,
        "confidence": confidence,
        "analysis": {
            "employees_provided": employees_provided,
            "employees_required_min": total_required_min,
            "employees_required_max": total_required_max,
            "shortfall": shortfall_min,
            "planning_days": days_in_horizon,
            "by_requirement": requirement_analysis
        },
        "warnings": warnings if warnings else None,
        "recommendations": recommendations if recommendations else None
    }


def _extract_constraints(constraint_list: List[Dict]) -> Dict[str, Any]:
    """Extract key constraints for feasibility calculation."""
    constraints = {
        'maxConsecutiveWorkDays': 12,
        'minOffDaysPerWeek': 1,
        'maxWeeklyNormalHours': 44.0
    }
    
    for c in constraint_list:
        constraint_id = c.get('id', '')
        params = c.get('params', {})
        
        if 'maxConsecutiveWorkDays' in constraint_id.lower():
            constraints['maxConsecutiveWorkDays'] = params.get('maxDays', 12)
        elif 'oneoffperweek' in constraint_id.lower():
            if params.get('required'):
                constraints['minOffDaysPerWeek'] = 1
        elif 'weeklyHoursCap' in constraint_id.lower():
            max_minutes = params.get('maxMinutesPerWeek', 2640)
            constraints['maxWeeklyNormalHours'] = max_minutes / 60.0
    
    return constraints


def _analyze_requirement(
    requirement: Dict,
    demand: Dict,
    employees: List[Dict],
    days_in_horizon: int,
    constraints: Dict
) -> Dict[str, Any]:
    """
    Analyze single requirement for feasibility.
    
    Returns estimated employee count and issues.
    """
    req_id = requirement.get('requirementId', 'unknown')
    headcount = requirement.get('headcount', 1)
    work_pattern = requirement.get('workPattern', [])
    product_type = requirement.get('productTypeId', '')
    rank_id = requirement.get('rankId', '')
    gender_req = requirement.get('gender', 'Any')
    scheme_req = requirement.get('Scheme', 'Global')
    
    issues = []
    
    # Filter matching employees
    matching_employees = _filter_matching_employees(
        employees, 
        product_type, 
        rank_id, 
        gender_req, 
        scheme_req
    )
    
    matching_count = len(matching_employees)
    
    if matching_count == 0:
        issues.append(
            f"Requirement {req_id}: No matching employees for {product_type}/{rank_id}"
        )
    
    # Check gender availability if specific gender required
    if gender_req in ['M', 'F', 'Male', 'Female']:
        gender_count = sum(1 for emp in matching_employees 
                          if emp.get('gender', '').upper().startswith(gender_req[0]))
        if gender_count == 0:
            issues.append(
                f"Requirement {req_id}: No {gender_req} employees available"
            )
    
    # Calculate required employees using work pattern
    if work_pattern:
        cycle_length = len(work_pattern)
        work_days = sum(1 for d in work_pattern if d != 'O')
    else:
        # Default assumption: 4 on, 2 off
        cycle_length = 6
        work_days = 4
    
    # Get shift hours (use default 11.0 = 12 gross - 1 lunch)
    shift_hours = 11.0
    
    # Use coverage simulator calculation
    min_employees = calculate_min_employees(
        pattern=work_pattern if work_pattern else ['D'] * work_days + ['O'] * (cycle_length - work_days),
        headcount_per_day=headcount,
        days_in_horizon=days_in_horizon,
        max_weekly_hours=constraints.get('maxWeeklyNormalHours', 44.0),
        shift_normal_hours=shift_hours
    )
    
    # Add 20% buffer for max estimate (accounts for constraints, unavailability, etc.)
    max_employees = ceil(min_employees * 1.2)
    
    # Check if we have enough matching employees
    if matching_count < min_employees:
        issues.append(
            f"Requirement {req_id}: Need {min_employees}-{max_employees} employees but only {matching_count} match"
        )
    
    return {
        "requirement_id": req_id,
        "product_type": product_type,
        "rank_id": rank_id,
        "headcount": headcount,
        "work_pattern": work_pattern,
        "employees_required_min": min_employees,
        "employees_required_max": max_employees,
        "employees_matching": matching_count,
        "sufficient": matching_count >= min_employees,
        "issues": issues
    }


def _filter_matching_employees(
    employees: List[Dict],
    product_type: str,
    rank_id: str,
    gender_req: str,
    scheme_req: str
) -> List[Dict]:
    """Filter employees matching requirement criteria."""
    matching = []
    
    for emp in employees:
        # Check product type
        emp_product = emp.get('productTypeId', '')
        if product_type and emp_product != product_type:
            continue
        
        # Check rank
        emp_rank = emp.get('rankId', '')
        if rank_id and emp_rank != rank_id:
            continue
        
        # Check gender (if specific gender required)
        if gender_req in ['M', 'F', 'Male', 'Female']:
            emp_gender = emp.get('gender', '').upper()
            req_gender = gender_req[0].upper()
            if emp_gender != req_gender:
                continue
        
        # Check scheme (if not Global)
        if scheme_req != 'Global':
            emp_scheme = emp.get('scheme', '')
            if emp_scheme != scheme_req:
                continue
        
        matching.append(emp)
    
    return matching
