# Empty Slots Solving - Implementation Plan

**Date:** January 2, 2026  
**Version:** v0.96  
**Status:** Implementation in Progress

---

## 📋 Overview

Implement a new "Empty Slots" solving mode that accepts only unfilled slots + locked employee context, eliminating the need to send full roster history. This is a **standalone feature** separate from incremental solving.

### Key Benefits
- **97% smaller payloads**: Send only 50 empty slots vs 1,550 full assignments
- **Faster processing**: No classification needed, direct to solving
- **Clearer intent**: Explicit about what needs to be filled
- **Better API design**: Client manages history, server optimizes

---

## 🏗️ Architecture

### Input Structure

```json
{
  "schemaVersion": "0.96",
  "planningReference": "JAN2026_CHANGIT1_APO",
  "solveMode": "emptySlots",
  
  "emptySlots": [
    {
      "slotId": "D001-2026-01-15-D-abc123",
      "date": "2026-01-15",
      "shiftCode": "D",
      "requirementId": "REQ_APO_CHANGIT1_DAY",
      "demandId": "D001",
      "locationId": "ChangiT1",
      "productTypeId": "APO",
      "rankId": "APO",
      "startTime": "07:00:00",
      "endTime": "19:00:00",
      "reason": "UNASSIGNED"
    }
  ],
  
  "lockedContext": {
    "cutoffDate": "2026-01-10",
    "employeeAssignments": [
      {
        "employeeId": "ALPHA_001",
        "assignedDates": ["2026-01-01", "2026-01-02", "2026-01-05"],
        "weeklyHours": {
          "2026-W01": 32.0,
          "2026-W02": 12.0
        },
        "monthlyHours": 44.0,
        "consecutiveWorkingDays": 3,
        "lastWorkDate": "2026-01-10",
        "rotationOffset": 0,
        "workPatternId": "ALPHA_4ON3OFF"
      }
    ]
  },
  
  "employees": [
    {
      "employeeId": "ALPHA_001",
      "rankId": "APO",
      "locationId": "ChangiT1",
      "workPattern": "4ON3OFF",
      "rotationOffset": 0
    }
  ],
  
  "demandItems": [
    {
      "requirementId": "REQ_APO_CHANGIT1_DAY",
      "locationId": "ChangiT1",
      "rankId": "APO",
      "shifts": [
        {
          "shiftCode": "D",
          "startTime": "07:00:00",
          "endTime": "19:00:00"
        }
      ]
    }
  ],
  
  "planningHorizon": {
    "startDate": "2026-01-11",
    "endDate": "2026-01-31"
  },
  
  "constraintList": [...],
  "solverScoreConfig": {...}
}
```

---

## 🔧 Implementation Components

### 1. Pydantic Models (`src/models.py`)

```python
class EmptySlot(BaseModel):
    """Slot that needs to be filled."""
    slotId: str = Field(..., description="Unique slot identifier")
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    shiftCode: str = Field(..., description="Shift code (D, N, E, etc.)")
    requirementId: str = Field(..., description="Links to demandItems requirement")
    demandId: str = Field(..., description="Demand identifier")
    locationId: str = Field(..., description="Location identifier")
    productTypeId: str = Field(..., description="Product type identifier")
    rankId: str = Field(..., description="Rank/position identifier")
    startTime: str = Field(..., description="HH:MM:SS format")
    endTime: str = Field(..., description="HH:MM:SS format")
    reason: str = Field(..., description="Why slot is empty", 
                        enum=["UNASSIGNED", "DEPARTED_EMPLOYEE", "LONG_LEAVE", "MANUAL_RELEASE"])

class EmployeeLockedContext(BaseModel):
    """Pre-computed context for each employee from locked assignments."""
    employeeId: str
    assignedDates: List[str] = Field(default=[], description="Dates already worked (YYYY-MM-DD)")
    weeklyHours: Dict[str, float] = Field(default={}, description="{week_key: hours}")
    monthlyHours: float = Field(default=0.0, description="Total hours this month")
    consecutiveWorkingDays: int = Field(default=0, description="Current working streak")
    lastWorkDate: Optional[str] = Field(None, description="Last date worked (YYYY-MM-DD)")
    rotationOffset: Optional[int] = Field(None, description="Current rotation offset")
    workPatternId: Optional[str] = Field(None, description="Work pattern identifier")

class LockedContext(BaseModel):
    """Context from locked/historical assignments."""
    cutoffDate: str = Field(..., description="Date before which all assignments are locked")
    employeeAssignments: List[EmployeeLockedContext] = Field(default=[])

class EmptySlotsRequest(BaseModel):
    """Request for empty slots solving mode."""
    schemaVersion: str = Field("0.96", description="Schema version")
    planningReference: str = Field(..., description="Planning reference")
    solveMode: str = Field("emptySlots", const=True, description="Must be 'emptySlots'")
    
    emptySlots: List[EmptySlot] = Field(..., description="Slots to fill")
    lockedContext: LockedContext = Field(..., description="Pre-computed employee context")
    
    employees: List[Dict[str, Any]] = Field(..., description="Available employees")
    demandItems: List[Dict[str, Any]] = Field(..., description="Demand requirements")
    planningHorizon: Dict[str, str] = Field(..., description="Start/end dates")
    
    constraintList: Optional[List[Dict[str, Any]]] = Field(None)
    solverScoreConfig: Optional[Dict[str, Any]] = Field(None)
    solverConfig: Optional[Dict[str, Any]] = Field(None)
```

---

### 2. Solver Module (`src/empty_slots_solver.py`)

```python
"""
Empty Slots Solver

Optimized solving mode that accepts only empty slots + locked employee context.
Bypasses slot classification and directly builds solvable slots from input.
"""

from datetime import datetime
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class EmptySlotsSolverError(Exception):
    """Errors during empty slots solving."""
    pass

def validate_empty_slots_request(request_data: Dict[str, Any]) -> None:
    """
    Validate empty slots request structure.
    
    Raises:
        EmptySlotsSolverError: If validation fails
    """
    # Check required fields
    required = ["emptySlots", "lockedContext", "employees", "demandItems", "planningHorizon"]
    for field in required:
        if field not in request_data:
            raise EmptySlotsSolverError(f"Missing required field: {field}")
    
    # Validate empty slots
    empty_slots = request_data["emptySlots"]
    if not isinstance(empty_slots, list):
        raise EmptySlotsSolverError("emptySlots must be a list")
    
    if len(empty_slots) == 0:
        raise EmptySlotsSolverError("emptySlots cannot be empty")
    
    # Validate locked context
    locked_context = request_data["lockedContext"]
    if "cutoffDate" not in locked_context:
        raise EmptySlotsSolverError("lockedContext missing cutoffDate")
    
    # Validate planning horizon
    horizon = request_data["planningHorizon"]
    if "startDate" not in horizon or "endDate" not in horizon:
        raise EmptySlotsSolverError("planningHorizon missing startDate or endDate")
    
    logger.info(f"✓ Empty slots request validated: {len(empty_slots)} slots")

def build_demand_items_from_empty_slots(
    empty_slots: List[Dict[str, Any]],
    planning_horizon: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Build demandItems structure from empty slots.
    
    Groups empty slots by requirementId and builds demand structure
    that the solver engine expects.
    """
    from collections import defaultdict
    from datetime import datetime
    
    start_date = datetime.fromisoformat(planning_horizon["startDate"]).date()
    end_date = datetime.fromisoformat(planning_horizon["endDate"]).date()
    
    # Group slots by requirementId
    slots_by_requirement = defaultdict(list)
    for slot in empty_slots:
        req_id = slot["requirementId"]
        slots_by_requirement[req_id].append(slot)
    
    # Build demand items
    demand_items = []
    for req_id, slots in slots_by_requirement.items():
        # Use first slot as template
        template = slots[0]
        
        # Count slots per date
        slots_per_date = defaultdict(int)
        for slot in slots:
            slot_date = datetime.fromisoformat(slot["date"]).date()
            slots_per_date[slot_date] += 1
        
        # Build demand item
        demand_item = {
            "requirementId": req_id,
            "demandId": template.get("demandId", req_id),
            "locationId": template["locationId"],
            "productTypeId": template["productTypeId"],
            "rankId": template["rankId"],
            "shifts": [
                {
                    "shiftCode": template["shiftCode"],
                    "startTime": template["startTime"],
                    "endTime": template["endTime"]
                }
            ],
            "demandPattern": []
        }
        
        # Build demand pattern for date range
        current_date = start_date
        while current_date <= end_date:
            count = slots_per_date.get(current_date, 0)
            demand_item["demandPattern"].append({
                "date": current_date.isoformat(),
                "count": count
            })
            current_date += timedelta(days=1)
        
        demand_items.append(demand_item)
    
    logger.info(f"Built {len(demand_items)} demand items from {len(empty_slots)} empty slots")
    return demand_items

def solve_empty_slots(
    request_data: Dict[str, Any],
    solver_engine: Any,
    run_id: str
) -> Dict[str, Any]:
    """
    Solve empty slots without full roster history.
    
    Args:
        request_data: EmptySlotsRequest data
        solver_engine: Solver engine function
        run_id: Unique run identifier
        
    Returns:
        Solution with only new assignments (no merging with locked)
    """
    logger.info("=" * 80)
    logger.info("[EMPTY SLOTS SOLVER STARTING]")
    logger.info("=" * 80)
    
    # Validate request
    validate_empty_slots_request(request_data)
    
    # Extract components
    empty_slots = request_data["emptySlots"]
    locked_context = request_data["lockedContext"]
    employees = request_data["employees"]
    planning_horizon = request_data["planningHorizon"]
    
    logger.info(f"Empty slots: {len(empty_slots)}")
    logger.info(f"Locked employees: {len(locked_context.get('employeeAssignments', []))}")
    logger.info(f"Available employees: {len(employees)}")
    
    # Build demand items from empty slots
    demand_items = request_data.get("demandItems")
    if not demand_items:
        # Auto-generate from empty slots
        demand_items = build_demand_items_from_empty_slots(empty_slots, planning_horizon)
    
    # Parse locked context
    locked_weekly_hours = {}
    locked_consecutive_days = {}
    employee_context_map = {}
    
    for emp_ctx in locked_context.get("employeeAssignments", []):
        emp_id = emp_ctx["employeeId"]
        
        # Weekly hours: convert string keys to tuples
        locked_weekly_hours[emp_id] = {
            tuple(map(int, k.replace("W", "-").split("-"))): v
            for k, v in emp_ctx.get("weeklyHours", {}).items()
        }
        
        # Consecutive days
        locked_consecutive_days[emp_id] = emp_ctx.get("consecutiveWorkingDays", 0)
        
        # Store full context
        employee_context_map[emp_id] = emp_ctx
    
    # Build solver input
    solver_input = {
        "schemaVersion": request_data.get("schemaVersion", "0.96"),
        "planningReference": request_data["planningReference"],
        "planningHorizon": planning_horizon,
        "employees": employees,
        "demandItems": demand_items,
        "constraintList": request_data.get("constraintList", []),
        "solverScoreConfig": request_data.get("solverScoreConfig", {}),
        "solverConfig": request_data.get("solverConfig", {}),
        
        # Empty slots context
        "_emptySlots": {
            "mode": "emptySlots",
            "emptySlots": empty_slots,
            "lockedWeeklyHours": locked_weekly_hours,
            "lockedConsecutiveDays": locked_consecutive_days,
            "lockedContext": locked_context,
            "employeeContextMap": employee_context_map
        }
    }
    
    # Invoke solver
    logger.info("Invoking solver engine...")
    try:
        status, solver_result, assignments, violations = solver_engine(solver_input)
        
        logger.info(f"✓ Solver completed: {status}")
        logger.info(f"  Assignments: {len(assignments)}")
        logger.info(f"  Violations: {len(violations)}")
        
    except Exception as e:
        logger.error(f"✗ Solver failed: {e}", exc_info=True)
        raise EmptySlotsSolverError(f"Solver execution failed: {e}")
    
    # Build output
    from src.output_builder import build_output
    
    output = build_output(
        input_data=request_data,
        ctx=solver_input,
        status=solver_result.get("status", "UNKNOWN"),
        solver_result=solver_result,
        assignments=assignments,
        violations=violations
    )
    
    # Add empty slots metadata
    filled_count = len([a for a in assignments if a.get("employeeId")])
    unassigned_count = len([a for a in assignments if a.get("status") == "UNASSIGNED"])
    
    output["emptySlotsMetadata"] = {
        "mode": "emptySlots",
        "emptySlotCount": len(empty_slots),
        "filledSlotCount": filled_count,
        "unassignedSlotCount": unassigned_count,
        "cutoffDate": locked_context["cutoffDate"],
        "reasonBreakdown": _count_reasons(empty_slots)
    }
    
    logger.info("=" * 80)
    logger.info("[EMPTY SLOTS SOLVER COMPLETED]")
    logger.info("=" * 80)
    
    return output

def _count_reasons(empty_slots: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count empty slots by reason."""
    from collections import Counter
    return dict(Counter(slot.get("reason", "UNKNOWN") for slot in empty_slots))
```

---

### 3. API Endpoint (`src/api_server.py`)

```python
@app.post("/solve/empty-slots", response_class=ORJSONResponse)
async def solve_empty_slots_endpoint(
    request: Request,
    payload: EmptySlotsRequest
):
    """
    Solve empty slots without full roster history.
    
    Optimized mode that accepts:
    - List of empty slots (what needs filling)
    - Locked employee context (pre-computed hours, consecutive days)
    - Available employees
    
    Benefits:
    - 97% smaller payload (send only empty slots vs full roster)
    - Faster processing (no classification needed)
    - Clearer intent (explicit about what to solve)
    
    All constraints (C1-C17, S1-S16) are fully applied.
    
    Returns:
    - 200: Solution completed (may have unassigned slots)
    - 400: Invalid request (missing data, validation errors)
    - 422: Schema validation error
    - 500: Solver error
    """
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    logger.info(f"[{request_id}] Empty slots solve request received")
    
    try:
        # Convert to dict
        request_data = payload.model_dump()
        
        # Generate run ID
        run_id = f"empty-{int(time.time())}-{request_id[:8]}"
        
        # Call empty slots solver
        from src.empty_slots_solver import solve_empty_slots
        
        result = solve_empty_slots(
            request_data=request_data,
            solver_engine=solver_engine,
            run_id=run_id
        )
        
        logger.info(f"[{request_id}] Empty slots solve completed successfully")
        
        return {
            "status": "success",
            "data": result,
            "meta": {
                "requestId": request_id,
                "runId": run_id,
                "timestamp": datetime.now().isoformat(),
                "schemaVersion": request_data.get("schemaVersion", "0.96")
            }
        }
        
    except Exception as e:
        logger.error(f"[{request_id}] Empty slots solve failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
```

---

## ✅ Constraint Compatibility

All constraints will work with empty slots mode:

### Hard Constraints (C1-C17)
- **C1 MOM Daily Hours**: Uses employee hours, works ✓
- **C2 Pattern Hours**: Reads `workPatternId` from `lockedContext.employeeAssignments` ✓
- **C3 Consecutive Days**: Uses `lockedConsecutiveDays` from locked context ✓
- **C4 Rest Between Shifts**: Uses `lastWorkDate` from locked context ✓
- **C5-C17**: All other constraints work on current solve window ✓

### Soft Constraints (S1-S16)
- **S14 Midmonth Insert**: Informational only, works ✓
- **All others**: Calculate violations from new assignments ✓

### Key Integration Points

1. **Weekly Hours (C1, C2)**:
   ```python
   if ctx.get('_emptySlots'):
       locked_hours = ctx['_emptySlots']['lockedWeeklyHours']
       current_week_hours = locked_hours.get(emp_id, {}).get(week_key, 0.0)
   ```

2. **Consecutive Days (C3)**:
   ```python
   if ctx.get('_emptySlots'):
       locked_streak = ctx['_emptySlots']['lockedConsecutiveDays'].get(emp_id, 0)
       total_consecutive = locked_streak + current_consecutive
   ```

3. **Rest Between Shifts (C4)**:
   ```python
   if ctx.get('_emptySlots'):
       emp_ctx = ctx['_emptySlots']['employeeContextMap'].get(emp_id)
       last_work_date = emp_ctx.get('lastWorkDate') if emp_ctx else None
   ```

---

## 🧪 Testing Strategy

### 1. Unit Tests

Create `tests/test_empty_slots_solver.py`:
```python
def test_validate_empty_slots_request():
    """Test request validation."""
    
def test_build_demand_items_from_empty_slots():
    """Test demand item generation."""
    
def test_solve_empty_slots_basic():
    """Test basic solving with 10 empty slots."""
    
def test_empty_slots_with_locked_hours():
    """Test that locked weekly hours are respected."""
    
def test_empty_slots_with_consecutive_days():
    """Test consecutive day caps with locked context."""
```

### 2. Integration Tests

Create `test_scripts/test_empty_slots_api.py`:
```python
def test_empty_slots_endpoint():
    """Test /solve/empty-slots endpoint."""
    
def test_compare_empty_slots_vs_incremental():
    """Compare empty slots mode with incremental mode - should give same result."""
```

### 3. Constraint Tests

Run all existing constraint tests with empty slots mode:
```bash
pytest tests/ -k "constraint" --empty-slots-mode
```

---

## 📦 Deliverables

1. ✅ **Implementation Plan** (this document)
2. **Code Changes**:
   - `src/models.py`: Add 4 new Pydantic models
   - `src/empty_slots_solver.py`: New 300-line module
   - `src/api_server.py`: Add 1 new endpoint
3. **Tests**:
   - `tests/test_empty_slots_solver.py`: Unit tests
   - `test_scripts/test_empty_slots_api.py`: Integration tests
   - `input/empty_slots_test.json`: Sample input
4. **Documentation**:
   - Update `README.md`: Add empty slots mode section
   - Update `implementation_docs/FASTAPI_QUICK_REFERENCE.md`: Add endpoint docs

---

## 📅 Implementation Timeline

- **Phase 1** (2 hours): Pydantic models + validation
- **Phase 2** (4 hours): Empty slots solver module
- **Phase 3** (2 hours): API endpoint integration
- **Phase 4** (3 hours): Test suite
- **Phase 5** (1 hour): Documentation updates

**Total Estimate**: 12 hours (1.5 days)

---

## 🚀 Deployment Plan

1. **Local Testing**: Test with sample inputs
2. **Dev Deployment**: Deploy to dev environment
3. **Regression Testing**: Ensure existing modes still work
4. **Production**: Deploy with monitoring

---

## ✅ Success Criteria

- [ ] Empty slots mode accepts minimal input (only unfilled slots)
- [ ] All C1-C17 hard constraints enforced
- [ ] All S1-S16 soft constraints scored
- [ ] 97% payload reduction vs full roster
- [ ] Same solution quality as incremental mode
- [ ] API responds < 200ms for 50 slots
- [ ] Unit test coverage > 90%
- [ ] Integration tests pass
- [ ] Documentation complete

---

**Status**: Ready for implementation  
**Next Step**: Add Pydantic models to `src/models.py`
