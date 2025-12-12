"""
ICPMP v3.0 Integration Module

This module integrates ICPMP v3.0 (Incremental Configuration Pattern Matching Preprocessor)
into the main solver workflow. It preprocesses requirements to:
1. Calculate optimal employee count using try-minimal-first algorithm
2. Generate optimal rotation offsets
3. Select employees using balanced strategy (working hours, availability, scheme diversity)
4. Filter and prepare employee pool for CP-SAT solver

Key Features:
- Proven minimal employee count (guaranteed optimal)
- Fair workload distribution (prefers employees with fewer working hours)
- Scheme-proportional selection (when requirement.scheme = "Global")
- Seniority-based tie-breaking
- Availability tracking (prevents over-allocation across multiple requirements)

Author: NGRS Solver Team
Date: December 2025
"""

from typing import Dict, List, Any, Set, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from math import ceil
import logging

from context.engine.config_optimizer_v3 import calculate_optimal_with_u_slots

logger = logging.getLogger(__name__)


class ICPMPPreprocessor:
    """
    ICPMP v3.0 Preprocessor for optimal employee selection and rotation offset assignment.
    
    This class handles the preprocessing phase before CP-SAT solver execution:
    - Runs ICPMP v3.0 for each requirement to get optimal employee count
    - Filters eligible employees based on requirement criteria
    - Selects optimal subset using balanced strategy
    - Applies rotation offsets to selected employees
    - Returns filtered employee list ready for CP-SAT
    
    Usage:
        preprocessor = ICPMPPreprocessor(input_json)
        result = preprocessor.preprocess_all_requirements()
        input_json['employees'] = result['filtered_employees']
        # Now pass to CP-SAT solver
    """
    
    def __init__(self, input_json: Dict[str, Any]):
        """
        Initialize preprocessor with solver input JSON.
        
        Args:
            input_json: Full solver input containing demandItems, employees, etc.
        """
        self.input = input_json
        self.assigned_employee_ids: Set[str] = set()
        self.icpmp_metadata: Dict[str, Any] = {}
        self.warnings: List[str] = []
        
        # Extract common data
        self.all_employees = input_json.get('employees', [])
        self.public_holidays = input_json.get('publicHolidays', [])
        self.planning_horizon = input_json.get('planningHorizon', {})
        
        logger.info(f"ICPMPPreprocessor initialized with {len(self.all_employees)} employees")
    
    def preprocess_all_requirements(self) -> Dict[str, Any]:
        """
        Main entry point: Process all requirements across all demand items.
        
        Returns:
            {
                'filtered_employees': List[Dict],  # Selected employees with offsets applied
                'icpmp_metadata': Dict,            # Per-requirement ICPMP results
                'warnings': List[str],              # Any issues encountered
                'summary': Dict                     # Summary statistics
            }
        """
        logger.info("=" * 80)
        logger.info("ICPMP v3.0 PREPROCESSING PHASE STARTED")
        logger.info("=" * 80)
        
        filtered_employees = []
        requirement_count = 0
        total_selected = 0
        
        for demand_item in self.input.get('demandItems', []):
            demand_id = demand_item.get('demandId', 'UNKNOWN')
            logger.info(f"\nProcessing Demand Item: {demand_id}")
            
            for req in demand_item.get('requirements', []):
                requirement_count += 1
                req_id = req.get('requirementId', 'UNKNOWN')
                logger.info(f"  Requirement: {req_id}")
                
                try:
                    # Step 1: Run ICPMP v3.0 to get optimal configuration
                    icpmp_result = self._run_icpmp_for_requirement(demand_item, req)
                    
                    # Step 2: Select and assign employees
                    selected_employees = self._select_and_assign_employees(
                        requirement=req,
                        demand_item=demand_item,
                        icpmp_result=icpmp_result
                    )
                    
                    # Step 3: Track results
                    filtered_employees.extend(selected_employees)
                    total_selected += len(selected_employees)
                    self.icpmp_metadata[req_id] = {
                        'demandId': demand_id,
                        'optimal_employees': icpmp_result['configuration']['employeesRequired'],
                        'selected_count': len(selected_employees),
                        'u_slots_total': icpmp_result['coverage']['totalUSlots'],
                        'offset_distribution': icpmp_result['configuration']['offsetDistribution'],
                        'is_optimal': icpmp_result['configuration']['optimality'] == 'PROVEN_MINIMAL',
                        'coverage_rate': icpmp_result['coverage']['achievedRate']
                    }
                    
                    logger.info(f"    ✓ Selected {len(selected_employees)} employees "
                              f"(optimal: {icpmp_result['configuration']['employeesRequired']}, "
                              f"U-slots: {icpmp_result['coverage']['totalUSlots']})")
                    
                except Exception as e:
                    error_msg = f"Failed to process requirement {req_id}: {str(e)}"
                    logger.error(f"    ✗ {error_msg}")
                    logger.error(f"    Traceback:", exc_info=True)
                    self.warnings.append(error_msg)
        
        summary = {
            'total_requirements_processed': requirement_count,
            'total_employees_selected': total_selected,
            'total_employees_available': len(self.all_employees),
            'utilization_rate': total_selected / len(self.all_employees) if self.all_employees else 0
        }
        
        logger.info("\n" + "=" * 80)
        logger.info("ICPMP v3.0 PREPROCESSING PHASE COMPLETED")
        logger.info(f"  Requirements Processed: {requirement_count}")
        logger.info(f"  Employees Selected: {total_selected} / {len(self.all_employees)}")
        logger.info(f"  Utilization Rate: {summary['utilization_rate']:.1%}")
        logger.info(f"  Warnings: {len(self.warnings)}")
        logger.info("=" * 80 + "\n")
        
        return {
            'filtered_employees': filtered_employees,
            'icpmp_metadata': self.icpmp_metadata,
            'warnings': self.warnings,
            'summary': summary
        }
    
    def _run_icpmp_for_requirement(self, demand_item: Dict, req: Dict) -> Dict:
        """
        Run ICPMP v3.0 for a single requirement to get optimal configuration.
        
        Args:
            demand_item: Demand item containing shift details
            req: Requirement with workPattern, headcount, etc.
        
        Returns:
            ICPMP result dict with num_employees, offset_distribution, patterns, etc.
        """
        req_id = req.get('requirementId', 'UNKNOWN')
        work_pattern = req.get('workPattern', [])
        
        # Normalize headcount to support both formats:
        # Legacy: "headcount": 10 (single value)
        # New: "headcount": {"D": 10, "N": 10} (per-shift)
        headcount_raw = req.get('headcount', 1)
        
        if isinstance(headcount_raw, dict):
            # New format: per-shift headcount
            # Calculate total slots needed per day
            total_headcount_per_day = sum(headcount_raw.values())
            headcount_by_shift = headcount_raw
            logger.info(f"    Headcount (new format): {headcount_by_shift}, Total per day: {total_headcount_per_day}")
        else:
            # Legacy format: single headcount value
            # Count unique shift types in pattern (excluding 'O')
            shift_types = set(s for s in work_pattern if s != 'O')
            
            if len(shift_types) > 1:
                # Multiple shift types: multiply by shift count
                total_headcount_per_day = headcount_raw * len(shift_types)
                headcount_by_shift = {shift: headcount_raw for shift in shift_types}
                logger.info(f"    Headcount (legacy): {headcount_raw} × {len(shift_types)} shifts = {total_headcount_per_day} total per day")
            else:
                # Single shift type: use as-is
                total_headcount_per_day = headcount_raw
                headcount_by_shift = {list(shift_types)[0]: headcount_raw} if shift_types else {}
                logger.info(f"    Headcount (legacy single-shift): {headcount_raw}")
        
        # Use total headcount for ICPMP calculation
        headcount = total_headcount_per_day
        
        # Extract coverage parameters from shifts (first shift for simplicity)
        shifts = demand_item.get('shifts', [{}])
        first_shift = shifts[0] if shifts else {}
        
        coverage_days = first_shift.get('coverageDays', 
                                       ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])
        coverage_anchor = first_shift.get('coverageAnchor', 
                                         demand_item.get('shiftStartDate', 
                                                       self.planning_horizon.get('startDate', '2026-01-01')))
        
        logger.info(f"    Extracting parameters for {req_id}:")
        logger.info(f"      Coverage days: {coverage_days}")
        logger.info(f"      Coverage anchor: {coverage_anchor}")
        logger.info(f"      Public holidays: {self.public_holidays}")
        logger.info(f"      Include holidays: {first_shift.get('includePublicHolidays', True)}")
        
        # Generate coverage calendar
        try:
            calendar = self._generate_coverage_calendar(
                coverage_days=coverage_days,
                start_date=self.planning_horizon.get('startDate'),
                end_date=self.planning_horizon.get('endDate'),
                public_holidays=self.public_holidays,
                include_public_holidays=first_shift.get('includePublicHolidays', True)
            )
        except Exception as cal_error:
            logger.error(f"    Calendar generation failed: {cal_error}")
            raise
        
        logger.info(f"    Running ICPMP v3.0: pattern={len(work_pattern)}-day, HC={headcount}, "
                   f"coverage={len(calendar)} days")
        
        # Call ICPMP v3.0
        icpmp_result = calculate_optimal_with_u_slots(
            pattern=work_pattern,
            headcount=headcount,
            calendar=calendar,
            anchor_date=coverage_anchor
        )
        
        # POST-ICPMP VALIDATION: Check if all required offsets are covered
        # This handles edge cases where ICPMP's greedy U-slot simulation
        # returns feasible=True, but CP-SAT fails due to missing offsets
        pattern_length = len(work_pattern)
        selected_offsets = set(icpmp_result['configuration']['offsetDistribution'].keys())
        required_offsets = set(range(pattern_length))
        missing_offsets = required_offsets - selected_offsets
        
        if missing_offsets:
            logger.warning(f"    ⚠️  ICPMP selected {len(selected_offsets)} offsets but pattern requires {pattern_length}")
            logger.warning(f"    Missing offsets: {sorted(missing_offsets)}")
            logger.warning(f"    This can cause CP-SAT infeasibility due to incomplete pattern coverage")
            logger.warning(f"    Recalculating with pattern_length ({pattern_length}) employees to ensure full offset coverage...")
            
            # Force recalculation with pattern_length employees
            from context.engine.config_optimizer_v3 import try_placement_with_n_employees
            
            recalc_result = try_placement_with_n_employees(
                num_employees=pattern_length,
                pattern=work_pattern,
                headcount=headcount,
                calendar=calendar,
                anchor_date=coverage_anchor,
                cycle_length=pattern_length
            )
            
            if recalc_result['is_feasible']:
                # Rebuild icpmp_result format with recalculated values
                icpmp_result = {
                    'requirementId': req_id,
                    'configuration': {
                        'employeesRequired': pattern_length,
                        'optimality': 'FORCED_FULL_OFFSET_COVERAGE',
                        'algorithm': 'GREEDY_INCREMENTAL_WITH_VALIDATION',
                        'lowerBound': icpmp_result['configuration']['lowerBound'],
                        'attemptsRequired': pattern_length - icpmp_result['configuration']['lowerBound'] + 1,
                        'offsetDistribution': recalc_result['offset_distribution']
                    },
                    'employeePatterns': recalc_result['employees'],
                    'coverage': {
                        'achievedRate': recalc_result['coverage_rate'],
                        'totalWorkDays': recalc_result['total_work_days'],
                        'totalUSlots': recalc_result['total_u_slots'],
                        'dailyCoverageDetails': recalc_result['daily_coverage']
                    },
                    'metadata': {
                        'patternCycleLength': pattern_length,
                        'workDaysPerCycle': sum(1 for s in work_pattern if s != 'O'),
                        'planningHorizonDays': len(calendar),
                        'totalCoverageNeeded': len(calendar) * headcount,
                        'validationApplied': True,
                        'originalEmployeesRequired': icpmp_result['configuration']['employeesRequired']
                    }
                }
                logger.info(f"    ✓ Validation fix applied: Using {pattern_length} employees with all offsets [0-{pattern_length-1}]")
            else:
                logger.error(f"    ✗ Recalculation with {pattern_length} employees still not feasible!")
                logger.error(f"    This indicates a deeper issue with the pattern or calendar configuration")
        else:
            logger.info(f"    ✓ Offset validation passed: All {pattern_length} offsets covered")
        
        return icpmp_result
    
    def _select_and_assign_employees(self, requirement: Dict, demand_item: Dict, 
                                    icpmp_result: Dict) -> List[Dict]:
        """
        Select optimal employees and apply rotation offsets.
        
        Args:
            requirement: Requirement dict with criteria
            demand_item: Demand item with whitelist/blacklist
            icpmp_result: ICPMP v3.0 result with optimal count and offsets
        
        Returns:
            List of selected employee dicts with rotationOffset updated
        """
        req_id = requirement.get('requirementId', 'UNKNOWN')
        optimal_count = icpmp_result['configuration']['employeesRequired']
        offset_distribution_dict = icpmp_result['configuration']['offsetDistribution']
        
        # Convert offset distribution dict {offset: count} to list of offsets
        # Example: {0: 2, 1: 3} → [0, 0, 1, 1, 1]
        offset_list = []
        for offset, count in sorted(offset_distribution_dict.items()):
            offset_list.extend([offset] * count)
        
        logger.info(f"    Offset distribution: {offset_distribution_dict}")
        logger.info(f"    Offset list: {offset_list}")
        
        # Step 1: Filter eligible employees
        eligible = self._filter_eligible_employees(requirement, demand_item)
        
        logger.info(f"    Eligible employees: {len(eligible)} (before availability check)")
        
        # Step 2: Filter by availability (not already assigned)
        available = [emp for emp in eligible 
                    if emp['employeeId'] not in self.assigned_employee_ids]
        
        logger.info(f"    Available employees: {len(available)} (after availability check)")
        
        # Step 3: Check sufficiency
        if len(available) < optimal_count:
            raise ValueError(
                f"Insufficient employees for requirement {req_id}: "
                f"Need {optimal_count}, but only {len(available)} available. "
                f"Total eligible: {len(eligible)}, Already assigned: {len(eligible) - len(available)}"
            )
        
        # Step 4: Select using balanced strategy
        selected = self._select_employees_balanced(
            available=available,
            optimal_count=optimal_count,
            requirement=requirement
        )
        
        # Step 5: Apply rotation offsets
        for i, emp in enumerate(selected):
            offset = offset_list[i] if i < len(offset_list) else 0
            emp['rotationOffset'] = offset
            emp['_icpmp_requirement_id'] = req_id  # Track which requirement assigned this
            self.assigned_employee_ids.add(emp['employeeId'])
        
        logger.info(f"    Offsets applied to {len(selected)} employees")
        
        return selected
    
    def _filter_eligible_employees(self, requirement: Dict, demand_item: Dict) -> List[Dict]:
        """
        Filter employees matching requirement criteria.
        
        Filters by:
        - productTypeId, rankId, ouId
        - requiredQualifications
        - gender
        - scheme (if not "Global")
        - shift duration compatibility (MOM hour limits)
        - whitelist/blacklist
        
        Args:
            requirement: Requirement criteria
            demand_item: Demand item with whitelist/blacklist
        
        Returns:
            List of eligible employee dicts (deep copies to avoid mutation)
        """
        import copy
        
        eligible = []
        filtered_count = 0
        
        # Extract criteria
        product_type = requirement.get('productTypeId')
        rank = requirement.get('rankId')
        ou_id = demand_item.get('ouId')
        required_quals = set(requirement.get('requiredQualifications', []))
        gender_req = requirement.get('gender', 'Any')
        scheme_req = requirement.get('scheme', 'Global')
        
        # Calculate maximum shift duration for scheme compatibility check
        max_shift_hours = self._calculate_max_shift_duration(demand_item)
        
        # MOM scheme hour limits (from constraint C6)
        SCHEME_HOUR_LIMITS = {
            'A': 14,  # Full-time Scheme A
            'B': 13,  # Full-time Scheme B
            'P': 9    # Part-time Scheme P (MOM regulated)
        }
        
        logger.debug(f"    Max shift duration: {max_shift_hours:.1f}h")
        
        # Extract whitelist/blacklist from first shift
        shifts = demand_item.get('shifts', [{}])
        first_shift = shifts[0] if shifts else {}
        whitelist_emp_ids = set(first_shift.get('whitelist', {}).get('employeeIds', []))
        blacklist_emp_ids = set(first_shift.get('blacklist', {}).get('employeeIds', []))
        whitelist_team_ids = set(first_shift.get('whitelist', {}).get('teamIds', []))
        
        for emp in self.all_employees:
            # Check blacklist first
            if emp['employeeId'] in blacklist_emp_ids:
                continue
            
            # Check whitelist (if specified)
            if whitelist_emp_ids and emp['employeeId'] not in whitelist_emp_ids:
                if not whitelist_team_ids or emp.get('teamId') not in whitelist_team_ids:
                    continue
            
            # Check basic criteria
            if product_type and emp.get('productTypeId') != product_type:
                continue
            if rank and emp.get('rankId') != rank:
                continue
            if ou_id and emp.get('ouId') != ou_id:
                continue
            
            # Check gender
            if gender_req != 'Any' and emp.get('gender') != gender_req:
                continue
            
            # Check shift duration compatibility (MOM hour limits)
            # Filter out employees whose scheme limit is less than shift duration
            emp_scheme = emp.get('scheme', 'Unknown')
            scheme_limit = SCHEME_HOUR_LIMITS.get(emp_scheme, 14)  # Default to Scheme A limit
            
            if max_shift_hours > scheme_limit:
                logger.debug(f"      Employee {emp['employeeId']} (Scheme {emp_scheme}, {scheme_limit}h limit) "
                           f"filtered: shift {max_shift_hours:.1f}h exceeds limit")
                filtered_count += 1
                continue
            
            # Check scheme (if not Global)
            if scheme_req != 'Global' and emp.get('scheme') != scheme_req:
                continue
            
            # Check qualifications
            emp_quals = set(emp.get('qualifications', []))
            if not required_quals.issubset(emp_quals):
                continue
            
            # Eligible - add deep copy to avoid mutating original
            eligible.append(copy.deepcopy(emp))
        
        # Log filtering summary
        if filtered_count > 0:
            logger.info(f"    Shift duration filter: Excluded {filtered_count} employees "
                       f"(shift {max_shift_hours:.1f}h exceeds their scheme limit)")
        
        return eligible
    
    def _select_employees_balanced(self, available: List[Dict], optimal_count: int, 
                                   requirement: Dict) -> List[Dict]:
        """
        Select employees using balanced strategy.
        
        Priority order:
        1. Working hours (prefer fewer hours for fairness)
        2. Scheme diversity (if requirement.scheme = "Global")
        3. Seniority (lower employeeId = more senior)
        
        Args:
            available: List of available employee dicts
            optimal_count: Number to select
            requirement: Requirement dict
        
        Returns:
            List of selected employee dicts
        """
        # Step 1: Sort by working hours (ascending), then by employeeId
        available_sorted = sorted(
            available,
            key=lambda e: (
                e.get('totalWorkingHours', 0),
                e.get('employeeId', 'ZZZZZZ')
            )
        )
        
        # Step 2: Handle scheme-based selection
        scheme_req = requirement.get('scheme', 'Global')
        
        if scheme_req == 'Global':
            # Distribute proportionally across schemes
            selected = self._select_across_schemes(available_sorted, optimal_count)
        else:
            # Simple selection (already filtered by scheme)
            selected = available_sorted[:optimal_count]
        
        return selected
    
    def _select_across_schemes(self, available: List[Dict], optimal_count: int) -> List[Dict]:
        """
        Distribute selection proportionally across Scheme A, B, P.
        Maintains working hours preference within each scheme.
        
        Args:
            available: Available employees (already sorted by working hours)
            optimal_count: Number to select
        
        Returns:
            Selected employees with balanced scheme distribution
        """
        # Group by scheme
        scheme_groups = defaultdict(list)
        for emp in available:
            scheme = emp.get('scheme', 'Unknown')
            scheme_groups[scheme].append(emp)
        
        if not scheme_groups:
            return []
        
        # Calculate proportional allocation
        total_available = len(available)
        scheme_allocation = {}
        
        for scheme, emps in scheme_groups.items():
            proportion = len(emps) / total_available
            # Use ceil for fairness, adjust later
            scheme_allocation[scheme] = max(1, round(proportion * optimal_count))
        
        # Adjust total to match optimal_count exactly
        current_total = sum(scheme_allocation.values())
        
        if current_total > optimal_count:
            # Remove from largest group(s)
            excess = current_total - optimal_count
            schemes_sorted = sorted(scheme_allocation.keys(), 
                                  key=lambda s: scheme_allocation[s], 
                                  reverse=True)
            for scheme in schemes_sorted:
                if excess <= 0:
                    break
                reduction = min(excess, scheme_allocation[scheme] - 1)
                if reduction > 0:
                    scheme_allocation[scheme] -= reduction
                    excess -= reduction
        
        elif current_total < optimal_count:
            # Add to largest group
            deficit = optimal_count - current_total
            largest_scheme = max(scheme_allocation.keys(), 
                               key=lambda s: len(scheme_groups[s]))
            scheme_allocation[largest_scheme] += deficit
        
        # Select from each scheme group
        selected = []
        for scheme, count in scheme_allocation.items():
            scheme_emps = scheme_groups[scheme]
            # Already sorted by working hours globally, maintain that order
            selected.extend(scheme_emps[:count])
        
        # Re-sort final selection by working hours to maintain fairness
        selected_sorted = sorted(
            selected,
            key=lambda e: (
                e.get('totalWorkingHours', 0),
                e.get('employeeId', 'ZZZZZZ')
            )
        )
        
        return selected_sorted[:optimal_count]
    
    def _calculate_max_shift_duration(self, demand_item: Dict) -> float:
        """
        Calculate maximum shift duration from demand item shifts.
        
        This is used to filter employees based on MOM scheme hour limits:
        - Scheme A: max 14h/day
        - Scheme B: max 13h/day
        - Scheme P: max 9h/day (part-time)
        
        Args:
            demand_item: Demand item containing shifts
        
        Returns:
            Maximum shift duration in hours (considering nextDay flag)
        """
        max_hours = 0.0
        
        shifts = demand_item.get('shifts', [])
        for shift in shifts:
            shift_details = shift.get('shiftDetails', [])
            for detail in shift_details:
                start = detail.get('start', '00:00:00')
                end = detail.get('end', '00:00:00')
                next_day = detail.get('nextDay', False)
                
                try:
                    # Parse times (handle both HH:MM:SS and HH:MM formats)
                    start_parts = start.split(':')
                    end_parts = end.split(':')
                    
                    start_h = int(start_parts[0])
                    start_m = int(start_parts[1]) if len(start_parts) > 1 else 0
                    end_h = int(end_parts[0])
                    end_m = int(end_parts[1]) if len(end_parts) > 1 else 0
                    
                    # Calculate duration
                    hours = end_h - start_h + (end_m - start_m) / 60.0
                    if next_day:
                        hours += 24
                    
                    max_hours = max(max_hours, hours)
                    
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse shift times: {start} to {end}. Error: {e}")
                    continue
        
        return max_hours
    
    def _generate_coverage_calendar(self, coverage_days: List[str], start_date: str, 
                                   end_date: str, public_holidays: List[str],
                                   include_public_holidays: bool = True) -> List[str]:
        """
        Generate list of coverage dates based on coverage days and holidays.
        
        Args:
            coverage_days: List of day names (Mon, Tue, etc.)
            start_date: Planning start date (ISO format)
            end_date: Planning end date (ISO format)
            public_holidays: List of public holiday dates (ISO format)
            include_public_holidays: Whether to include public holidays
        
        Returns:
            List of ISO date strings for coverage days
        """
        # Map day names to weekday numbers
        day_map = {
            'Mon': 0, 'Monday': 0,
            'Tue': 1, 'Tuesday': 1,
            'Wed': 2, 'Wednesday': 2,
            'Thu': 3, 'Thursday': 3,
            'Fri': 4, 'Friday': 4,
            'Sat': 5, 'Saturday': 5,
            'Sun': 6, 'Sunday': 6
        }
        
        coverage_weekdays = [day_map.get(day) for day in coverage_days if day in day_map]
        public_holiday_set = set(public_holidays)
        
        # Generate calendar
        calendar = []
        current = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        
        while current <= end:
            date_str = current.date().isoformat()
            
            # Check if this day is in coverage days
            if current.weekday() in coverage_weekdays:
                # Check public holiday exclusion
                if date_str in public_holiday_set and not include_public_holidays:
                    pass  # Skip this day
                else:
                    calendar.append(date_str)
            
            current += timedelta(days=1)
        
        return calendar
