"""S17: Work Continuity - Minimize gaps in employee work schedules (SOFT constraint).

Penalizes "gaps" or isolated unassigned days between work assignments.
Encourages clustering of work days and consolidation of off-days.

This helps reduce scattered U-slots and improves roster readability.
"""
from collections import defaultdict
from datetime import datetime, timedelta


def score_violations(ctx, assignments, score_book):
    """
    Score work continuity violations: penalize gaps between work assignments.
    
    Strategy:
    1. For each employee, identify sequences of: Work - Gap - Work
    2. Penalize each gap day (U-slot between assigned shifts)
    3. Larger gaps get higher penalties
    
    Args:
        ctx: Context dict
        assignments: List of assignment dicts
        score_book: ScoreBook instance for recording violations
    """
    
    employees = ctx.get('employees', [])
    slots = ctx.get('slots', [])
    
    if not assignments or not employees:
        return
    
    # Get planning horizon dates
    all_dates = sorted(set(slot.date for slot in slots))
    if len(all_dates) < 3:
        # Too short to have meaningful gaps
        return
    
    # Group assignments by employee and date
    emp_work_dates = defaultdict(set)
    for assignment in assignments:
        emp_id = assignment.get('employeeId')
        date_str = assignment.get('date')
        if emp_id and date_str:
            # Convert string to date object for comparison
            if isinstance(date_str, str):
                date_obj = datetime.fromisoformat(date_str).date()
            else:
                date_obj = date_str
            emp_work_dates[emp_id].add(date_obj)
    
    total_gap_days = 0
    total_gap_sequences = 0
    
    # For each employee, find gaps
    for emp in employees:
        emp_id = emp.get('employeeId')
        
        if emp_id not in emp_work_dates:
            continue  # Employee has no assignments
        
        work_dates = sorted(emp_work_dates[emp_id])
        
        if len(work_dates) < 2:
            continue  # Need at least 2 work days to have a gap
        
        # Find gaps: days between work assignments that are not worked
        for i in range(len(work_dates) - 1):
            start_work = work_dates[i]
            end_work = work_dates[i + 1]
            
            # Calculate days between these work days
            days_between = (end_work - start_work).days - 1  # Exclude the work days themselves
            
            if days_between > 0 and days_between <= 7:
                # There's a gap of 1-7 days (anything longer is likely intentional rest period)
                # Check if these gap days are actually available (not rest pattern days)
                
                # Penalize the gap
                gap_penalty = days_between * 10  # 10 points per gap day
                total_gap_days += days_between
                total_gap_sequences += 1
                
                score_book.add_violation(
                    constraint_id='S17',
                    constraint_name='Work Continuity',
                    violation_type='gap_in_schedule',
                    penalty=gap_penalty,
                    details=f"Employee {emp_id}: {days_between}-day gap between {start_work} and {end_work}"
                )
    
    if total_gap_sequences > 0:
        print(f"[S17] Work Continuity (SOFT)")
        print(f"     Total gaps: {total_gap_sequences} sequences ({total_gap_days} gap days)")
        print(f"     Total penalty: {total_gap_sequences * total_gap_days * 10}")
