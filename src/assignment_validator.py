"""
Assignment Validator - Phase 1: Employee-Specific Hard Constraints

Validates whether an employee can be assigned to candidate slots without
violating hard constraints. Does NOT use CP-SAT model - validates directly
for performance (<100ms target).

Supported Constraints (Phase 1 - Employee-Specific Only):
- C1: Daily Hours Cap (14h/13h/9h by scheme)
- C2: Weekly Hours Cap (44-52h normal hours)
- C3: Consecutive Working Days (max days without break)
- C4: Rest Period Between Shifts (minimum hours)
- C17: Monthly OT Cap (72h maximum overtime)

NOT Supported (require team/global context):
- C9: Team Assignment
- C14: Scheme Quotas
- S7: Team Cohesion
"""

import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from collections import defaultdict

from src.models import (
    ValidateAssignmentRequest,
    ValidateAssignmentResponse,
    SlotValidationResult,
    ViolationDetail,
    EmployeeInfo,
    ExistingAssignment,
    CandidateSlot
)


class AssignmentValidator:
    """
    Validates employee assignments against hard constraints.
    
    Usage:
        validator = AssignmentValidator()
        response = validator.validate(request)
    """
    
    # Mapping from human-readable constraint IDs to internal constraint codes
    CONSTRAINT_ID_MAP = {
        'momDailyHoursCap': 'C1',
        'momWeeklyHoursCap44h': 'C2',
        'maxConsecutiveWorkingDays': 'C3',
        'apgdMinRestBetweenShifts': 'C4',
        'momMonthlyOTcap72h': 'C17',
        'minimumOffDaysPerWeek': 'C_OFF_DAYS',
        'momLunchBreak': 'C_LUNCH',
        'oneShiftPerDay': 'C_ONE_SHIFT',
        'partTimerWeeklyHours': 'C_PART_TIMER',
        # Also support direct constraint IDs
        'C1': 'C1',
        'C2': 'C2',
        'C3': 'C3',
        'C4': 'C4',
        'C17': 'C17',
    }
    
    # Default constraint configuration with default values
    DEFAULT_CONSTRAINTS = {
        'C1': {
            'enabled': True, 
            'name': 'Daily Hours Cap',
            'defaultValue': 12,
            'schemeOverrides': {'A': 14, 'B': 13, 'P': 9},
            'params': {}
        },
        'C2': {
            'enabled': True,
            'name': 'Weekly Hours Cap',
            'defaultValue': 44,
            'schemeOverrides': {},
            'params': {}
        },
        'C3': {
            'enabled': True,
            'name': 'Consecutive Working Days',
            'defaultValue': 12,
            'schemeOverrides': {},
            'params': {}
        },
        'C4': {
            'enabled': True,
            'name': 'Rest Period Between Shifts',
            'defaultValue': 8,
            'schemeOverrides': {'P': 1},
            'params': {}
        },
        'C17': {
            'enabled': True,
            'name': 'Monthly OT Cap',
            'defaultValue': 72,
            'schemeOverrides': {},
            'params': {}
        },
        'C_LUNCH': {
            'enabled': True,
            'name': 'Lunch Break',
            'defaultValue': 60,  # minutes
            'schemeOverrides': {},
            'params': {'deductIfShiftAtLeastMinutes': 480}
        },
        'C_OFF_DAYS': {
            'enabled': True,
            'name': 'Minimum Off Days Per Week',
            'defaultValue': 1,
            'schemeOverrides': {},
            'params': {}
        },
        'C_PART_TIMER': {
            'enabled': True,
            'name': 'Part-Timer Weekly Hours',
            'defaultValue': None,  # Uses params instead
            'schemeOverrides': {},
            'params': {
                'maxHours4Days': 34.98,
                'maxHoursMoreDays': 29.98
            },
            'applicableToSchemes': ['P']
        },
        'C_MONTHLY_TOTAL': {
            'enabled': True,
            'name': 'Monthly Total Hours',
            'defaultValue': None,  # Loaded from monthlyHourLimits
            'schemeOverrides': {},
            'params': {}
        },
    }
    
    # Default monthly hour limits by month length
    DEFAULT_MONTHLY_LIMITS = {
        28: {'normalHours': 176, 'maxOvertimeHours': 112, 'totalMaxHours': 288},
        29: {'normalHours': 182, 'maxOvertimeHours': 116, 'totalMaxHours': 298},
        30: {'normalHours': 189, 'maxOvertimeHours': 120, 'totalMaxHours': 309},
        31: {'normalHours': 195, 'maxOvertimeHours': 124, 'totalMaxHours': 319},
    }
    
    def __init__(self):
        """Initialize validator with default configuration."""
        self.constraints = {k: v.copy() for k, v in self.DEFAULT_CONSTRAINTS.items()}
        self.monthly_limits = {k: v.copy() for k, v in self.DEFAULT_MONTHLY_LIMITS.items()}
    
    def _extract_scheme_letter(self, scheme: str) -> str:
        """
        Extract scheme letter from full scheme name.
        
        Examples:
            "Scheme A" -> "A"
            "A" -> "A"
            "Scheme P" -> "P"
        
        Returns:
            Single letter scheme identifier (A, B, or P)
        """
        if scheme.startswith("Scheme "):
            return scheme.replace("Scheme ", "").strip()
        return scheme.strip()
    
    def _normalize_datetime(self, dt_str: str) -> datetime:
        """
        Normalize datetime string to offset-naive datetime.
        
        Handles both:
        - "2026-01-13T07:00:00+08:00" (with timezone)
        - "2026-01-13T07:00:00" (without timezone)
        """
        # Remove timezone info to make all datetimes offset-naive for comparison
        dt_str_clean = dt_str.replace('Z', '').replace('+08:00', '').replace('+00:00', '')
        return datetime.fromisoformat(dt_str_clean)
    
    def validate(self, request: ValidateAssignmentRequest) -> ValidateAssignmentResponse:
        """
        Validate employee assignment to candidate slots.
        
        Args:
            request: Validation request with employee, existing assignments, and candidate slots
        
        Returns:
            ValidateAssignmentResponse with per-slot validation results
        """
        start_time = time.time()
        
        # Update constraint configuration if provided
        if request.constraintList:
            self._update_constraints(request.constraintList)
        
        # Update monthly hour limits if provided
        if hasattr(request, 'monthlyHourLimits') and request.monthlyHourLimits:
            self._update_monthly_limits(request.monthlyHourLimits)
        
        # Validate each candidate slot
        results = []
        for slot in request.candidateSlots:
            result = self._validate_single_slot(
                employee=request.employee,
                existing_assignments=request.existingAssignments,
                candidate_slot=slot,
                planning_ref=request.planningReference or {}
            )
            results.append(result)
        
        processing_time_ms = (time.time() - start_time) * 1000
        
        return ValidateAssignmentResponse(
            status="success",
            validationResults=results,
            employeeId=request.employee.employeeId,
            timestamp=datetime.now().isoformat(),
            processingTimeMs=round(processing_time_ms, 2)
        )
    
    def _update_constraints(self, constraint_list: List):
        """
        Update constraint configuration from request.
        
        Supports two formats:
        1. Simple format: {"constraintId": "C1", "enabled": true}
        2. Extended format: {"id": "momDailyHoursCap", "defaultValue": 12, "schemeOverrides": {...}}
        """
        for constraint_config in constraint_list:
            # Convert to dict if Pydantic model
            if hasattr(constraint_config, 'model_dump'):
                config = constraint_config.model_dump()
            elif hasattr(constraint_config, 'dict'):
                config = constraint_config.dict()
            elif isinstance(constraint_config, dict):
                config = constraint_config
            else:
                continue
            
            # Get constraint ID - support both 'constraintId' and 'id' fields
            raw_id = config.get('constraintId') or config.get('id')
            if not raw_id:
                continue
            
            # Map human-readable ID to internal constraint code
            constraint_id = self.CONSTRAINT_ID_MAP.get(raw_id, raw_id)
            
            # Skip if this constraint is not tracked
            if constraint_id not in self.constraints:
                continue
            
            # Determine if enabled (default True, or check 'enforcement' != 'disabled')
            enabled = config.get('enabled', True)
            enforcement = config.get('enforcement', 'hard')
            if enforcement == 'disabled':
                enabled = False
            
            self.constraints[constraint_id]['enabled'] = enabled
            
            # Update defaultValue if provided (and not None)
            if 'defaultValue' in config and config['defaultValue'] is not None:
                self.constraints[constraint_id]['defaultValue'] = config['defaultValue']
            
            # Update schemeOverrides if provided
            if 'schemeOverrides' in config and config['schemeOverrides']:
                scheme_overrides = config['schemeOverrides']
                # Handle nested format: {"A": {"productTypes": [...], "value": 8}}
                # or simple format: {"A": 14, "B": 13}
                for scheme_key, override_value in scheme_overrides.items():
                    if isinstance(override_value, dict) and 'value' in override_value:
                        # Nested format - extract the value
                        self.constraints[constraint_id]['schemeOverrides'][scheme_key] = override_value['value']
                    else:
                        # Simple format - use directly
                        self.constraints[constraint_id]['schemeOverrides'][scheme_key] = override_value
            
            # Update params if provided
            if 'params' in config and config['params']:
                self.constraints[constraint_id]['params'].update(config['params'])
    
    def _update_monthly_limits(self, monthly_hour_limits: List[Dict[str, Any]]):
        """
        Update monthly hour limits from request.
        
        Parses monthlyHourLimits entries like:
        - standardMonthlyHours
        - apgdTotalMaxHours
        - apgdMaximumOvertimeHours
        """
        for limit_config in monthly_hour_limits:
            limit_id = limit_config.get('id', '')
            values_by_month = limit_config.get('valuesByMonthLength', {})
            
            # Update monthly limits based on the configuration
            for month_days_str, values in values_by_month.items():
                try:
                    month_days = int(month_days_str)
                    if month_days not in self.monthly_limits:
                        self.monthly_limits[month_days] = {}
                    
                    # Update with the values from this config
                    if 'totalMaxHours' in values:
                        self.monthly_limits[month_days]['totalMaxHours'] = values['totalMaxHours']
                    if 'normalHours' in values:
                        self.monthly_limits[month_days]['normalHours'] = values['normalHours']
                    if 'maxOvertimeHours' in values:
                        self.monthly_limits[month_days]['maxOvertimeHours'] = values['maxOvertimeHours']
                except (ValueError, TypeError):
                    continue
    
    def _validate_single_slot(
        self,
        employee: EmployeeInfo,
        existing_assignments: List[ExistingAssignment],
        candidate_slot: CandidateSlot,
        planning_ref: Dict[str, Any]
    ) -> SlotValidationResult:
        """
        Validate a single candidate slot assignment.
        
        Creates a temporary assignment and checks all enabled constraints.
        """
        # Create temporary assignment from candidate slot
        temp_assignment = self._create_temp_assignment(employee, candidate_slot)
        
        # Combine existing + temporary assignments
        all_assignments = existing_assignments + [temp_assignment]
        
        # Check all enabled constraints
        violations = []
        
        if self.constraints['C1']['enabled']:
            violations.extend(self._check_c1_daily_hours(employee, temp_assignment))
        
        if self.constraints['C2']['enabled']:
            violations.extend(self._check_c2_weekly_hours(employee, all_assignments, temp_assignment))
        
        if self.constraints['C3']['enabled']:
            violations.extend(self._check_c3_consecutive_days(employee, all_assignments, temp_assignment))
        
        if self.constraints['C4']['enabled']:
            violations.extend(self._check_c4_rest_period(employee, all_assignments, temp_assignment))
        
        if self.constraints['C17']['enabled']:
            violations.extend(self._check_c17_monthly_ot(employee, all_assignments, temp_assignment))
        
        # New constraints
        if self.constraints.get('C_OFF_DAYS', {}).get('enabled', True):
            violations.extend(self._check_off_days_per_week(employee, all_assignments, temp_assignment))
        
        if self.constraints.get('C_PART_TIMER', {}).get('enabled', True):
            violations.extend(self._check_part_timer_weekly_hours(employee, all_assignments, temp_assignment))
        
        if self.constraints.get('C_MONTHLY_TOTAL', {}).get('enabled', True):
            violations.extend(self._check_monthly_total_hours(employee, all_assignments, temp_assignment))
        
        # Determine feasibility and recommendation
        hard_violations = [v for v in violations if v.violationType == 'hard']
        is_feasible = len(hard_violations) == 0
        
        recommendation = 'feasible' if is_feasible else 'not_feasible'
        
        return SlotValidationResult(
            slotId=candidate_slot.slotId,
            isFeasible=is_feasible,
            violations=violations,
            recommendation=recommendation,
            hours=temp_assignment.hours  # Include hour breakdown in result
        )
    
    def _create_temp_assignment(
        self, 
        employee: EmployeeInfo, 
        slot: CandidateSlot
    ) -> ExistingAssignment:
        """Create a temporary assignment object from candidate slot."""
        # Parse datetime (normalize to offset-naive)
        start_dt = self._normalize_datetime(slot.startDateTime)
        end_dt = self._normalize_datetime(slot.endDateTime)
        
        # Calculate hours
        hours = (end_dt - start_dt).total_seconds() / 3600.0
        
        # Extract date
        date_str = start_dt.strftime('%Y-%m-%d')
        
        # Get lunch break configuration
        lunch_config = self.constraints.get('C_LUNCH', {})
        lunch_minutes = lunch_config.get('defaultValue', 60)  # default 60 minutes
        min_shift_minutes = lunch_config.get('params', {}).get('deductIfShiftAtLeastMinutes', 480)  # default 8 hours
        
        # Calculate hour breakdown (gross - lunch, capped at 8h normal)
        gross_hours = hours
        gross_minutes = gross_hours * 60
        lunch_hours = (lunch_minutes / 60.0) if gross_minutes >= min_shift_minutes else 0.0
        net_hours = gross_hours - lunch_hours
        normal_hours = min(net_hours, 8.0)
        ot_hours = max(0.0, net_hours - 8.0)
        
        # Create HoursBreakdown
        from src.models import HoursBreakdown
        hours_breakdown = HoursBreakdown(
            gross=gross_hours,
            lunch=lunch_hours,
            normal=normal_hours,
            ot=ot_hours,
            restDayPay=0.0,
            paid=gross_hours
        )
        
        return ExistingAssignment(
            assignmentId=f"temp_{slot.slotId}",
            demandId=slot.demandItemId or "",
            requirementId=slot.requirementId or "",
            slotId=slot.slotId,
            startDateTime=slot.startDateTime,
            endDateTime=slot.endDateTime,
            shiftCode=slot.shiftCode,
            hours=hours_breakdown,
            date=date_str
        )
    
    # ===== Constraint Validation Functions =====
    
    def _check_c1_daily_hours(
        self, 
        employee: EmployeeInfo, 
        temp_assignment: ExistingAssignment
    ) -> List[ViolationDetail]:
        """
        C1: Daily Hours Cap - Check if shift exceeds scheme-specific daily limit.
        
        Uses values from constraint configuration:
        - defaultValue: base daily cap
        - schemeOverrides: scheme-specific caps (e.g., A: 14, B: 13, P: 9)
        """
        violations = []
        
        # Get constraint config
        c1_config = self.constraints.get('C1', {})
        default_cap = c1_config.get('defaultValue', 12)
        scheme_overrides = c1_config.get('schemeOverrides', {})
        
        # Extract scheme letter and get daily cap
        scheme_letter = self._extract_scheme_letter(employee.scheme)
        
        # Get scheme-specific cap or default
        daily_cap = float(scheme_overrides.get(scheme_letter, default_cap))
        
        # Get shift hours from breakdown (normal + OT)
        if hasattr(temp_assignment.hours, 'normal'):
            # New format: HoursBreakdown object
            shift_hours = temp_assignment.hours.normal + temp_assignment.hours.ot
        elif isinstance(temp_assignment.hours, dict):
            # Dict format
            shift_hours = temp_assignment.hours.get('normal', 0) + temp_assignment.hours.get('ot', 0)
        else:
            # Fallback: simple float
            shift_hours = temp_assignment.hours or 0.0
        
        if shift_hours > daily_cap:
            violations.append(ViolationDetail(
                constraintId='C1',
                constraintName='Daily Hours Cap',
                violationType='hard',
                description=f'Shift duration {shift_hours:.1f}h exceeds daily cap of {daily_cap:.1f}h for Scheme {scheme_letter}',
                context={
                    'shiftHours': shift_hours,
                    'dailyCap': daily_cap,
                    'scheme': scheme_letter,
                    'date': temp_assignment.date
                }
            ))
        
        return violations
    
    def _check_c2_weekly_hours(
        self,
        employee: EmployeeInfo,
        all_assignments: List[ExistingAssignment],
        temp_assignment: ExistingAssignment
    ) -> List[ViolationDetail]:
        """
        C2: Weekly Hours Cap - Pattern-aware normal hours calculation with rest day pay support.
        
        Limit: 44 hours normal hours per week (same for all schemes)
        Week definition: Sunday to Saturday
        
        Pattern-aware rules (matching main solver):
        - 4-day pattern: 11.0h normal/day
        - 5-day pattern: 8.8h normal/day
        - 6+ day pattern: 
          * Days 1-5: 8.8h normal/day
          * Day 6+: 0h normal (rest day pay = 8.0h, doesn't count toward 44h cap)
        
        Scheme P (part-time) has different thresholds:
        - ≤4 days: 8.745h/day, 5 days: 5.996h/day, 6 days: 4.996h/day, 7 days: 4.283h/day
        """
        violations = []
        
        # Parse temp assignment date
        temp_date = datetime.strptime(temp_assignment.date, '%Y-%m-%d').date()
        
        # Calculate week boundaries (Sunday to Saturday)
        days_since_sunday = (temp_date.weekday() + 1) % 7
        week_start = temp_date - timedelta(days=days_since_sunday)
        week_end = week_start + timedelta(days=6)
        
        # Build map of date -> assignment for the week
        assignments_by_date = {}
        for assignment in all_assignments:
            if not assignment.date:
                continue
            assign_date = datetime.strptime(assignment.date, '%Y-%m-%d').date()
            if week_start <= assign_date <= week_end:
                assignments_by_date[assign_date] = assignment
        
        # Calculate pattern-aware normal hours for each day in the week
        weekly_hours = 0.0
        work_pattern = employee.workPattern if employee.workPattern else []
        rotation_offset = getattr(employee, 'rotationOffset', 0) or 0
        scheme_letter = employee.scheme.split()[-1] if employee.scheme else 'A'  # Extract 'A', 'B', 'P'
        
        for day_offset in range(7):
            current_date = week_start + timedelta(days=day_offset)
            
            if current_date not in assignments_by_date:
                continue
            
            assignment = assignments_by_date[current_date]
            
            # Get pattern day for this date
            pattern_day = self._get_pattern_day_for_date(current_date, work_pattern, rotation_offset)
            
            # Calculate pattern-aware normal hours
            normal_hours = self._calculate_pattern_aware_normal_hours(
                assignment=assignment,
                work_pattern=work_pattern,
                pattern_day=pattern_day,
                scheme=scheme_letter,
                week_assignments=assignments_by_date,
                week_start=week_start
            )
            
            weekly_hours += normal_hours
        
        # Check against 44h cap
        weekly_cap = 44.0
        
        if weekly_hours > weekly_cap:
            violations.append(ViolationDetail(
                constraintId='C2',
                constraintName='Weekly Hours Cap',
                violationType='hard',
                description=f'Weekly normal hours {weekly_hours:.1f}h exceeds cap of {weekly_cap:.1f}h (week {week_start} to {week_end})',
                context={
                    'weeklyHours': round(weekly_hours, 1),
                    'weeklyCap': weekly_cap,
                    'weekStart': str(week_start),
                    'weekEnd': str(week_end),
                    'assignmentsInWeek': len(assignments_by_date)
                }
            ))
        
        return violations
    
    def _check_c3_consecutive_days(
        self,
        employee: EmployeeInfo,
        all_assignments: List[ExistingAssignment],
        temp_assignment: ExistingAssignment
    ) -> List[ViolationDetail]:
        """
        C3: Consecutive Working Days - Check if assignment causes too many consecutive work days.
        
        Uses values from constraint configuration:
        - defaultValue: base maximum consecutive days
        - schemeOverrides: scheme/product-specific overrides (e.g., A+APO = 8 days)
        """
        violations = []
        
        # Get constraint config
        c3_config = self.constraints.get('C3', {})
        default_max = c3_config.get('defaultValue', 12)
        scheme_overrides = c3_config.get('schemeOverrides', {})
        
        # Sort assignments by date
        dated_assignments = [a for a in all_assignments if a.date]
        dated_assignments.sort(key=lambda x: x.date)
        
        if not dated_assignments:
            return violations
        
        # Extract scheme letter for comparison
        scheme = self._extract_scheme_letter(employee.scheme)
        product_type = employee.productTypeId
        
        # Determine max consecutive days based on scheme + product type
        max_consecutive = default_max
        limit_source = f"default ({default_max})"
        
        # Check scheme overrides - supports nested format with productTypes
        if scheme in scheme_overrides:
            override = scheme_overrides[scheme]
            if isinstance(override, dict) and 'productTypes' in override:
                # Nested format: {"A": {"productTypes": ["APO"], "value": 8}}
                if product_type in override.get('productTypes', []):
                    value = override.get('value', default_max)
                    max_consecutive = value if value is not None else default_max
                    limit_source = f"Scheme {scheme} + {product_type}"
            else:
                # Simple format: {"A": 8}
                max_consecutive = int(override) if override is not None else default_max
                limit_source = f"Scheme {scheme}"
        elif employee.workPattern:
            # Fall back to work pattern analysis
            # Count longest consecutive work days in pattern
            pattern_max = 0
            current_count = 0
            for day in employee.workPattern:
                if day in ['D', 'N', 'E']:  # Work shifts
                    current_count += 1
                    pattern_max = max(pattern_max, current_count)
                else:  # Off day
                    current_count = 0
            
            if pattern_max > 0 and max_consecutive is not None and pattern_max < max_consecutive:
                max_consecutive = pattern_max
                limit_source = f"work pattern"
        
        # Safety check - ensure max_consecutive is never None
        if max_consecutive is None:
            max_consecutive = default_max
            limit_source = f"fallback default ({default_max})"
        
        # Build set of all work dates
        work_dates = set()
        for assignment in dated_assignments:
            work_date = datetime.strptime(assignment.date, '%Y-%m-%d').date()
            work_dates.add(work_date)
        
        # Find longest consecutive streak
        sorted_dates = sorted(work_dates)
        current_streak = 1
        max_streak = 1
        streak_end_date = sorted_dates[0]
        
        for i in range(1, len(sorted_dates)):
            if (sorted_dates[i] - sorted_dates[i-1]).days == 1:
                current_streak += 1
                if current_streak > max_streak:
                    max_streak = current_streak
                    streak_end_date = sorted_dates[i]
            else:
                current_streak = 1
        
        if max_streak > max_consecutive:
            violations.append(ViolationDetail(
                constraintId='C3',
                constraintName='Consecutive Working Days',
                violationType='hard',
                description=f'Assignment creates {max_streak} consecutive work days, exceeding limit of {max_consecutive} days ({limit_source})',
                context={
                    'consecutiveDays': max_streak,
                    'maxAllowed': max_consecutive,
                    'limitSource': limit_source,
                    'scheme': scheme,
                    'productType': product_type,
                    'workPattern': employee.workPattern,
                    'streakEndDate': str(streak_end_date)
                }
            ))
        
        return violations
    
    def _check_c4_rest_period(
        self,
        employee: EmployeeInfo,
        all_assignments: List[ExistingAssignment],
        temp_assignment: ExistingAssignment
    ) -> List[ViolationDetail]:
        """
        C4: Rest Period Between Shifts - Check minimum rest hours between consecutive shifts.
        
        Uses values from constraint configuration:
        - defaultValue: base rest period (hours)
        - schemeOverrides: scheme-specific rest periods (e.g., P: 1 hour)
        """
        violations = []
        
        # Get constraint config
        c4_config = self.constraints.get('C4', {})
        default_rest = c4_config.get('defaultValue', 8)
        scheme_overrides = c4_config.get('schemeOverrides', {})
        
        # Sort assignments by start time (normalize to offset-naive for comparison)
        timed_assignments = []
        for assignment in all_assignments:
            if assignment.startDateTime and assignment.endDateTime:
                start_dt = self._normalize_datetime(assignment.startDateTime)
                end_dt = self._normalize_datetime(assignment.endDateTime)
                timed_assignments.append((start_dt, end_dt, assignment))
        
        timed_assignments.sort(key=lambda x: x[0])
        
        # Get scheme-specific rest hours or default
        scheme = self._extract_scheme_letter(employee.scheme)
        min_rest_hours = float(scheme_overrides.get(scheme, default_rest))
        
        for i in range(1, len(timed_assignments)):
            prev_end = timed_assignments[i-1][1]
            curr_start = timed_assignments[i][0]
            
            rest_hours = (curr_start - prev_end).total_seconds() / 3600.0
            
            if rest_hours < min_rest_hours:
                prev_assignment = timed_assignments[i-1][2]
                curr_assignment = timed_assignments[i][2]
                
                violations.append(ViolationDetail(
                    constraintId='C4',
                    constraintName='Rest Period Between Shifts',
                    violationType='hard',
                    description=f'Only {rest_hours:.1f}h rest between shifts, minimum required is {min_rest_hours:.1f}h',
                    context={
                        'restHours': round(rest_hours, 1),
                        'minRequired': min_rest_hours,
                        'previousShiftEnd': prev_assignment.endDateTime,
                        'currentShiftStart': curr_assignment.startDateTime
                    }
                ))
        
        return violations
    
    def _check_c17_monthly_ot(
        self,
        employee: EmployeeInfo,
        all_assignments: List[ExistingAssignment],
        temp_assignment: ExistingAssignment
    ) -> List[ViolationDetail]:
        """
        C17: Monthly OT Cap - Check if assignment causes monthly OT to exceed limit.
        
        Uses values from constraint configuration:
        - defaultValue: base monthly OT cap (hours)
        - schemeOverrides: scheme-specific caps
        """
        violations = []
        
        # Get constraint config
        c17_config = self.constraints.get('C17', {})
        default_cap = c17_config.get('defaultValue', 72)
        scheme_overrides = c17_config.get('schemeOverrides', {})
        
        # Parse temp assignment date
        temp_date = datetime.strptime(temp_assignment.date, '%Y-%m-%d').date()
        temp_month = temp_date.replace(day=1)
        
        # Calculate monthly OT hours
        monthly_ot = 0.0
        assignments_in_month = []
        
        for assignment in all_assignments:
            if not assignment.date:
                continue
            
            assign_date = datetime.strptime(assignment.date, '%Y-%m-%d').date()
            assign_month = assign_date.replace(day=1)
            
            if assign_month == temp_month:
                assignments_in_month.append(assignment)
                # Calculate OT hours (hours beyond 9h per shift)
                ot_hours = self._calculate_ot_hours(assignment)
                monthly_ot += ot_hours
        
        # Determine monthly OT cap based on scheme + product type
        scheme = self._extract_scheme_letter(employee.scheme)
        product_type = employee.productTypeId
        
        # Check scheme overrides first
        monthly_ot_cap = float(scheme_overrides.get(scheme, default_cap))
        
        # Special case: APGD-D10 (Scheme A + APO) - dynamic cap based on month length
        if scheme == 'A' and product_type == 'APO' and scheme not in scheme_overrides:
            from calendar import monthrange
            days_in_month = monthrange(temp_month.year, temp_month.month)[1]
            monthly_ot_cap = round(3.8 * days_in_month, 1)  # ~3.8h OT per day
        
        if monthly_ot > monthly_ot_cap:
            violations.append(ViolationDetail(
                constraintId='C17',
                constraintName='Monthly OT Cap',
                violationType='hard',
                description=f'Monthly OT {monthly_ot:.1f}h exceeds cap of {monthly_ot_cap:.1f}h for {temp_month.strftime("%B %Y")}',
                context={
                    'monthlyOT': round(monthly_ot, 1),
                    'monthlyCap': monthly_ot_cap,
                    'month': temp_month.strftime('%Y-%m'),
                    'assignmentsInMonth': len(assignments_in_month)
                }
            ))
        
        return violations
    
    def _check_off_days_per_week(
        self,
        employee: EmployeeInfo,
        all_assignments: List[ExistingAssignment],
        temp_assignment: ExistingAssignment
    ) -> List[ViolationDetail]:
        """
        Check minimum off-days per week constraint.
        
        Uses values from constraint configuration:
        - defaultValue: minimum off days required per week (default: 1)
        """
        violations = []
        
        # Get constraint config
        config = self.constraints.get('C_OFF_DAYS', {})
        min_off_days = config.get('defaultValue', 1)
        
        # Parse temp assignment date
        temp_date = datetime.strptime(temp_assignment.date, '%Y-%m-%d').date()
        
        # Calculate week boundaries (Sunday to Saturday)
        days_since_sunday = (temp_date.weekday() + 1) % 7
        week_start = temp_date - timedelta(days=days_since_sunday)
        week_end = week_start + timedelta(days=6)
        
        # Count work days in the week
        work_days_in_week = set()
        for assignment in all_assignments:
            if not assignment.date:
                continue
            assign_date = datetime.strptime(assignment.date, '%Y-%m-%d').date()
            if week_start <= assign_date <= week_end:
                # Only count actual work shifts (not off days)
                if assignment.shiftCode and assignment.shiftCode.upper() not in ['O', 'OFF']:
                    work_days_in_week.add(assign_date)
        
        # Calculate off days
        days_in_week = 7
        off_days = days_in_week - len(work_days_in_week)
        
        if off_days < min_off_days:
            violations.append(ViolationDetail(
                constraintId='C_OFF_DAYS',
                constraintName='Minimum Off Days Per Week',
                violationType='hard',
                description=f'Only {off_days} off day(s) in week, minimum required is {min_off_days}',
                context={
                    'offDays': off_days,
                    'minRequired': min_off_days,
                    'workDays': len(work_days_in_week),
                    'weekStart': str(week_start),
                    'weekEnd': str(week_end)
                }
            ))
        
        return violations
    
    def _check_part_timer_weekly_hours(
        self,
        employee: EmployeeInfo,
        all_assignments: List[ExistingAssignment],
        temp_assignment: ExistingAssignment
    ) -> List[ViolationDetail]:
        """
        Check part-timer weekly hour limits (Scheme P only).
        
        Rules:
        - ≤4 working days per week: max 34.98h
        - >4 working days per week: max 29.98h
        """
        violations = []
        
        # Only applies to Scheme P
        scheme = self._extract_scheme_letter(employee.scheme)
        if scheme != 'P':
            return violations
        
        # Get constraint config
        config = self.constraints.get('C_PART_TIMER', {})
        params = config.get('params', {})
        max_hours_4_days = params.get('maxHours4Days', 34.98)
        max_hours_more_days = params.get('maxHoursMoreDays', 29.98)
        
        # Parse temp assignment date
        temp_date = datetime.strptime(temp_assignment.date, '%Y-%m-%d').date()
        
        # Calculate week boundaries (Sunday to Saturday)
        days_since_sunday = (temp_date.weekday() + 1) % 7
        week_start = temp_date - timedelta(days=days_since_sunday)
        week_end = week_start + timedelta(days=6)
        
        # Calculate work days and total hours in the week
        work_days_in_week = set()
        weekly_hours = 0.0
        
        for assignment in all_assignments:
            if not assignment.date:
                continue
            assign_date = datetime.strptime(assignment.date, '%Y-%m-%d').date()
            if week_start <= assign_date <= week_end:
                if assignment.shiftCode and assignment.shiftCode.upper() not in ['O', 'OFF']:
                    work_days_in_week.add(assign_date)
                    # Get hours from assignment
                    if hasattr(assignment.hours, 'gross'):
                        weekly_hours += assignment.hours.gross
                    elif isinstance(assignment.hours, dict):
                        weekly_hours += assignment.hours.get('gross', 0)
        
        num_work_days = len(work_days_in_week)
        
        # Determine applicable limit
        if num_work_days <= 4:
            weekly_cap = max_hours_4_days
            limit_type = "≤4 days"
        else:
            weekly_cap = max_hours_more_days
            limit_type = ">4 days"
        
        if weekly_hours > weekly_cap:
            violations.append(ViolationDetail(
                constraintId='C_PART_TIMER',
                constraintName='Part-Timer Weekly Hours',
                violationType='hard',
                description=f'Part-timer weekly hours {weekly_hours:.2f}h exceeds {weekly_cap:.2f}h limit ({limit_type})',
                context={
                    'weeklyHours': round(weekly_hours, 2),
                    'weeklyCap': weekly_cap,
                    'workDays': num_work_days,
                    'limitType': limit_type,
                    'weekStart': str(week_start),
                    'weekEnd': str(week_end)
                }
            ))
        
        return violations
    
    def _check_monthly_total_hours(
        self,
        employee: EmployeeInfo,
        all_assignments: List[ExistingAssignment],
        temp_assignment: ExistingAssignment
    ) -> List[ViolationDetail]:
        """
        Check monthly total hours limit.
        
        Uses monthlyHourLimits configuration to determine:
        - totalMaxHours: maximum total working hours per month
        """
        violations = []
        
        # Parse temp assignment date
        temp_date = datetime.strptime(temp_assignment.date, '%Y-%m-%d').date()
        temp_month = temp_date.replace(day=1)
        
        # Get days in month
        from calendar import monthrange
        days_in_month = monthrange(temp_month.year, temp_month.month)[1]
        
        # Get monthly limits for this month length
        limits = self.monthly_limits.get(days_in_month, {})
        total_max_hours = limits.get('totalMaxHours')
        
        if not total_max_hours:
            # Use default calculation if not specified
            return violations
        
        # Calculate total hours in the month
        monthly_hours = 0.0
        assignments_in_month = []
        
        for assignment in all_assignments:
            if not assignment.date:
                continue
            
            assign_date = datetime.strptime(assignment.date, '%Y-%m-%d').date()
            assign_month = assign_date.replace(day=1)
            
            if assign_month == temp_month:
                assignments_in_month.append(assignment)
                # Get gross hours from assignment
                if hasattr(assignment.hours, 'gross'):
                    monthly_hours += assignment.hours.gross
                elif isinstance(assignment.hours, dict):
                    monthly_hours += assignment.hours.get('gross', 0)
        
        if monthly_hours > total_max_hours:
            violations.append(ViolationDetail(
                constraintId='C_MONTHLY_TOTAL',
                constraintName='Monthly Total Hours',
                violationType='hard',
                description=f'Monthly total hours {monthly_hours:.1f}h exceeds limit of {total_max_hours}h for {temp_month.strftime("%B %Y")}',
                context={
                    'monthlyHours': round(monthly_hours, 1),
                    'monthlyLimit': total_max_hours,
                    'daysInMonth': days_in_month,
                    'month': temp_month.strftime('%Y-%m'),
                    'assignmentsInMonth': len(assignments_in_month)
                }
            ))
        
        return violations
    
    # ===== Helper Functions =====
    
    def _get_pattern_day_for_date(self, date, work_pattern: list, rotation_offset: int) -> int:
        """Get pattern day index (0-based) for a given date."""
        if not work_pattern:
            return 0
        
        # Calculate days since epoch (2024-01-01 is reference)
        from datetime import date as date_class
        if isinstance(date, str):
            date = datetime.strptime(date, '%Y-%m-%d').date()
        
        epoch = date_class(2024, 1, 1)
        days_since_epoch = (date - epoch).days
        
        # Apply rotation offset
        pattern_day = (days_since_epoch + rotation_offset) % len(work_pattern)
        return pattern_day
    
    def _count_work_days_in_pattern(self, pattern: list) -> int:
        """Count total work days in pattern."""
        if not pattern:
            return 5  # Default assumption
        return sum(1 for day in pattern if day != 'O')
    
    def _analyze_consecutive_positions(self, pattern: list) -> dict:
        """Analyze work pattern to identify consecutive work day positions.
        
        Returns dict mapping pattern_index -> consecutive_position.
        Example: ['D','D','D','D','D','D','O'] -> {0:1, 1:2, 2:3, 3:4, 4:5, 5:6, 6:0}
        """
        if not pattern:
            return {}
        
        position_map = {}
        consecutive_count = 0
        
        for idx, day in enumerate(pattern):
            if day != 'O':
                consecutive_count += 1
                position_map[idx] = consecutive_count
            else:
                position_map[idx] = 0
                consecutive_count = 0
        
        return position_map
    
    def _calculate_pattern_aware_normal_hours(
        self,
        assignment: ExistingAssignment,
        work_pattern: list,
        pattern_day: int,
        scheme: str,
        week_assignments: dict,
        week_start
    ) -> float:
        """Calculate normal hours using pattern-aware logic (matches main solver).
        
        Args:
            assignment: Assignment to calculate hours for
            work_pattern: Employee work pattern
            pattern_day: Pattern day index (0-based)
            scheme: 'A', 'B', or 'P'
            week_assignments: Dict of date -> assignment for the week
            week_start: Start date of the week
        
        Returns:
            Normal hours for this assignment
        """
        # Get gross and lunch hours
        if hasattr(assignment.hours, 'gross'):
            gross_hours = assignment.hours.gross
            lunch_hours = assignment.hours.lunch if hasattr(assignment.hours, 'lunch') else 0.0
        elif isinstance(assignment.hours, dict):
            gross_hours = assignment.hours.get('gross', 0.0)
            lunch_hours = assignment.hours.get('lunch', 0.0)
        else:
            gross_hours = assignment.hours or 0.0
            lunch_hours = 1.0 if gross_hours > 6 else 0.0
        
        working_hours = gross_hours - lunch_hours
        
        if not work_pattern:
            # Fallback: 8.8h threshold
            return min(8.8, working_hours)
        
        work_days_count = self._count_work_days_in_pattern(work_pattern)
        consecutive_positions = self._analyze_consecutive_positions(work_pattern)
        consecutive_pos = consecutive_positions.get(pattern_day, 0)
        
        # SCHEME P (PART-TIME)
        if scheme == 'P':
            if work_days_count <= 4:
                return min(8.745, working_hours)
            elif work_days_count == 5:
                if consecutive_pos >= 5:
                    return 0.0  # 5th day entire shift is OT
                return min(5.996, working_hours)
            elif work_days_count == 6:
                return min(4.996, working_hours)
            elif work_days_count >= 7:
                return min(4.283, working_hours)
            else:
                return min(8.745, working_hours)
        
        # SCHEME A/B (FULL-TIME)
        if work_days_count == 4:
            return min(11.0, working_hours)
        elif work_days_count == 5:
            return min(8.8, working_hours)
        elif work_days_count >= 6:
            if consecutive_pos >= 6:
                # 6th+ consecutive day: 0h normal (rest day pay = 8.0h)
                return 0.0
            else:
                # Days 1-5: 8.8h normal
                return min(8.8, working_hours)
        else:
            # Fallback
            return min(8.8, working_hours)
    
    def _calculate_normal_hours(self, assignment: ExistingAssignment) -> float:
        """
        Calculate normal working hours for an assignment.
        
        Uses hours breakdown if available, otherwise calculates from gross hours.
        Normal hours = gross hours - lunch hours, capped at 8h (rest is OT)
        """
        # New format: HoursBreakdown object
        if hasattr(assignment.hours, 'normal'):
            return assignment.hours.normal
        
        # Dict format
        if isinstance(assignment.hours, dict):
            return assignment.hours.get('normal', 0.0)
        
        # Fallback: calculate from simple hours value
        gross_hours = assignment.hours or 0.0
        if gross_hours <= 0:
            return 0.0
        
        # Deduct lunch (1h if shift > 6h)
        lunch_hours = 1.0 if gross_hours > 6 else 0.0
        net_hours = gross_hours - lunch_hours
        
        # Cap at 8h (rest is OT)
        normal_hours = min(net_hours, 8.0)
        return max(normal_hours, 0.0)
    
    def _calculate_ot_hours(self, assignment: ExistingAssignment) -> float:
        """
        Calculate overtime hours for an assignment.
        
        Uses hours breakdown if available, otherwise calculates from gross hours.
        OT hours = hours beyond 8h (after lunch deduction)
        """
        # New format: HoursBreakdown object
        if hasattr(assignment.hours, 'ot'):
            return assignment.hours.ot
        
        # Dict format
        if isinstance(assignment.hours, dict):
            return assignment.hours.get('ot', 0.0)
        
        # Fallback: calculate from simple hours value
        gross_hours = assignment.hours or 0.0
        
        # Deduct lunch
        lunch_hours = 1.0 if gross_hours > 6.0 else 0.0
        working_hours = gross_hours - lunch_hours
        
        # OT is hours beyond 8h
        ot_hours = max(0.0, working_hours - 8.0)
        
        return ot_hours

