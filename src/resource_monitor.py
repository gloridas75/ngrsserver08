"""
Resource Monitor and Safety Wrapper for Solver

Prevents server crashes by monitoring memory/CPU and rejecting oversized requests.
"""

import psutil
import logging
import os
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class SolverResourceLimits:
    """Resource limits for solver to prevent server crashes."""
    
    # Memory limits
    MAX_MEMORY_PERCENT = float(os.getenv("MAX_SOLVER_MEMORY_PERCENT", "70"))  # 70% of available RAM
    MAX_MEMORY_GB = float(os.getenv("MAX_SOLVER_MEMORY_GB", "2.5"))  # 2.5GB max (safe for 4GB server)
    
    # Problem size limits (variables = slots × employees × patterns)
    MAX_VARIABLES_SMALL = 50_000      # 2 vCPU, 4GB: ~50K variables max
    MAX_VARIABLES_MEDIUM = 200_000    # 4 vCPU, 8GB: ~200K variables max
    MAX_VARIABLES_LARGE = 1_000_000   # 8 vCPU, 16GB: ~1M variables max
    
    # Time limits (prevent infinite hanging)
    MAX_TIME_LIMIT_SECONDS = int(os.getenv("MAX_SOLVER_TIME_LIMIT", "120"))  # 2 minutes max
    
    # CPU limits
    MAX_CPU_WORKERS = int(os.getenv("MAX_CPSAT_WORKERS", "2"))  # Limit parallel workers


def estimate_problem_complexity(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Estimate problem complexity before solving.
    
    Returns:
        Dict with complexity metrics
    """
    num_slots = len(ctx.get('slots', []))
    num_employees = len(ctx.get('employees', []))
    num_requirements = len(ctx.get('requirements', []))
    
    # Estimate pattern length (default 7 if not specified)
    avg_pattern_length = 7
    if ctx.get('requirements'):
        pattern_lengths = [
            len(req.get('workPattern', []))
            for req in ctx['requirements']
            if req.get('workPattern')
        ]
        if pattern_lengths:
            avg_pattern_length = sum(pattern_lengths) / len(pattern_lengths)
    
    # Estimate decision variables
    # x[slot, employee, pattern_day] ∈ {0, 1}
    estimated_variables = num_slots * num_employees * int(avg_pattern_length)
    
    # Estimate constraints
    # - Headcount: ~num_slots
    # - One per day: ~num_employees * planning_days
    # - Consecutive days: ~num_employees
    # - Weekly hours: ~num_employees * num_weeks
    planning_days = ctx.get('planningHorizon', {}).get('lengthDays', 31)
    num_weeks = (planning_days + 6) // 7
    estimated_constraints = (
        num_slots +  # Headcount
        (num_employees * planning_days) +  # One per day
        num_employees +  # Consecutive days
        (num_employees * num_weeks)  # Weekly hours
    )
    
    # Memory estimate (rough approximation)
    # CP-SAT uses ~100 bytes per variable on average
    estimated_memory_mb = (estimated_variables * 100) / (1024 * 1024)
    
    return {
        "num_slots": num_slots,
        "num_employees": num_employees,
        "num_requirements": num_requirements,
        "avg_pattern_length": avg_pattern_length,
        "planning_days": planning_days,
        "estimated_variables": estimated_variables,
        "estimated_constraints": estimated_constraints,
        "estimated_memory_mb": round(estimated_memory_mb, 2),
        "complexity_score": estimated_variables / 10000  # Normalized score
    }


def check_resource_availability() -> Tuple[bool, Optional[str]]:
    """
    Check if system has enough resources to run solver.
    
    Returns:
        Tuple of (can_run: bool, reason: Optional[str])
    """
    try:
        # Check memory
        memory = psutil.virtual_memory()
        available_gb = memory.available / (1024 ** 3)
        used_percent = memory.percent
        
        if used_percent > SolverResourceLimits.MAX_MEMORY_PERCENT:
            return False, f"System memory usage too high: {used_percent:.1f}% (limit: {SolverResourceLimits.MAX_MEMORY_PERCENT}%)"
        
        if available_gb < 0.5:  # Less than 500MB available
            return False, f"Insufficient available memory: {available_gb:.2f}GB (need at least 0.5GB)"
        
        # Check CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent > 90:
            return False, f"System CPU usage too high: {cpu_percent:.1f}%"
        
        return True, None
        
    except Exception as e:
        logger.warning(f"Resource check failed: {e}")
        return True, None  # Allow solving if check fails


def validate_problem_size(ctx: Dict[str, Any]) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Validate that problem size is within safe limits.
    
    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str], complexity_metrics: dict)
    """
    complexity = estimate_problem_complexity(ctx)
    
    logger.info(f"Problem complexity: {complexity['estimated_variables']} variables, "
                f"{complexity['estimated_memory_mb']}MB estimated")
    
    # Get server capacity (from env or auto-detect)
    total_memory_gb = psutil.virtual_memory().total / (1024 ** 3)
    cpu_count = psutil.cpu_count(logical=True)
    
    # Determine limits based on server capacity
    if total_memory_gb <= 4.5:  # 4GB server
        max_variables = SolverResourceLimits.MAX_VARIABLES_SMALL
        max_memory_gb = 2.5
    elif total_memory_gb <= 8.5:  # 8GB server
        max_variables = SolverResourceLimits.MAX_VARIABLES_MEDIUM
        max_memory_gb = 6.0
    else:  # 16GB+ server
        max_variables = SolverResourceLimits.MAX_VARIABLES_LARGE
        max_memory_gb = 12.0
    
    # Check variable limit
    if complexity['estimated_variables'] > max_variables:
        return False, (
            f"Problem too large for this server: {complexity['estimated_variables']:,} variables "
            f"(limit: {max_variables:,}). "
            f"Server capacity: {total_memory_gb:.1f}GB RAM, {cpu_count} vCPUs. "
            f"Consider: (1) Reducing headcount per requirement, "
            f"(2) Using incremental solver for partial re-runs, "
            f"(3) Upgrading to larger server (8GB+ RAM recommended)."
        ), complexity
    
    # Check memory estimate
    if complexity['estimated_memory_mb'] / 1024 > max_memory_gb:
        return False, (
            f"Problem requires too much memory: {complexity['estimated_memory_mb']:.0f}MB "
            f"(limit: {max_memory_gb:.1f}GB for {total_memory_gb:.1f}GB server). "
            f"Consider reducing problem size or upgrading server."
        ), complexity
    
    # Warning threshold (70% of max)
    warning_threshold = max_variables * 0.7
    if complexity['estimated_variables'] > warning_threshold:
        logger.warning(
            f"⚠️ Problem size is large: {complexity['estimated_variables']:,} variables "
            f"({complexity['estimated_variables']/max_variables*100:.0f}% of capacity). "
            f"Solving may take 30-120 seconds and use significant resources."
        )
    
    return True, None, complexity


def apply_resource_limits_to_solver(ctx: Dict[str, Any], solver_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply safe resource limits to solver configuration.
    
    Args:
        ctx: Solver context
        solver_config: User-provided solver config
        
    Returns:
        Safe solver config with resource limits applied
    """
    safe_config = solver_config.copy()
    
    # Limit time
    user_time_limit = safe_config.get('timeLimitSeconds', 60)
    safe_config['timeLimitSeconds'] = min(
        user_time_limit,
        SolverResourceLimits.MAX_TIME_LIMIT_SECONDS
    )
    
    # Limit parallel workers
    cpu_count = psutil.cpu_count(logical=True) or 2
    max_workers = min(
        SolverResourceLimits.MAX_CPU_WORKERS,
        max(1, cpu_count - 1)  # Leave 1 CPU for system
    )
    
    user_workers = safe_config.get('numSearchWorkers')
    if user_workers:
        safe_config['numSearchWorkers'] = min(user_workers, max_workers)
    else:
        safe_config['numSearchWorkers'] = max_workers
    
    # Log if limits were applied
    if user_time_limit > safe_config['timeLimitSeconds']:
        logger.warning(
            f"⚠️ Time limit reduced: {user_time_limit}s → {safe_config['timeLimitSeconds']}s "
            f"(server limit)"
        )
    
    if user_workers and user_workers > safe_config['numSearchWorkers']:
        logger.warning(
            f"⚠️ Parallel workers reduced: {user_workers} → {safe_config['numSearchWorkers']} "
            f"(server has {cpu_count} vCPUs)"
        )
    
    return safe_config


def pre_solve_safety_check(ctx: Dict[str, Any]) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Comprehensive pre-solve safety check.
    
    Returns:
        Tuple of (can_solve: bool, error_message: Optional[str], complexity_metrics: dict)
    """
    # Check system resources
    can_run, resource_error = check_resource_availability()
    if not can_run:
        return False, resource_error, {}
    
    # Validate problem size
    is_valid, size_error, complexity = validate_problem_size(ctx)
    if not is_valid:
        return False, size_error, complexity
    
    return True, None, complexity
