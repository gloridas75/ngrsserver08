"""
Pydantic models for NGRS Solver API.

Defines request/response schemas for validation and documentation.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, List, Any
from datetime import datetime


class SolveRequest(BaseModel):
    """
    Request payload for POST /solve endpoint.
    
    Key Parameters for Pattern-Based Scheduling:
    
    - **fixedRotationOffset** (bool): When using work patterns (e.g., D-D-N-N-O-O), set to `true` 
      to prevent the solver from clustering employees on the same rotation offset. 
      Pre-distribute employee offsets (0-5) in input JSON for optimal coverage.
      
    - **optimizationMode** (str): Choose solver objective:
      - "balanceWorkload" (recommended for patterns): Distributes assignments evenly across employees.
        Naturally achieves minimal employee usage while ensuring full utilization (~20 shifts/employee/month).
        Works seamlessly with continuous adherence and pattern-based rotation.
        
      - "minimizeEmployeeCount": Aggressively minimizes employee count using 100,000× weight penalty.
        WARNING: May conflict with pattern-based scheduling and continuous adherence.
        Can cause offset clustering and INFEASIBLE results. Use only for simple shift coverage.
        
    - **Continuous Adherence Behavior**: When an employee is selected for a work pattern, 
      they will be assigned to work ALL days in their pattern cycle (~20 shifts per month for D-D-N-N-O-O).
      This prevents under-utilization (employees working only 1-2 shifts).
      
    Best Practices:
    - Use balanceWorkload mode for pattern-based rotation schedules
    - Pre-distribute employee rotation offsets (0-5) to ensure coverage diversity
    - Set fixedRotationOffset=true to prevent solver re-clustering
    - Expect 20-21 shifts per employee per month for 6-day patterns
    - For simple shift coverage without patterns, either mode works
    """
    
    input_json: Optional[Dict[str, Any]] = Field(
        None,
        description="Full NGRS input JSON (required if file not provided). "
                    "Should match schema v0.43+. "
                    "See class docstring for optimization mode guidance."
    )
    
    model_config = ConfigDict(extra='allow')  # Forgiving: accept extra fields


class Score(BaseModel):
    """Score breakdown."""
    hard: int = Field(0, description="Hard constraint violations count")
    soft: int = Field(0, description="Soft constraint penalties")
    overall: int = Field(0, description="Overall score (hard + soft)")


class SolverRunMetadata(BaseModel):
    """Metadata about the solve run."""
    runId: str = Field(..., description="Unique run ID")
    solverVersion: str = Field(default="optSolve-py-0.95.0")
    startedAt: str = Field(..., description="ISO 8601 timestamp")
    ended: str = Field(..., description="ISO 8601 timestamp")
    durationSeconds: float = Field(..., description="Total solve time in seconds")
    status: str = Field(..., description="Final solver status: OPTIMAL, FEASIBLE, INFEASIBLE, etc.")
    timeLimitSec: Optional[int] = Field(None, description="Time limit applied")
    numVars: Optional[int] = Field(None, description="Number of decision variables")
    numConstraints: Optional[int] = Field(None, description="Number of constraints")


class Meta(BaseModel):
    """Response metadata."""
    requestId: str = Field(..., description="Unique request ID for tracing")
    generatedAt: str = Field(..., description="ISO 8601 timestamp of response generation")
    inputHash: Optional[str] = Field(None, description="SHA256 hash of input (excluding runtime data)")
    warnings: List[str] = Field(default_factory=list, description="Warning messages")
    employeeHours: Optional[Dict[str, Dict[str, Any]]] = Field(
        None,
        description="Per-employee weekly normal hours and monthly OT aggregates"
    )
    hourBreakdown: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Hour breakdown per assignment (gross, lunch, normal, ot, paid)"
    )


class Assignment(BaseModel):
    """Single assignment in solution."""
    employeeId: str
    date: str
    demandId: str
    shiftCode: str
    patternDay: Optional[int] = Field(
        None,
        description="Position in the work pattern cycle (0 to pattern_length-1). Calculated as (days_since_start + employee_offset) % pattern_length"
    )
    startDateTime: str
    endDateTime: str
    hours: Optional[Dict[str, float]] = Field(
        None,
        description="Hour breakdown: gross, lunch, normal, ot, paid"
    )
    
    model_config = ConfigDict(extra='allow')


class Violation(BaseModel):
    """Constraint violation."""
    constraintId: str
    employeeId: Optional[str] = None
    message: str
    
    model_config = ConfigDict(extra='allow')


class SolveResponse(BaseModel):
    """Response payload from POST /solve endpoint."""
    
    schemaVersion: Optional[str] = Field(
        "0.95",
        description="Schema version of the response (Updated: patternDay field, employeeRoster, rosterSummary)"
    )
    
    planningReference: Optional[str] = Field(
        None,
        description="Reference for the planning period"
    )
    
    solverRun: Optional[SolverRunMetadata] = Field(
        None,
        description="Metadata about the solver execution"
    )
    
    score: Score = Field(..., description="Score breakdown")
    
    scoreBreakdown: Optional[Dict[str, Any]] = Field(
        None,
        description="Detailed score breakdown by constraint"
    )
    
    assignments: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of assignments (employee-shift pairs). Each assignment includes patternDay field showing position in work pattern cycle (0 to pattern_length-1)"
    )
    
    employeeRoster: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Complete daily status for all employees showing ASSIGNED/OFF_DAY/UNASSIGNED/NOT_USED per date. Includes patternDay for ASSIGNED and OFF_DAY statuses"
    )
    
    rosterSummary: Optional[Dict[str, Any]] = Field(
        None,
        description="Summary statistics of roster statuses across all employees and dates. Contains totalDailyStatuses and byStatus breakdown (ASSIGNED, OFF_DAY, UNASSIGNED, NOT_USED counts)"
    )
    
    solutionQuality: Optional[Dict[str, Any]] = Field(
        None,
        description="Solution quality metrics explaining why solution is OPTIMAL/FEASIBLE and utilization statistics"
    )
    
    violations: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Constraint violations found (if any)"
    )
    
    unmetDemand: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list,
        description="Demands that could not be fully met"
    )
    
    meta: Meta = Field(..., description="Response metadata")
    
    error: Optional[str] = Field(
        None,
        description="Error message (if status='ERROR')"
    )
    
    model_config = ConfigDict(extra='allow')


class HealthResponse(BaseModel):
    """Response from GET /health endpoint."""
    status: str = Field("ok")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class SchemaResponse(BaseModel):
    """Response from GET /schema endpoint."""
    inputSchema: Dict[str, Any] = Field(..., description="JSON Schema for input")
    outputSchema: Dict[str, Any] = Field(..., description="JSON Schema for output")


class VersionResponse(BaseModel):
    """Response from GET /version endpoint."""
    apiVersion: str = Field("0.95.0")
    solverVersion: str = Field("optSolve-py-0.95.0")
    schemaVersion: str = Field("0.95")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# ============================================================================
# ASYNC MODE MODELS
# ============================================================================

class AsyncJobRequest(BaseModel):
    """Request payload for POST /solve/async endpoint."""
    
    input_json: Optional[Dict[str, Any]] = Field(
        None,
        description="Full NGRS input JSON (wrapped format). Should match schema v0.95."
    )
    
    priority: Optional[int] = Field(
        0,
        ge=0,
        le=10,
        description="Job priority (0-10, higher = more important). Default: 0"
    )
    
    ttl_seconds: Optional[int] = Field(
        None,
        ge=60,
        le=86400,
        description="Time-to-live for result in seconds (60-86400). Default: 3600 (1 hour)"
    )
    
    webhook_url: Optional[str] = Field(
        None,
        description="Optional webhook URL to POST job completion status. Will receive JobStatusResponse payload."
    )
    
    model_config = ConfigDict(extra='allow')


class AsyncJobResponse(BaseModel):
    """Response from POST /solve/async endpoint."""
    
    job_id: str = Field(..., description="Unique job UUID for tracking")
    status: str = Field(..., description="Initial status (typically 'queued')")
    created_at: str = Field(..., description="ISO 8601 timestamp")
    message: str = Field(default="Job submitted successfully")
    feasibility_check: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional pre-flight feasibility analysis with warnings and recommendations"
    )
    
    model_config = ConfigDict(extra='allow')


class JobStatusResponse(BaseModel):
    """Response from GET /solve/async/{job_id} endpoint."""
    
    job_id: str = Field(..., description="Job UUID")
    status: str = Field(
        ...,
        description="Current status: queued, validating, in_progress, completed, failed, expired"
    )
    created_at: str = Field(..., description="ISO 8601 timestamp of job creation")
    started_at: Optional[str] = Field(None, description="ISO 8601 timestamp when processing started")
    completed_at: Optional[str] = Field(None, description="ISO 8601 timestamp when processing finished")
    error_message: Optional[str] = Field(None, description="Error message if status is 'failed'")
    result_available: bool = Field(
        default=False,
        description="True if result can be downloaded via /solve/async/{job_id}/result"
    )
    result_size_bytes: Optional[int] = Field(None, description="Size of result JSON in bytes")
    
    model_config = ConfigDict(extra='allow')


class AsyncStatsResponse(BaseModel):
    """Response from GET /solve/async/stats endpoint."""
    
    total_jobs: int = Field(..., description="Total jobs created (lifetime)")
    active_jobs: int = Field(..., description="Jobs currently in system")
    queue_length: int = Field(..., description="Jobs waiting in queue")
    results_cached: int = Field(..., description="Results currently cached")
    status_breakdown: Dict[str, int] = Field(..., description="Jobs by status")
    ttl_seconds: int = Field(..., description="Result TTL in seconds")
    workers: int = Field(..., description="Number of active workers")
    redis_connected: bool = Field(..., description="Redis connection status")
    jobs: Optional[List[Dict[str, Any]]] = Field(None, description="Detailed job list (when details=true)")
    
    model_config = ConfigDict(extra='allow')


class WebhookPayload(BaseModel):
    """Payload posted to webhook URL when job completes."""
    
    job_id: str = Field(..., description="Job UUID")
    status: str = Field(..., description="Final status: completed or failed")
    created_at: str = Field(..., description="ISO 8601 timestamp of job creation")
    started_at: Optional[str] = Field(None, description="ISO 8601 timestamp when processing started")
    completed_at: str = Field(..., description="ISO 8601 timestamp when processing finished")
    duration_seconds: Optional[float] = Field(None, description="Total processing time in seconds")
    error_message: Optional[str] = Field(None, description="Error message if status is 'failed'")
    result_url: Optional[str] = Field(None, description="URL to retrieve full result (if completed successfully)")
    result_size_bytes: Optional[int] = Field(None, description="Size of result JSON in bytes")
    
    model_config = ConfigDict(extra='allow')


# ============================================================================
# Incremental Solve Models (v0.80)
# ============================================================================

class TemporalWindow(BaseModel):
    """Temporal window for incremental solving."""
    
    cutoffDate: str = Field(
        ..., 
        description="Lock all assignments before this date (YYYY-MM-DD). Must be < solveFromDate."
    )
    solveFromDate: str = Field(
        ..., 
        description="Start solving from this date onwards (YYYY-MM-DD). Must be > cutoffDate."
    )
    solveToDate: str = Field(
        ..., 
        description="End of planning horizon (YYYY-MM-DD). Must be >= solveFromDate."
    )


class NewJoiner(BaseModel):
    """New employee joining mid-month."""
    
    employee: Dict[str, Any] = Field(
        ..., 
        description="Full employee object matching input schema"
    )
    availableFrom: str = Field(
        ..., 
        description="Date employee can start working (YYYY-MM-DD)"
    )


class NotAvailableEmployee(BaseModel):
    """Employee who departed or resigned."""
    
    employeeId: str = Field(..., description="Employee ID")
    notAvailableFrom: str = Field(
        ..., 
        description="Date from which employee is no longer available (YYYY-MM-DD). "
                    "All assignments from this date onwards will be unassigned."
    )


class LongLeave(BaseModel):
    """Employee on long leave."""
    
    employeeId: str = Field(..., description="Employee ID")
    leaveFrom: str = Field(..., description="Leave start date (YYYY-MM-DD)")
    leaveTo: str = Field(..., description="Leave end date (YYYY-MM-DD), inclusive")


class EmployeeChanges(BaseModel):
    """Changes to employee availability for incremental solve."""
    
    newJoiners: Optional[List[NewJoiner]] = Field(
        default_factory=list,
        description="New employees joining (delta only)"
    )
    notAvailableFrom: Optional[List[NotAvailableEmployee]] = Field(
        default_factory=list,
        description="Employees who departed/resigned"
    )
    longLeave: Optional[List[LongLeave]] = Field(
        default_factory=list,
        description="Employees on temporary leave"
    )


class AssignmentAuditInfo(BaseModel):
    """Audit information for assignment traceability."""
    
    solverRunId: str = Field(..., description="Solver run ID that created this assignment")
    source: str = Field(
        ..., 
        description="Assignment source: 'locked' (from previous solve) or 'incremental' (from this solve)"
    )
    timestamp: str = Field(..., description="ISO 8601 timestamp when assignment was created/locked")
    inputHash: Optional[str] = Field(None, description="Hash of input that generated this assignment")
    previousJobId: Optional[str] = Field(None, description="Job ID of previous solve (if source=locked)")


class IncrementalSolveRequest(BaseModel):
    """Request payload for POST /solve/incremental endpoint."""
    
    schemaVersion: str = Field(
        "0.80", 
        description="Schema version for incremental solve"
    )
    planningReference: str = Field(
        ..., 
        description="Planning reference identifier"
    )
    
    temporalWindow: TemporalWindow = Field(
        ..., 
        description="Defines which dates to lock vs solve"
    )
    
    previousOutput: Dict[str, Any] = Field(
        ..., 
        description="Full previous solver output JSON (must include assignments, solverRun, score)"
    )
    
    employeeChanges: EmployeeChanges = Field(
        ..., 
        description="Changes to employee pool: new joiners, departures, long leave"
    )
    
    demandItems: List[Dict[str, Any]] = Field(
        ..., 
        description="Demand items (same as original solve)"
    )
    
    planningHorizon: Dict[str, Any] = Field(
        ..., 
        description="Planning horizon (must match previous solve)"
    )
    
    solverConfig: Optional[Dict[str, Any]] = Field(
        None,
        description="Solver configuration overrides"
    )
    
    model_config = ConfigDict(extra='allow')


# ============================================================================
# Empty Slots Solver Models (v0.96)
# ============================================================================

class EmptySlot(BaseModel):
    """Definition of an empty/unassigned slot to fill."""
    
    date: str = Field(..., description="Slot date (YYYY-MM-DD)")
    shiftCode: str = Field(..., description="Shift code (D/N/E/O)")
    requirementId: str = Field(..., description="Requirement ID this slot belongs to")
    slotId: Optional[str] = Field(None, description="Unique slot identifier")
    reason: Optional[str] = Field(None, description="Why slot is empty: UNASSIGNED, DEPARTED, LEAVE")
    demandId: Optional[str] = Field(None, description="Demand item ID")
    startTime: str = Field(..., description="Shift start time (HH:MM:SS)")
    endTime: str = Field(..., description="Shift end time (HH:MM:SS)")
    hours: Dict[str, float] = Field(..., description="Hour breakdown: gross, lunch, normal, ot")


class EmployeeAvailability(BaseModel):
    """Date-specific availability for an employee."""
    
    date: str = Field(..., description="Date (YYYY-MM-DD)")
    available: bool = Field(..., description="Is employee available on this date?")


class ExistingEmployeeWithAvailability(BaseModel):
    """Existing employee with availability tracking for empty slots solving."""
    
    employeeId: str = Field(..., description="Employee ID")
    
    availableHours: Dict[str, float] = Field(
        ...,
        description="Remaining hours capacity: {weekly: float, monthly: float}"
    )
    
    availableDays: Dict[str, int] = Field(
        ...,
        description="Remaining days capacity: {consecutive: int, total: int}"
    )
    
    currentState: Dict[str, Any] = Field(
        ...,
        description="Current rotation state: {consecutiveDaysWorked, lastWorkDate, rotationOffset, patternDay}"
    )
    
    availability: Optional[List[EmployeeAvailability]] = Field(
        None,
        description="Optional date-specific availability list"
    )


class FillSlotsTemporalWindow(BaseModel):
    """Temporal window for fill slots solving."""
    
    cutoffDate: str = Field(
        ...,
        description="Last date with locked assignments (YYYY-MM-DD)"
    )
    solveFromDate: str = Field(
        ...,
        description="First date to solve (YYYY-MM-DD)"
    )
    solveToDate: str = Field(
        ...,
        description="Last date to solve (YYYY-MM-DD)"
    )
    lengthDays: Optional[int] = Field(
        None,
        description="Number of days in solve period (calculated if omitted)"
    )


class FillSlotsWithAvailabilityRequest(BaseModel):
    """Request payload for POST /solve/fill-slots-mixed endpoint (Option 3)."""
    
    schemaVersion: str = Field("0.96", description="Schema version")
    mode: str = Field("fillEmptySlotsWithAvailability", description="Solve mode")
    planningReference: str = Field(..., description="Planning reference identifier")
    
    temporalWindow: FillSlotsTemporalWindow = Field(
        ...,
        description="Temporal window defining solve period"
    )
    
    emptySlots: List[EmptySlot] = Field(
        ...,
        description="List of empty/unassigned slots to fill"
    )
    
    existingEmployees: List[ExistingEmployeeWithAvailability] = Field(
        ...,
        description="Existing employees with availability tracking"
    )
    
    newJoiners: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list,
        description="Optional new employees to add (full employee objects)"
    )
    
    requirements: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list,
        description="Optional requirement definitions for pattern validation"
    )
    
    solverConfig: Optional[Dict[str, Any]] = Field(
        None,
        description="Solver configuration overrides"
    )
    
    model_config = ConfigDict(extra='allow')
