"""S17: Work Continuity - Encourage 6-day same-week patterns and reduce gaps (SOFT constraint).

Soft constraint that rewards:
1. **6 work days within same ISO week** (primary goal - fills more slots, reduces gaps)
2. Consecutive work day sequences (fewer gaps = better)
3. Alignment with DDDDDOD pattern (6 work + 1 off)

Strategy:
- REWARD: Employees who work 6 days within single ISO week
- PENALIZE: Gaps that break potential 6-day weeks
- PENALIZE: Cross-week fragmentation (e.g., 4 days week1 + 2 days week2)

This encourages solver to pack work days efficiently within ISO weeks.
"""
from collections import defaultdict
from datetime import datetime, timedelta


def score_violations(ctx, assignments, score_book):
    """
    Score work continuity - reward 6-day same-week patterns, penalize gaps.
    
    Scoring Rules:
    1. -200 points: Employee works 6 days in single ISO week (REWARD - negative reduces total penalty)
    2. +50 points per gap day: Gaps between work days (PENALTY)
    3. +100 points: 6 consecutive days but spanning 2 ISO weeks (PENALTY)
    
    Args:
        ctx: Context dict
        assignments: List of assignment dicts
        score_book: ScoreBook instance for recording violations
    """
    
    # Get config
    config = ctx.get('solverScoreConfig', {})
    same_week_6day_bonus = config.get('sameWeek6DayBonus', -200)  # Negative = reward (reduces penalty)
    gap_penalty = config.get('gapPenalty', 50)
    cross_week_penalty = config.get('crossWeekPenalty', 100)
    
    # Group assignments by employee and ISO week
    employee_dates = defaultdict(list)
    employee_weeks = defaultdict(lambda: defaultdict(int))  # emp -> week_key -> work_day_count
    
    for assignment in assignments:
        emp_id = assignment.get('employeeId')
        date_str = assignment.get('date')
        shift_code = assignment.get('shiftCode', '')
        
        if emp_id and date_str and shift_code and shift_code != 'O':
            try:
                if isinstance(date_str, str):
                    date_obj = datetime.fromisoformat(date_str).date()
                else:
                    date_obj = date_str
                    
                employee_dates[emp_id].append(date_obj)
                
                # Track work days per ISO week
                iso_year, iso_week, _ = date_obj.isocalendar()
                week_key = f"{iso_year}-W{iso_week:02d}"
                employee_weeks[emp_id][week_key] += 1
            except:
                continue
    
    total_penalty = 0
    rewards = 0
    gap_penalties = 0
    cross_week_penalties = 0
    six_day_weeks = 0
    
    # Score each employee
    for emp_id, dates in employee_dates.items():
        if len(dates) < 2:
            continue
        
        sorted_dates = sorted(dates)
        
        # 1. REWARD: Count 6-day same-week patterns
        for week_key, work_days in employee_weeks[emp_id].items():
            if work_days == 6:
                # Employee worked 6 days in this ISO week - REWARD!
                total_penalty += same_week_6day_bonus  # Negative value = reduces penalty
                rewards += abs(same_week_6day_bonus)
                six_day_weeks += 1
        
        # 2. PENALIZE: Gaps between work days
        for i in range(len(sorted_dates) - 1):
            gap = (sorted_dates[i + 1] - sorted_dates[i]).days - 1
            
            if gap > 0 and gap <= 7:  # Only penalize gaps up to 7 days
                # Gap found - penalize
                gap_cost = gap_penalty * gap
                total_penalty += gap_cost
                gap_penalties += gap_cost
        
        # 3. PENALIZE: 6 consecutive days spanning 2 ISO weeks
        # Find consecutive sequences of 6+ days
        consecutive_count = 1
        for i in range(len(sorted_dates) - 1):
            if (sorted_dates[i + 1] - sorted_dates[i]).days == 1:
                consecutive_count += 1
                
                # Check if we hit 6 consecutive
                if consecutive_count == 6:
                    # Check if all 6 days are in same ISO week
                    seq_start = sorted_dates[i - 4]
                    seq_end = sorted_dates[i + 1]
                    
                    start_week = f"{seq_start.isocalendar()[0]}-W{seq_start.isocalendar()[1]:02d}"
                    end_week = f"{seq_end.isocalendar()[0]}-W{seq_end.isocalendar()[1]:02d}"
                    
                    if start_week != end_week:
                        # 6 consecutive days span 2 weeks - penalize
                        total_penalty += cross_week_penalty
                        cross_week_penalties += cross_week_penalty
            else:
                consecutive_count = 1  # Reset on gap
    
    # Record violation (or reward) if there's activity
    if total_penalty != 0 or rewards > 0:
        score_book.add_violation(
            constraint_id='S17',
            constraint_name='Work Continuity',
            violation_type='continuity_scoring',
            penalty=max(0, total_penalty),  # Don't allow negative total
            details=f"6-day same-week rewards: {six_day_weeks} weeks (-{rewards}pts), "
                    f"Gap penalties: +{gap_penalties}pts, "
                    f"Cross-week penalties: +{cross_week_penalties}pts, "
                    f"Net: {round(total_penalty, 2)}pts"
        )
    
    if six_day_weeks > 0:
        print(f"[S17] Work Continuity: {six_day_weeks} employees with 6-day same-week patterns (-{rewards}pts reward)")

