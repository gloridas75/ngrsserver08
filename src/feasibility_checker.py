"""
Fast Pre-Flight Feasibility Checker for NGRS Solver

Performs quick mathematical validation WITHOUT running CP-SAT solver.
Helps identify obvious infeasibility issues before expensive solver execution.

UPGRADED: Uses ICPMP v2.0 logic for accurate employee count estimation.
"""
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from collections import defaultdict
from math import ceil

# ICPMP v2.0: Use sophisticated coverage simulation
from context.engine.config_optimizer_v3 import simulate_coverage_with_preprocessing


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
    Analyze single requirement for feasibility using ICPMP v2.0 logic.
    
    Returns estimated employee count and issues.
    """
    req_id = requirement.get('requirementId', 'unknown')
    headcount = requirement.get('headcount', 1)
    work_pattern = requirement.get('workPattern', [])
    product_type = requirement.get('productTypeId', '')
    rank_id = requirement.get('rankId', '')
    gender_req = requirement.get('gender', 'Any')
    # Normalize scheme: "Scheme P" → "P", "Scheme A" → "A", etc.
    scheme_req_raw = requirement.get('Scheme', 'Global')
    scheme_map = data.get('schemeMap', {})
    scheme_req = _normalize_scheme(scheme_req_raw, scheme_map)
    coverage_days = requirement.get('coverageDays', ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])
    
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
    
    # ICPMP v2.0: Use coverage-aware simulation for accurate estimates
    if work_pattern and len(work_pattern) > 0:
        pattern = work_pattern
    else:
        # Default pattern: 4 on, 2 off (6-day cycle)
        pattern = ['D', 'D', 'D', 'D', 'O', 'O']
    
    # Validate pattern length matches coverage days
    if len(pattern) != len(coverage_days):
        # Adjust pattern to match coverage days
        cycle_length = len(coverage_days)
        work_days = max(1, int(cycle_length * 0.7))  # ~70% work days
        pattern = ['D'] * work_days + ['O'] * (cycle_length - work_days)
    
    try:
        # Use ICPMP v2.0 simulation for accurate employee count
        start_date = datetime(2026, 1, 1)  # Use arbitrary start date for simulation
        
        # Calculate reasonable available_employees for simulation
        # We want strict + flexible employees, not truly flexible
        cycle_length = len(pattern)
        work_days = sum(1 for d in pattern if d != 'O')
        rough_estimate = ceil(headcount / (work_days / cycle_length)) if cycle_length > 0 else headcount * 2
        available_for_sim = min(200, max(rough_estimate * 3, 20))  # Give generous pool but not excessive
        
        sim_result = simulate_coverage_with_preprocessing(
            pattern=pattern,
            headcount=headcount,
            coverage_days=coverage_days,
            days_in_horizon=days_in_horizon,
            start_date=start_date,
            available_employees=available_for_sim
        )
        
        # For feasibility, we care about strict + flexible (pattern-following) employees
        # Truly flexible employees would be manually assigned, so exclude from estimate
        min_employees = sim_result['strictEmployees'] + sim_result['flexibleEmployees']
        
        # Add small buffer for max since flexible assignments may vary
        max_employees = ceil(min_employees * 1.1) if min_employees > 0 else 1
        
    except Exception as e:
        # Fallback to basic calculation if simulation fails
        cycle_length = len(pattern)
        work_days = sum(1 for d in pattern if d != 'O')
        coverage_per_employee = work_days / cycle_length if cycle_length > 0 else 0.7
        min_employees = ceil(headcount / coverage_per_employee) if coverage_per_employee > 0 else headcount * 2
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
        "work_pattern": pattern,
        "coverage_days": coverage_days,
        "employees_required_min": min_employees,
        "employees_required_max": max_employees,
        "employees_matching": matching_count,
        "sufficient": matching_count >= min_employees,
        "issues": issues,
        "estimation_method": "ICPMP v2.0"
    }


def _normalize_scheme(scheme_value: str, scheme_map: Dict[str, str] = None) -> str:
    """Normalize scheme value to short code format (A, B, P, or Global).
    
    Args:
        scheme_value: The scheme value from input (can be "Scheme P" or "P")
        scheme_map: Optional schemeMap from input
    
    Returns:
        Normalized short code: "A", "B", "P", or "Global"
    """
    if not scheme_value or scheme_value == "Global":
        return "Global"
    
    if scheme_map:
        # Check if value is already a short code
        if scheme_value in scheme_map:
            return scheme_value
        # Try reverse lookup
        for short_code, full_name in scheme_map.items():
            if full_name == scheme_value:
                return short_code
    
    # Fallback: extract letter from "Scheme X"
    if scheme_value.startswith("Scheme "):
        return scheme_value.replace("Scheme ", "").strip()
    
    return scheme_value


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
        # Note: scheme_req is already normalized to short code (A/B/P) by caller
        if scheme_req != 'Global':
            emp_scheme = emp.get('scheme', '')  # Employee scheme is already in short format
            if emp_scheme != scheme_req:
                continue
        
        matching.append(emp)
    
    return matching
