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
    
    # Default constraint configuration
    DEFAULT_CONSTRAINTS = {
        'C1': {'enabled': True, 'name': 'Daily Hours Cap', 'params': {}},
        'C2': {'enabled': True, 'name': 'Weekly Hours Cap', 'params': {}},
        'C3': {'enabled': True, 'name': 'Consecutive Working Days', 'params': {}},
        'C4': {'enabled': True, 'name': 'Rest Period Between Shifts', 'params': {}},
        'C17': {'enabled': True, 'name': 'Monthly OT Cap', 'params': {}},
    }
    
    def __init__(self):
        """Initialize validator with default configuration."""
        self.constraints = self.DEFAULT_CONSTRAINTS.copy()
    
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
        """Update constraint configuration from request."""
        for constraint_config in constraint_list:
            # Handle both dict and Pydantic model
            if hasattr(constraint_config, 'constraintId'):
                constraint_id = constraint_config.constraintId
                enabled = constraint_config.enabled
                params = constraint_config.params if hasattr(constraint_config, 'params') else None
            else:
                constraint_id = constraint_config.get('constraintId')
                enabled = constraint_config.get('enabled', True)
                params = constraint_config.get('params')
            
            if constraint_id in self.constraints:
                self.constraints[constraint_id]['enabled'] = enabled
                if params:
                    self.constraints[constraint_id]['params'] = params
    
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
        
        # Calculate hour breakdown (gross - 1h lunch, capped at 8h normal)
        gross_hours = hours
        lunch_hours = 1.0 if gross_hours > 6 else 0.0
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
        
        Limits (gross hours):
        - Scheme A: 14 hours
        - Scheme B: 13 hours
        - Scheme P: 9 hours
        """
        violations = []
        
        # Extract scheme letter and get daily cap
        scheme_letter = self._extract_scheme_letter(employee.scheme)
        daily_caps = {
            'A': 14.0,
            'B': 13.0,
            'P': 9.0
        }
        daily_cap = daily_caps.get(scheme_letter, 14.0)
        
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
        C2: Weekly Hours Cap - Check if assignment causes weekly hours to exceed limit.
        
        Limit: 44 hours normal hours per week (same for all schemes)
        Week definition: Sunday to Saturday
        
        Note: Normal hours exclude lunch break and OT hours
        """
        violations = []
        
        # Parse temp assignment date
        temp_date = datetime.strptime(temp_assignment.date, '%Y-%m-%d').date()
        
        # Calculate week boundaries (Sunday to Saturday)
        # Get Sunday of the week containing temp_date
        days_since_sunday = (temp_date.weekday() + 1) % 7  # Monday=0, Sunday=6 -> Sunday=0
        week_start = temp_date - timedelta(days=days_since_sunday)
        week_end = week_start + timedelta(days=6)
        
        # Group assignments by week
        weekly_hours = 0.0
        assignments_in_week = []
        
        for assignment in all_assignments:
            if not assignment.date:
                continue
            
            assign_date = datetime.strptime(assignment.date, '%Y-%m-%d').date()
            
            if week_start <= assign_date <= week_end:
                assignments_in_week.append(assignment)
                # Calculate normal hours (excluding lunch and OT)
                normal_hours = self._calculate_normal_hours(assignment)
                weekly_hours += normal_hours
        
        # Get weekly cap based on scheme
        scheme = employee.scheme.upper()
        weekly_cap = 52.0  # Default maximum
        weekly_min = 44.0  # MOM standard
        
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
                    'assignmentsInWeek': len(assignments_in_week)
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
        
        Limit determination priority:
        1. Scheme + ProductType specific (e.g., Scheme A + APO = 8 days per APGD-D10)
        2. Work pattern-derived limit (count consecutive work days in pattern)
        3. MOM absolute maximum: 12 days fallback
        
        Common limits:
        - Scheme A + APO (APGD-D10): 8 days
        - Other schemes: 12 days (MOM maximum)
        """
        violations = []
        
        # Sort assignments by date
        dated_assignments = [a for a in all_assignments if a.date]
        dated_assignments.sort(key=lambda x: x.date)
        
        if not dated_assignments:
            return violations
        
        # Extract scheme letter for comparison
        scheme = self._extract_scheme_letter(employee.scheme)
        product_type = employee.productTypeId
        
        # Determine max consecutive days based on scheme + product type
        # Match main solver's C3 logic: Scheme A + APO = 8 days (APGD-D10)
        max_consecutive = 12  # MOM absolute maximum (default)
        limit_source = "MOM default"
        
        if scheme == 'A' and product_type == 'APO':
            # APGD-D10: Scheme A employees with APO product type
            max_consecutive = 8
            limit_source = "APGD-D10 (Scheme A + APO)"
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
            
            if pattern_max > 0 and pattern_max < max_consecutive:
                max_consecutive = pattern_max
                limit_source = f"work pattern ({employee.workPattern})"
        
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
        
        Limits (from apgdMinRestBetweenShifts):
        - Default: 8 hours (standard rest period)
        - Scheme P: 1 hour (allows split-shift patterns)
        """
        violations = []
        
        # Sort assignments by start time (normalize to offset-naive for comparison)
        timed_assignments = []
        for assignment in all_assignments:
            if assignment.startDateTime and assignment.endDateTime:
                start_dt = self._normalize_datetime(assignment.startDateTime)
                end_dt = self._normalize_datetime(assignment.endDateTime)
                timed_assignments.append((start_dt, end_dt, assignment))
        
        timed_assignments.sort(key=lambda x: x[0])
        
        # Check rest period between consecutive shifts
        # Scheme-specific: P = 1 hour (split-shift), others = 8 hours
        scheme = self._extract_scheme_letter(employee.scheme)
        min_rest_hours = 1.0 if scheme == 'P' else 8.0
        
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
        
        Limits (from momMonthlyOTcap72h and APGD-D10 rules):
        - Standard: 72 hours per month
        - APGD-D10 (Scheme A + APO): 112-124 hours (varies by month length)
        
        Note: APGD-D10 limit is ~3.8h/day × days_in_month
        """
        violations = []
        
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
        # APGD-D10 (Scheme A + APO): ~3.8h/day × days_in_month
        # Standard: 72 hours per month
        scheme = self._extract_scheme_letter(employee.scheme)
        product_type = employee.productTypeId
        
        if scheme == 'A' and product_type == 'APO':
            # APGD-D10: Higher monthly OT cap based on month length
            # Feb: 28-29 days → 106-110h, Others: 30-31 days → 114-118h
            from calendar import monthrange
            days_in_month = monthrange(temp_month.year, temp_month.month)[1]
            monthly_ot_cap = round(3.8 * days_in_month, 1)  # ~3.8h OT per day
        else:
            monthly_ot_cap = 72.0
        
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
    
    # ===== Helper Functions =====
    
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

