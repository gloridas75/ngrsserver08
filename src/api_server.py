"""
NGRS Solver FastAPI Application.

Main entry point for the REST API.
Exposes endpoints for solving scheduling problems.

Run with:
    uvicorn src.api_server:app --reload --port 8080

Or production:
    uvicorn src.api_server:app --host 0.0.0.0 --port 8080 --workers 2
"""

import os
import sys
import json
import uuid
import time
import logging
import pathlib
from typing import Optional
from datetime import datetime

# Setup path
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, File, UploadFile, Query, HTTPException, Request, Header
from fastapi.responses import ORJSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from context.engine.data_loader import load_input
from context.engine.solver_engine import solve
from context.engine.config_optimizer_v3 import optimize_all_requirements, format_output_config
from context.engine.config_optimizer_v3 import optimize_multiple_requirements
from src.models import (
    SolveRequest, SolveResponse, HealthResponse, 
    Score, SolverRunMetadata, Meta, Violation,
    AsyncJobRequest, AsyncJobResponse, JobStatusResponse, AsyncStatsResponse,
    IncrementalSolveRequest, FillSlotsWithAvailabilityRequest, EmptySlotsRequest,
    ValidateAssignmentRequest, ValidateAssignmentResponse
)
from src.output_builder import build_output
from src.redis_job_manager import RedisJobManager
from src.redis_worker import start_worker_pool
from src.feasibility_checker import quick_feasibility_check
from src.incremental_solver import solve_incremental, IncrementalSolverError
from src.fill_slots_solver import solve_fill_slots, FillSlotsSolverError
from src.offset_manager import ensure_staggered_offsets
from src.resource_monitor import (
    pre_solve_safety_check,
    apply_resource_limits_to_solver,
    estimate_problem_complexity
)
from src.input_validator import validate_input, ValidationResult

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ngrs.api")

# ============================================================================
# MIDDLEWARE: REQUEST ID TRACKING
# ============================================================================

class RequestIdMiddleware(BaseHTTPMiddleware):
    """Add request ID to all requests for tracing."""
    
    async def dispatch(self, request: Request, call_next):
        # Use incoming X-Request-ID or generate new UUID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Process request
        response = await call_next(request)
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        return response

# ============================================================================
# ADMIN API KEY
# ============================================================================

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "change-me-in-production")

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="NGRS Solver API",
    description="REST API for NGRS Shift Scheduling Solver with ICPMP v2.0 Configuration Optimizer",
    version="0.96.0",
    docs_url="/docs",
    openapi_url="/openapi.json"
)

# Add middleware
app.add_middleware(RequestIdMiddleware)

# Add CORS
cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ============================================================================
# ASYNC MODE: REDIS JOB MANAGER & WORKERS
# ============================================================================

# Initialize Redis-based job manager
NUM_WORKERS = int(os.getenv("SOLVER_WORKERS", "2"))
job_manager = RedisJobManager(
    result_ttl_seconds=int(os.getenv("RESULT_TTL_SECONDS", "3600")),
    key_prefix=os.getenv("REDIS_KEY_PREFIX", "ngrs")
)

# Start worker pool on startup (can be disabled via env var)
worker_processes = []
worker_stop_event = None
START_WORKERS = os.getenv("START_WORKERS", "true").lower() in ("true", "1", "yes")

@app.on_event("startup")
async def startup_event():
    """Initialize worker pool on API startup"""
    global worker_processes, worker_stop_event
    
    if START_WORKERS:
        logger.info(f"Starting {NUM_WORKERS} solver workers with Redis...")
        worker_processes, worker_stop_event = start_worker_pool(
            num_workers=NUM_WORKERS,
            ttl_seconds=int(os.getenv("RESULT_TTL_SECONDS", "3600"))
        )
        logger.info(f"Async mode enabled with {NUM_WORKERS} workers (Redis-backed)")
    else:
        logger.info("Worker startup disabled (START_WORKERS=false). Run workers separately.")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup workers on shutdown"""
    global worker_processes, worker_stop_event
    
    if START_WORKERS and worker_processes:
        logger.info("Shutting down solver workers...")
        from src.redis_worker import cleanup_worker_pool
        cleanup_worker_pool(worker_processes, worker_stop_event)
    else:
        logger.info("No workers to shutdown (workers run separately)")


def restart_workers():
    """Restart worker pool"""
    global worker_processes, worker_stop_event
    
    # Stop existing workers
    if worker_stop_event and worker_processes:
        logger.info("Stopping existing workers...")
        from src.redis_worker import cleanup_worker_pool
        cleanup_worker_pool(worker_processes, worker_stop_event)
        worker_processes.clear()
    
    # Start new workers
    logger.info(f"Starting {NUM_WORKERS} new workers...")
    new_processes, new_stop_event = start_worker_pool(
        num_workers=NUM_WORKERS,
        ttl_seconds=int(os.getenv("RESULT_TTL_SECONDS", "3600"))
    )
    worker_processes = new_processes
    worker_stop_event = new_stop_event
    logger.info(f"Worker pool restarted with {len(worker_processes)} workers")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def load_json_from_upload(file: UploadFile) -> dict:
    """Load and parse JSON from uploaded file."""
    try:
        raw = await file.read()
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Unable to parse uploaded file as JSON: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Error reading uploaded file: {str(e)}"
        )


def get_input_json(request_obj: Optional[SolveRequest], uploaded_file_json: Optional[dict], raw_body_json: Optional[dict] = None) -> tuple:
    """
    Select input JSON from body or file.
    
    Handles three input formats:
    1. {"input_json": {...}} - wrapped format (in raw_body_json)
    2. {"schemaVersion": "0.43", ...} - raw NGRS input (top-level in raw_body_json)
    3. Uploaded file
    
    Returns:
        (input_json, warnings_list)
    """
    warnings = []
    input_json = None
    source = None
    
    # Priority 1: Check if body has explicit input_json wrapper
    if request_obj and request_obj.input_json:
        input_json = request_obj.input_json
        source = "body (wrapped)"
    
    # Priority 2: Check if raw body has input_json wrapper
    elif raw_body_json and "input_json" in raw_body_json and isinstance(raw_body_json.get("input_json"), dict):
        input_json = raw_body_json["input_json"]
        source = "body (wrapped)"
    
    # Priority 3: Check if raw body is NGRS input (has schemaVersion or planningHorizon)
    elif raw_body_json and ("schemaVersion" in raw_body_json or "planningHorizon" in raw_body_json):
        input_json = raw_body_json
        source = "body (raw NGRS input)"
    
    # Priority 4: Use uploaded file
    elif uploaded_file_json:
        input_json = uploaded_file_json
        source = "uploaded file"
    
    if input_json is None:
        raise HTTPException(
            status_code=400,
            detail="Provide either input_json in request body, raw NGRS input, or upload a JSON file."
        )
    
    # Warn if multiple inputs provided
    inputs_count = 0
    if request_obj and request_obj.input_json is not None:
        inputs_count += 1
    if raw_body_json is not None:
        inputs_count += 1
    if uploaded_file_json is not None:
        inputs_count += 1
    
    if inputs_count > 1:
        warnings.append(f"Multiple inputs provided; used {source}.")
    
    return input_json, warnings


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(status="ok")


@app.post("/validate")
async def validate_input_endpoint(request: Request):
    """
    Validate solver input without running the solver.
    
    Performs comprehensive validation including:
    - Schema structure and required fields
    - Business logic (shift definitions, work patterns, etc.)
    - Scheme consistency across requirements and employees
    - Feasibility pre-checks (matching employees for requirements)
    
    Returns:
    - 200: Validation complete (check "valid" field in response)
    - 400: Invalid JSON format
    
    Response includes:
    - valid: boolean indicating if input is valid
    - errors: List of blocking errors (prevent solver execution)
    - warnings: List of warnings (informational, don't block execution)
    
    Each error/warning includes:
    - field: JSON path to the problematic field
    - code: Machine-readable error code
    - message: Human-readable description
    - severity: "error" or "warning"
    """
    try:
        raw_body = await request.body()
        input_json = json.loads(raw_body)
        
        # Run validation
        validation_result = validate_input(input_json)
        
        # Build response
        response = validation_result.to_dict()
        
        # Add summary
        response["summary"] = {
            "total_errors": len(validation_result.errors),
            "total_warnings": len(validation_result.warnings),
            "can_submit": validation_result.is_valid
        }
        
        return ORJSONResponse(
            status_code=200,
            content=response
        )
        
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Validation error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Validation failed: {str(e)}"
        )


@app.get("/version")
async def get_version():
    """Get API and solver version information."""
    return {
        "apiVersion": "0.96.0",
        "solverVersion": "optSolve-py-0.96.0-icpmp-v2",
        "schemaVersion": "0.96",
        "icpmpVersion": "2.0",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/validate/assignment", response_model=ValidateAssignmentResponse)
async def validate_assignment(
    request: Request,
    payload: ValidateAssignmentRequest
):
    """
    Validate Employee Assignment - Phase 1 (Employee-Specific Hard Constraints)
    
    Validates whether an employee can be assigned to candidate slot(s) without
    violating hard constraints. Returns detailed violation information.
    
    **Supported Constraints (Employee-Specific Only):**
    - C1: Daily Hours Cap (14h/13h/9h by scheme)
    - C2: Weekly Hours Cap (44-52h normal hours)
    - C3: Consecutive Working Days (max days without break)
    - C4: Rest Period Between Shifts (minimum 12h rest)
    - C17: Monthly OT Cap (72h maximum overtime)
    
    **NOT Supported (require team/global context):**
    - C9: Team Assignment
    - C14: Scheme Quotas
    - S7: Team Cohesion
    
    **Request Body:**
    ```json
    {
      "employee": {
        "employeeId": "EMP001",
        "name": "John Doe",
        "rank": "SO",
        "gender": "M",
        "scheme": "A",
        "productTypes": ["Guarding"],
        "workPattern": "DDNNOOO",
        "rotationOffset": 2
      },
      "existingAssignments": [
        {
          "startDateTime": "2026-01-13T07:00:00+08:00",
          "endDateTime": "2026-01-13T15:00:00+08:00",
          "shiftType": "DAY",
          "hours": 8.0,
          "date": "2026-01-13"
        }
      ],
      "candidateSlots": [
        {
          "slotId": "slot_unassigned_456",
          "startDateTime": "2026-01-15T07:00:00+08:00",
          "endDateTime": "2026-01-15T15:00:00+08:00",
          "shiftType": "DAY",
          "productType": "Guarding",
          "rank": "SO",
          "scheme": "A"
        }
      ],
      "constraintList": [
        {"constraintId": "C1", "enabled": true},
        {"constraintId": "C2", "enabled": true}
      ]
    }
    ```
    
    **Response:**
    ```json
    {
      "status": "success",
      "validationResults": [
        {
          "slotId": "slot_456",
          "isFeasible": true,
          "violations": [],
          "recommendation": "feasible"
        }
      ],
      "employeeId": "EMP001",
      "timestamp": "2026-01-14T10:30:00+08:00",
      "processingTimeMs": 12.5
    }
    ```
    
    **Returns:**
    - 200: Validation complete (check isFeasible for each slot)
    - 400: Invalid request (missing data, validation errors)
    - 422: Schema validation error
    - 500: Internal error
    
    **Performance:** Target <100ms for single slot, ~50-200ms for multiple slots
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    
    logger.info(f"[{request_id}] Assignment validation request received")
    logger.info(f"[{request_id}] Employee: {payload.employee.employeeId}, "
                f"Existing assignments: {len(payload.existingAssignments)}, "
                f"Candidate slots: {len(payload.candidateSlots)}")
    
    try:
        # Import validator
        from src.assignment_validator import AssignmentValidator
        
        # Create validator instance
        validator = AssignmentValidator()
        
        # Run validation
        response = validator.validate(payload)
        
        # Log results
        feasible_count = sum(1 for r in response.validationResults if r.isFeasible)
        logger.info(f"[{request_id}] Validation complete: "
                    f"{feasible_count}/{len(response.validationResults)} slots feasible, "
                    f"Processing time: {response.processingTimeMs}ms")
        
        return response
        
    except Exception as e:
        logger.error(
            f"[{request_id}] Assignment validation error: {str(e)}",
            exc_info=True
        )
        
        # Determine error type for appropriate HTTP status
        if "validation" in str(e).lower() or "missing" in str(e).lower():
            status_code = 400
        else:
            status_code = 500
        
        raise HTTPException(status_code=status_code, detail=str(e))


@app.get("/metrics")
async def get_metrics():
    """
    Get server resource metrics and capacity.
    
    Returns:
        System metrics including memory, CPU, and problem size limits
    """
    import psutil
    
    memory = psutil.virtual_memory()
    cpu_count = psutil.cpu_count(logical=True)
    total_memory_gb = memory.total / (1024 ** 3)
    
    # Determine capacity tier
    if total_memory_gb <= 4.5:
        tier = "small"
        max_variables = 50_000
    elif total_memory_gb <= 8.5:
        tier = "medium"
        max_variables = 200_000
    else:
        tier = "large"
        max_variables = 1_000_000
    
    return {
        "timestamp": datetime.now().isoformat(),
        "system": {
            "cpu_count": cpu_count,
            "memory_total_gb": round(total_memory_gb, 2),
            "memory_available_gb": round(memory.available / (1024 ** 3), 2),
            "memory_percent_used": memory.percent,
            "cpu_percent": psutil.cpu_percent(interval=0.5)
        },
        "capacity": {
            "tier": tier,
            "max_variables": max_variables,
            "max_employees_estimate": int(max_variables / 500),  # Rough estimate
            "max_time_limit_seconds": 120
        },
        "limits": {
            "max_memory_percent": float(os.getenv("MAX_SOLVER_MEMORY_PERCENT", "70")),
            "max_memory_gb": float(os.getenv("MAX_SOLVER_MEMORY_GB", "2.5")),
            "max_cpsat_workers": int(os.getenv("MAX_CPSAT_WORKERS", "2"))
        }
    }


@app.post("/estimate-complexity")
async def estimate_complexity_endpoint(request: Request):
    """
    Estimate problem complexity without solving.
    
    Useful for pre-checking if a problem will fit on current server.
    
    Returns:
        Complexity metrics and safety assessment
    """
    try:
        raw_body = await request.body()
        input_json = json.loads(raw_body)
        
        # Load context (lightweight, doesn't build full model)
        from context.engine.data_loader import load_input
        ctx = load_input(input_json)
        
        # Estimate complexity
        complexity = estimate_problem_complexity(ctx)
        
        # Check if it's safe
        can_solve, error_message, _ = pre_solve_safety_check(ctx)
        
        return {
            "complexity": complexity,
            "safety": {
                "can_solve": can_solve,
                "error": error_message,
                "recommendation": (
                    "Safe to solve" if can_solve
                    else "Problem too large for this server - reduce size or upgrade server"
                )
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error estimating complexity: {str(e)}"
        )


@app.get("/schema")
async def get_schemas():
    """
    Get JSON schemas for input and output validation.
    
    Returns JSON Schema documents (draft-07) for request/response validation.
    """
    import json
    from pathlib import Path
    
    try:
        schema_dir = Path(__file__).parent.parent / "context" / "schemas"
        
        # Load input schema
        input_schema_path = schema_dir / "input_schema_v0.73.json"
        with open(input_schema_path, 'r') as f:
            input_schema = json.load(f)
        
        # Load output schema
        output_schema_path = schema_dir / "output_schema_v0.73.json"
        with open(output_schema_path, 'r') as f:
            output_schema = json.load(f)
        
        return {
            "inputSchema": input_schema,
            "outputSchema": output_schema
        }
    except FileNotFoundError as e:
        return {
            "error": "Schema files not found",
            "message": str(e),
            "inputSchema": {"description": "NGRS input schema (v0.95)"},
            "outputSchema": {"description": "NGRS output schema (v0.95)"}
        }
    except Exception as e:
        return {
            "error": "Error loading schemas",
            "message": str(e)
        }


@app.post("/configure", response_class=ORJSONResponse)
async def configure_endpoint(
    request: Request,
    file: Optional[UploadFile] = File(None),
):
    """
    ICPMP v2.0 Configuration Optimizer: Find optimal work patterns and staffing.

    This endpoint analyzes requirements and suggests:
    1. Optimal work patterns for each requirement (coverage-aware cycle length)
    2. Minimum employee count needed per shift type
    3. Recommended rotation offsets for maximum coverage

    **Enhanced v2.0 Features:**
    - Coverage-aware pattern generation (5-day patterns for Mon-Fri, 7-day for full week)
    - Pattern length validation (eliminates mismatches)
    - Integration with rotation preprocessor for intelligent offsets
    - 24% more efficient employee allocation vs v1

    Input Schema (required):
    - JSON body: {
        "requirements": [
            {
                "requirementId": "REQ_52_1",
                "requirementName": "Weekday APO Coverage",
                "coverageDays": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                "shiftTypes": ["D"],
                "headcountByShift": {"D": 10},
                "strictAdherence": true
            }
        ],
        "constraints": {...},
        "planningHorizon": {...},
        "shiftDefinitions": {  // Optional
            "D": {"grossHours": 12.0, "lunchBreak": 1.0},
            "N": {"grossHours": 12.0, "lunchBreak": 1.0}
        }
      }
    - Uploaded file: multipart/form-data with file field (same schema)
    
    Note: If shiftDefinitions is not provided, default hours are used (11.0 = 12 gross - 1 lunch).

    Returns:
    - 200: Optimized configuration with per-shift recommendations
    - 400: Invalid input
    - 422: Malformed JSON
    - 500: Internal server error
    """
    
    request_id = request.state.request_id
    start_time = time.perf_counter()
    
    try:
        # ====== PARSE INPUT ======
        raw_body_json = None
        if request.headers.get("content-type", "").startswith("application/json"):
            try:
                raw_body = await request.body()
                if raw_body:
                    raw_body_json = json.loads(raw_body)
            except Exception:
                raw_body_json = None
        
        uploaded_json = None
        if file:
            uploaded_json = await load_json_from_upload(file)
        
        # Select input
        config_input = uploaded_json if uploaded_json else raw_body_json
        
        if config_input is None:
            raise HTTPException(
                status_code=400,
                detail="Provide either JSON body or upload a JSON file with requirements, constraints, and planningHorizon."
            )
        
        # Validate required fields
        if "requirements" not in config_input:
            raise HTTPException(
                status_code=400,
                detail="Missing 'requirements' field in input."
            )
        if "planningHorizon" not in config_input:
            raise HTTPException(
                status_code=400,
                detail="Missing 'planningHorizon' field in input."
            )

        # Validate each requirement for headcountPerShift
        for req in config_input["requirements"]:
            if "shiftTypes" not in req:
                raise HTTPException(
                    status_code=400,
                    detail=f"Requirement {req.get('id','')} missing 'shiftTypes'."
                )
            if "headcountPerShift" not in req:
                raise HTTPException(
                    status_code=400,
                    detail=f"Requirement {req.get('id','')} missing 'headcountPerShift'."
                )
            if not isinstance(req["headcountPerShift"], dict) or not req["headcountPerShift"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Requirement {req.get('id','')} 'headcountPerShift' must be a non-empty dict."
                )

        # Use default constraints if not provided
        constraints = config_input.get("constraints", {})
        
        # Extract optional shift definitions
        shift_definitions = config_input.get("shiftDefinitions", None)

        # ====== OPTIMIZE ======
        optimized_result = optimize_all_requirements(
            requirements=config_input["requirements"],
            constraints=constraints,
            planning_horizon=config_input["planningHorizon"],
            shift_definitions=shift_definitions
        )

        # ====== FORMAT OUTPUT ======
        output_config = format_output_config(
            optimized_result,
            config_input  # Pass full config, not just requirements
        )
        
        # ====== ENRICH RESPONSE ======
        output_config["meta"] = {
            "requestId": request_id,
            "timestamp": datetime.now().isoformat(),
            "processingTimeMs": int((time.perf_counter() - start_time) * 1000)
        }
        
        # ====== LOG ======
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.info(
            "configure requestId=%s totalRequirements=%s totalEmployees=%s durMs=%s",
            request_id,
            output_config["summary"]["totalRequirements"],
            output_config["summary"]["totalEmployees"],
            elapsed_ms
        )
        
        return output_config
    
    except HTTPException:
        raise
    
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        error_msg = f"Configuration optimization error: {str(e)}"
        logger.error(
            "configure requestId=%s error=%s durMs=%s",
            request_id,
            str(e),
            elapsed_ms,
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=error_msg)


@app.post("/icpmp", response_class=ORJSONResponse)
async def icpmp_calculate(request: Request):
    """
    Simple ICPMP Calculator: Calculate employees needed for a specific work pattern.
    
    This endpoint performs a straightforward calculation without optimization.
    It tells you how many employees are needed to maintain the specified
    headcount with the given work pattern.
    
    Input Schema:
    {
        "headcount": 10,
        "workPattern": ["D", "D", "N", "N", "O", "O"]
    }
    
    Returns:
    {
        "employeesNeeded": 30,
        "cycleLength": 6,
        "workDays": 4,
        "uniqueShiftCodes": 2,
        "slotsPerWorkDay": 20,
        "formula": "2 shifts × 10 headcount × (6 cycle / 4 work days) = 30"
    }
    """
    request_id = request.state.request_id
    start_time = time.perf_counter()
    
    try:
        # Parse input
        raw_body = await request.body()
        if not raw_body:
            raise HTTPException(status_code=400, detail="Empty request body")
        
        data = json.loads(raw_body)
        headcount = data.get('headcount')
        work_pattern = data.get('workPattern')
        
        if not headcount or not work_pattern:
            raise HTTPException(
                status_code=400,
                detail="Missing required fields: 'headcount' and 'workPattern'"
            )
        
        if not isinstance(headcount, int) or headcount < 1:
            raise HTTPException(status_code=400, detail="headcount must be a positive integer")
        
        if not isinstance(work_pattern, list) or len(work_pattern) == 0:
            raise HTTPException(status_code=400, detail="workPattern must be a non-empty array")
        
        # Calculate
        cycle_length = len(work_pattern)
        work_days = sum(1 for shift in work_pattern if shift != 'O')
        
        if work_days == 0:
            raise HTTPException(status_code=400, detail="workPattern must contain at least one work day (non-'O' shift)")
        
        # Get unique shift codes (excluding 'O')
        unique_shifts = set(shift for shift in work_pattern if shift != 'O')
        unique_shift_count = len(unique_shifts)
        
        # Calculate slots per work day
        slots_per_work_day = headcount * unique_shift_count
        
        # Calculate employees needed
        # Formula: unique_shifts * headcount * (cycle_length / work_days)
        employees_needed = int(unique_shift_count * headcount * (cycle_length / work_days))
        
        # Build formula string
        formula = f"{unique_shift_count} shifts × {headcount} headcount × ({cycle_length} cycle / {work_days} work days) = {employees_needed}"
        
        result = {
            "employeesNeeded": employees_needed,
            "cycleLength": cycle_length,
            "workDays": work_days,
            "uniqueShiftCodes": unique_shift_count,
            "shiftTypes": list(unique_shifts),
            "slotsPerWorkDay": slots_per_work_day,
            "formula": formula,
            "workPattern": work_pattern
        }
        
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.info(
            "icpmp requestId=%s headcount=%d pattern=%s employees=%d durMs=%d",
            request_id,
            headcount,
            '-'.join(work_pattern),
            employees_needed,
            elapsed_ms
        )
        
        return result
        
    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=422, detail=f"Invalid JSON: {str(e)}")
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        error_msg = f"ICPMP calculation error: {str(e)}"
        logger.error(
            "icpmp requestId=%s error=%s durMs=%s",
            request_id,
            str(e),
            elapsed_ms,
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=error_msg)


@app.post("/icpmp/v3", response_class=ORJSONResponse)
async def icpmp_v3_calculate(request: Request):
    """
    ICPMP v3.0: Optimal Employee Calculator with U-Slot Injection
    
    Calculates the mathematically MINIMAL number of employees needed
    using strategic "U" (unassigned) slot injection. All employees follow
    strict patterns with U-slots injected when coverage would exceed headcount.
    
    Key Features:
    - Proven optimal employee count (try-minimal-first algorithm)
    - All employees on strict patterns (no flexible category)
    - U-slots for predictable scheduling
    - Handles public holidays and coverage day filtering
    
    Input Schema (solver v0.70 subset):
    {
        "fixedRotationOffset": true,
        "planningHorizon": {
            "startDate": "2026-01-01",
            "endDate": "2026-01-31"
        },
        "publicHolidays": ["2026-01-01"],
        "coverageDays": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
        "demandItems": [
            {
                "demandItemId": "48",
                "requirements": [
                    {
                        "requirementId": "48_1",
                        "workPattern": ["D","D","D","D","O","O"],
                        "headcount": 5
                    }
                ]
            }
        ]
    }
    
    Returns (per requirement):
    {
        "requirementId": "48_1",
        "configuration": {
            "employeesRequired": 6,
            "optimality": "PROVEN_MINIMAL",
            "algorithm": "GREEDY_INCREMENTAL",
            "lowerBound": 5,
            "attemptsRequired": 2,
            "offsetDistribution": {"0": 1, "1": 1, "2": 1, "3": 1, "4": 1, "5": 1}
        },
        "employeePatterns": [
            {
                "employeeNumber": 1,
                "rotationOffset": 0,
                "pattern": ["D","D","D","D","O","O",...],
                "workDays": 23,
                "uSlots": 0,
                "restDays": 8,
                "utilization": 100.0
            }
        ],
        "coverage": {
            "achievedRate": 100.0,
            "totalWorkDays": 155,
            "totalUSlots": 35,
            "dailyCoverageDetails": {...}
        }
    }
    """
    request_id = request.state.request_id
    start_time = time.perf_counter()
    
    try:
        # Parse input
        raw_body = await request.body()
        if not raw_body:
            raise HTTPException(status_code=400, detail="Empty request body")
        
        data = json.loads(raw_body)
        
        # Validate required fields
        planning_horizon = data.get('planningHorizon')
        demand_items = data.get('demandItems')
        
        if not planning_horizon:
            raise HTTPException(status_code=400, detail="Missing required field: 'planningHorizon'")
        
        if not planning_horizon.get('startDate') or not planning_horizon.get('endDate'):
            raise HTTPException(
                status_code=400,
                detail="planningHorizon must contain 'startDate' and 'endDate'"
            )
        
        if not demand_items or not isinstance(demand_items, list):
            raise HTTPException(status_code=400, detail="Missing or invalid 'demandItems' array")
        
        # Extract optional parameters
        public_holidays = data.get('publicHolidays', [])
        coverage_days = data.get('coverageDays')  # Optional - defaults to all days
        
        # Flatten requirements from all demand items
        all_requirements = []
        for demand_item in demand_items:
            demand_item_id = demand_item.get('demandItemId', 'unknown')
            requirements = demand_item.get('requirements', [])
            
            for req in requirements:
                # Add demandItemId context to requirement
                req_with_context = req.copy()
                req_with_context['demandItemId'] = demand_item_id
                
                # Generate requirementId if not present
                if 'requirementId' not in req_with_context:
                    req_with_context['requirementId'] = f"{demand_item_id}_{len(all_requirements) + 1}"
                
                all_requirements.append(req_with_context)
        
        if not all_requirements:
            raise HTTPException(
                status_code=400,
                detail="No requirements found in demandItems"
            )
        
        logger.info(
            "icpmp_v3 requestId=%s requirements=%d horizon=%s->%s",
            request_id,
            len(all_requirements),
            planning_horizon['startDate'],
            planning_horizon['endDate']
        )
        
        # Calculate optimal employees for each requirement
        results = optimize_multiple_requirements(
            requirements=all_requirements,
            planning_horizon=planning_horizon,
            public_holidays=public_holidays,
            coverage_days=coverage_days
        )
        
        # Build response
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        
        response = {
            "version": "3.0",
            "algorithm": "U_SLOT_INJECTION",
            "optimality": "PROVEN_MINIMAL",
            "planningHorizon": planning_horizon,
            "publicHolidays": public_holidays,
            "coverageDays": coverage_days,
            "results": results,
            "summary": {
                "totalRequirements": len(all_requirements),
                "successfulCalculations": sum(1 for r in results if 'error' not in r),
                "failedCalculations": sum(1 for r in results if 'error' in r),
                "totalEmployeesRequired": sum(
                    r['configuration']['employeesRequired'] 
                    for r in results if 'configuration' in r
                ),
                "computationTimeMs": elapsed_ms
            }
        }
        
        logger.info(
            "icpmp_v3 requestId=%s success=%d failed=%d totalEmployees=%d durMs=%d",
            request_id,
            response['summary']['successfulCalculations'],
            response['summary']['failedCalculations'],
            response['summary']['totalEmployeesRequired'],
            elapsed_ms
        )
        
        return response
        
    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=422, detail=f"Invalid JSON: {str(e)}")
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        error_msg = f"ICPMP v3.0 calculation error: {str(e)}"
        logger.error(
            "icpmp_v3 requestId=%s error=%s durMs=%s",
            request_id,
            str(e),
            elapsed_ms,
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=error_msg)


# ============================================================================
# ASYNC ENDPOINTS
# ============================================================================

@app.post("/solve/async", response_model=AsyncJobResponse)
async def solve_async(
    request: Request,
    payload: Optional[AsyncJobRequest] = None
):
    """
    Submit solver job for asynchronous processing.
    
    Returns immediately with job UUID for tracking.
    
    Accepts input via:
    - Wrapped format: {"input_json": {...NGRS input...}, "priority": 5, "webhook_url": "https://your-api.com/webhook"}
    - Raw format: {...NGRS input directly...} (without input_json wrapper)
    
    Query parameters (optional):
    - priority: Job priority 0-10 (default 0)
    - ttl_seconds: Result TTL 60-86400 seconds (default 3600)
    - webhook_url: Optional URL to receive job completion notification
    
    Feasibility Pre-Check (Automatic):
    - Fast mathematical analysis (< 100ms) before queuing job
    - Estimates minimum employee count needed using coverage formulas
    - Checks role/rank/gender/scheme matching
    - Returns warnings if obvious infeasibility detected
    - Job is queued regardless - check helps set expectations
    - Response includes "feasibility_check" field with:
      * likely_feasible: bool
      * confidence: "high" | "medium" | "low"
      * warnings: List of issues detected
      * recommendations: Suggested fixes
      * analysis: Detailed breakdown by requirement
    
    Webhook Notification:
    - When job completes (success or failure), a POST request is sent to webhook_url
    - Payload includes: job_id, status, timestamps, duration, error_message (if failed), result_url
    - Webhook timeout: 10 seconds
    - Job will complete successfully even if webhook fails
    
    Returns:
    - 201: Job created and queued
    - 400: Invalid input or missing required fields
    - 503: Queue full (too many pending jobs)
    """
    request_id = request.state.request_id
    
    try:
        # Parse raw body to support both wrapped and unwrapped formats
        raw_body_json = None
        if request.headers.get("content-type", "").startswith("application/json"):
            try:
                raw_body = await request.body()
                if raw_body:
                    raw_body_json = json.loads(raw_body)
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid JSON in request body: {str(e)}"
                )
        
        # Extract input_json using flexible parsing (wrapped or raw)
        input_json, warnings = get_input_json(
            request_obj=payload,
            uploaded_file_json=None,
            raw_body_json=raw_body_json
        )
        
        # Extract priority and ttl from payload or use defaults
        priority = 0
        ttl_seconds = None
        webhook_url = None
        
        if payload:
            priority = payload.priority or 0
            ttl_seconds = payload.ttl_seconds
            webhook_url = payload.webhook_url
        elif raw_body_json:
            # Check if raw body has these fields (for backward compatibility)
            priority = raw_body_json.get("priority", 0)
            ttl_seconds = raw_body_json.get("ttl_seconds")
            webhook_url = raw_body_json.get("webhook_url")
        
        # ====== INPUT VALIDATION ======
        # Validate input structure and business logic before submission
        validation_result = validate_input(input_json)
        
        if not validation_result.is_valid:
            logger.warning(
                f"async_job_validation_failed requestId={request_id} "
                f"errors={len(validation_result.errors)} "
                f"first_error={validation_result.errors[0].code if validation_result.errors else 'none'}"
            )
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "validation_failed",
                    "message": "Input validation failed. Please fix errors and resubmit.",
                    **validation_result.to_dict()
                }
            )
        
        # Log warnings if any
        if validation_result.warnings:
            logger.info(
                f"async_job_validation_warnings requestId={request_id} "
                f"warnings={len(validation_result.warnings)}"
            )
        
        # NOTE: Rotation offset handling is now done inside solve_problem() in src/solver.py
        # This ensures consistent behavior between API and CLI paths
        
        # Perform quick feasibility check (< 100ms)
        feasibility_result = None
        try:
            feasibility_result = quick_feasibility_check(input_json)
            logger.info(
                f"async_job_feasibility requestId={request_id} likely_feasible={feasibility_result['likely_feasible']} "
                f"confidence={feasibility_result['confidence']} "
                f"employees_provided={feasibility_result['analysis']['employees_provided']} "
                f"employees_required={feasibility_result['analysis']['employees_required_min']}-{feasibility_result['analysis']['employees_required_max']}"
            )
            # DEBUG: Log first requirement details
            if feasibility_result.get('analysis', {}).get('by_requirement'):
                first_req = feasibility_result['analysis']['by_requirement'][0]
                logger.info(f"First requirement fields: {sorted(first_req.keys())}")
        except Exception as check_error:
            # Don't fail job submission if feasibility check fails
            logger.warning(f"Feasibility check failed for requestId={request_id}: {check_error}")
            feasibility_result = None
        
        # Create job with webhook URL
        job_id = job_manager.create_job(input_json, webhook_url=webhook_url)
        
        queue_length = job_manager.get_queue_length()
        logger.info(
            "async_job_created requestId=%s jobId=%s queueLength=%s",
            request_id, job_id, queue_length
        )
        
        return AsyncJobResponse(
            job_id=job_id,
            status="queued",
            created_at=datetime.now().isoformat(),
            message="Job submitted successfully",
            feasibility_check=feasibility_result
        )
        
    except Exception as e:
        logger.error(
            "async_job_error requestId=%s error=%s",
            request_id, str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create job: {str(e)}"
        )


@app.get("/solve/async/stats", response_model=AsyncStatsResponse)
async def get_async_stats(details: bool = Query(False, description="Include detailed job list with UUIDs and timestamps")):
    """
    Get statistics about async job queue and workers.
    
    Query parameters:
    - details: If true, includes list of all jobs with UUIDs and timestamps (default: false)
    
    Returns:
    - 200: Current statistics
    
    Useful for monitoring queue capacity and worker utilization.
    """
    stats = job_manager.get_stats()
    stats["workers"] = NUM_WORKERS
    
    # Add detailed job list if requested
    if details:
        stats["jobs"] = job_manager.get_all_jobs_details()
    
    return AsyncStatsResponse(**stats)


@app.post("/admin/reset")
async def admin_reset(
    x_api_key: str = Header(..., description="Admin API key for authentication")
):
    """
    **ADMIN ONLY**: Complete system reset - flush Redis and restart workers.
    
    Requires admin API key in x-api-key header.
    
    This will:
    - Flush all Redis data (jobs, results, queue)
    - Restart all worker processes
    - Reset job counters and stats
    
    **WARNING**: This will delete all active jobs and results!
    
    Security:
    - Set ADMIN_API_KEY environment variable in production
    - Keep the key secret and rotate regularly
    - Only use when necessary (e.g., after critical errors)
    
    Returns:
    - 200: System reset successful
    - 401: Invalid or missing API key
    - 500: Reset failed
    
    Example:
    ```bash
    curl -X POST https://api.example.com/admin/reset \\
      -H "x-api-key: your-secret-key"
    ```
    """
    # Validate API key
    if x_api_key != ADMIN_API_KEY:
        logger.warning(f"Admin reset attempted with invalid API key")
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    try:
        logger.warning("Admin reset initiated - flushing Redis and restarting workers")
        
        # 1. Flush Redis
        logger.info("Flushing Redis database...")
        job_manager.redis.flushdb()
        logger.info("Redis flushed")
        
        # 2. Restart workers (only if workers are managed by this process)
        if START_WORKERS and worker_processes:
            logger.info("Restarting worker pool...")
            restart_workers()
            logger.info("Workers restarted")
            workers_restarted = True
        else:
            logger.info("Workers run separately - restart manually if needed")
            workers_restarted = False
        
        # 3. Verify system state
        stats = job_manager.get_stats()
        stats["workers"] = NUM_WORKERS
        
        actions = [
            "Redis database flushed (all jobs and results deleted)",
            "System ready for new jobs"
        ]
        
        if workers_restarted:
            actions.insert(1, f"Worker pool restarted ({NUM_WORKERS} workers)")
        else:
            actions.insert(1, "Workers run separately (not restarted)")
        
        logger.warning("Admin reset completed successfully")
        
        return {
            "status": "success",
            "message": "System reset completed",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "actions": actions,
            "workers_restarted": workers_restarted,
            "current_stats": stats
        }
        
    except Exception as e:
        logger.error(f"Admin reset failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Reset failed: {str(e)}"
        )


@app.get("/solve/async/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Get status of asynchronous solver job.
    
    Path parameters:
    - job_id: UUID returned from POST /solve/async
    
    Returns:
    - 200: Job status information
    - 404: Job not found (invalid UUID or expired)
    
    Status values:
    - queued: Waiting in queue
    - validating: Validating input
    - in_progress: Solver running
    - completed: Solution ready (use GET /solve/async/{job_id}/result)
    - failed: Error occurred (see error_message)
    - expired: Result expired (TTL exceeded)
    """
    job_info = job_manager.get_job(job_id)
    
    if not job_info:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found"
        )
    
    return JobStatusResponse(
        job_id=job_info.job_id,
        status=job_info.status.value,
        created_at=datetime.fromtimestamp(job_info.created_at).isoformat(),
        started_at=datetime.fromtimestamp(job_info.started_at).isoformat() if job_info.started_at else None,
        completed_at=datetime.fromtimestamp(job_info.completed_at).isoformat() if job_info.completed_at else None,
        error_message=job_info.error_message,
        result_available=(job_info.status.value == "completed"),
        result_size_bytes=job_info.result_size_bytes
    )


@app.get("/solve/async/{job_id}/result")
async def get_job_result(job_id: str):
    """
    Download result of completed solver job.
    
    Path parameters:
    - job_id: UUID returned from POST /solve/async
    
    Returns:
    - 200: Full solver output JSON (same format as POST /solve)
    - 404: Job not found
    - 425: Job not completed yet (check status first)
    - 410: Result expired or job failed
    """
    job_info = job_manager.get_job(job_id)
    
    if not job_info:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found"
        )
    
    if job_info.status.value == "failed":
        raise HTTPException(
            status_code=410,
            detail=f"Job failed: {job_info.error_message}"
        )
    
    if job_info.status.value == "expired":
        raise HTTPException(
            status_code=410,
            detail="Job result expired (TTL exceeded)"
        )
    
    if job_info.status.value != "completed":
        raise HTTPException(
            status_code=425,
            detail=f"Job not completed yet (current status: {job_info.status.value})"
        )
    
    result = job_manager.get_result(job_id)
    
    if not result:
        raise HTTPException(
            status_code=410,
            detail="Result no longer available"
        )
    
    return ORJSONResponse(content=result)


@app.delete("/solve/async/{job_id}")
async def cancel_job(job_id: str):
    """
    Cancel pending job or delete result.
    
    Smart cancellation based on job state:
    - QUEUED: Removed from queue immediately
    - IN_PROGRESS: Cancellation flag set, worker stops at next checkpoint (~30-60s)
    - COMPLETED/FAILED: Result deleted, job marked as cancelled
    - CANCELLING: Already cancelling
    - CANCELLED: Already cancelled
    
    Path parameters:
    - job_id: UUID returned from POST /solve/async
    
    Returns:
    - 200: Job cancelled/being cancelled with details
    - 404: Job not found
    
    Response includes:
    - method: Cancellation strategy used (queue_removal, cancellation_flag, result_deletion)
    - immediate: Whether cancellation is immediate (true) or takes time (false)
    - estimated_stop_time_seconds: For non-immediate cancellations
    
    Note: Jobs IN_PROGRESS cannot be stopped instantly due to CP-SAT solver limitations.
    Worker checks cancellation flag before and after solving, typically stopping within 60 seconds.
    """
    result = job_manager.cancel_job(job_id)
    
    if not result.get("success"):
        raise HTTPException(
            status_code=404,
            detail=result.get("error", f"Job {job_id} not found")
        )
    
    return result


@app.post("/solve/async/{job_id}/cancel")
async def cancel_job_post(job_id: str):
    """
    Cancel job (alternative POST endpoint for systems that don't support DELETE).
    
    Same functionality as DELETE /solve/async/{job_id}.
    
    Smart cancellation based on job state:
    - QUEUED: Removed from queue immediately  
    - IN_PROGRESS: Cancellation flag set, worker stops at checkpoint (~30-60s)
    - COMPLETED/FAILED: Result deleted, job marked as cancelled
    
    Path parameters:
    - job_id: UUID returned from POST /solve/async
    
    Returns:
    - 200: Job cancelled/being cancelled with details
    - 404: Job not found
    """
    result = job_manager.cancel_job(job_id)
    
    if not result.get("success"):
        raise HTTPException(
            status_code=404,
            detail=result.get("error", f"Job {job_id} not found")
        )
    
    return result


# ============================================================================
# INCREMENTAL SOLVE ENDPOINT (v0.80)
# ============================================================================

@app.post("/solve/incremental", response_class=ORJSONResponse)
async def solve_incremental_endpoint(
    request: Request,
    payload: IncrementalSolveRequest
):
    """
    Incremental solver for mid-month scenarios.
    
    Use cases:
    - New employees joining mid-month (fill unassigned slots from join date onwards)
    - Employee departures/resignations (re-assign their future slots)
    - Long leave periods (temporarily unassign and re-distribute)
    
    How it works:
    1. Locks all assignments before cutoffDate (immutable/historical)
    2. Identifies solvable slots:
       - Slots >= solveFromDate that are UNASSIGNED
       - Slots assigned to departed employees (freed)
       - Slots during long leave periods (freed)
    3. Builds employee pool: previous employees (minus departed) + new joiners
    4. Solves only for solvable slots while respecting:
       - Locked weekly hours from locked assignments
       - Consecutive days leading up to solve window
       - All standard constraints (C1-C17)
    5. Returns combined output with audit trail (source: locked vs incremental)
    
    Temporal window validation:
    - cutoffDate < solveFromDate (error if not)
    - solveFromDate <= solveToDate (error if not)
    
    Employee changes:
    - newJoiners: Delta only (full employee objects + availableFrom dates)
    - notAvailableFrom: Employees who departed (their future assignments freed)
    - longLeave: Temporary unavailability windows (can work before/after)
    
    Rotation re-baseline:
    - All employees (including existing) get fresh rotation pattern from solveFromDate
    - CP-SAT optimizes offsets independently for each employee
    
    Constraints:
    - Weekly hours: Count locked hours Mon-cutoff + new hours cutoff-Sun
    - Consecutive days: Track locked streak before solve window
    - Validation: Only new assignments validated (trust locked assignments)
    
    Output:
    - Locked assignments marked with "source": "locked"
    - New assignments marked with "source": "incremental"
    - Full audit info: solverRunId, timestamp, inputHash, previousJobId
    
    Returns:
    - 200: Incremental solve completed (may have partial solution)
    - 400: Invalid request (temporal window errors, missing data)
    - 422: Validation error (schema mismatch)
    - 500: Solver error
    """
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    logger.info(f"[{request_id}] Incremental solve request received")
    
    try:
        # Convert Pydantic model to dict
        request_data = payload.model_dump()
        
        # Generate unique run ID
        run_id = f"incr-{int(time.time())}-{request_id[:8]}"
        
        # Call incremental solver
        result = solve_incremental(
            request_data=request_data,
            solver_engine=solve,  # Pass solver function
            run_id=run_id
        )
        
        logger.info(f"[{request_id}] Incremental solve completed: {result.get('status')}")
        
        # Enrich result with meta information (unwrapped format like /solve endpoint)
        result.setdefault("meta", {})
        result["meta"]["requestId"] = request_id
        result["meta"]["runId"] = run_id
        result["meta"]["timestamp"] = datetime.now().isoformat()
        if "schemaVersion" not in result["meta"]:
            result["meta"]["schemaVersion"] = request_data.get("schemaVersion", "0.95")
        
        return result
        
    except IncrementalSolverError as e:
        logger.error(f"[{request_id}] Incremental solver error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        logger.error(
            f"[{request_id}] Unexpected error in incremental solve: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.post("/solve/fill-slots-mixed", response_class=ORJSONResponse)
async def solve_fill_slots_endpoint(
    request: Request,
    payload: FillSlotsWithAvailabilityRequest
):
    """
    Fill empty/unassigned slots with existing + new employees (v0.96).
    
    Lightweight slot filling without requiring full previousOutput (~500KB-1MB).
    Optimized for scenarios where you have:
    - Unassigned/empty slots to fill
    - Existing employees with remaining capacity
    - Optional new joiners
    
    How it works:
    1. Takes list of empty slots (with date, shift, hours)
    2. Existing employees with availability tracking:
       - Available hours (weekly/monthly remaining)
       - Available days (consecutive days left, total days)
       - Current state (consecutive streak, last work date, rotation)
    3. Optional new joiners (full employee objects)
    4. Greedy assignment algorithm respects:
       - Weekly hours limit (44h max)
       - Consecutive days limit (12 max)
       - Date-specific availability
       - Employee capacity constraints
    
    Temporal window:
    - cutoffDate: Last date with locked assignments
    - solveFromDate: Start filling slots from this date
    - solveToDate: End of planning horizon
    - lengthDays: Duration (auto-calculated if omitted)
    
    Input format:
    - emptySlots: List of {date, shiftCode, hours, startTime, endTime, ...}
    - existingEmployees: List with availableHours, availableDays, currentState
    - newJoiners: Optional list of full employee objects
    - requirements: Optional requirement definitions
    
    Advantages over full incremental solver:
    - 99% smaller payload (3-8KB vs 500KB-1MB)
    - No previousOutput required
    - Simple availability tracking
    - Fast execution (<1 second for 10-20 slots)
    
    Use cases:
    - Fill unassigned slots mid-month
    - Quick slot filling after departures
    - Partial month re-runs (e.g., Dec 16-31 only)
    - Adding new joiners to existing roster
    
    Returns:
    - 200: Fill slots completed (may have unmet slots)
    - 400: Invalid request (validation errors)
    - 422: Schema validation error
    - 500: Solver error
    """
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    logger.info(f"[{request_id}] Fill slots request received")
    
    try:
        # Convert Pydantic model to dict
        request_data = payload.model_dump()
        
        # Call fill slots solver
        result = solve_fill_slots(request_data)
        
        logger.info(f"[{request_id}] Fill slots completed: {result['solverRun']['status']}, "
                   f"{result['solverRun']['numAssignments']} assignments")
        
        # Add request ID to meta
        result["meta"]["requestId"] = request_id
        
        return result
        
    except FillSlotsSolverError as e:
        logger.error(f"[{request_id}] Fill slots solver error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        logger.error(
            f"[{request_id}] Unexpected error in fill slots: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


# ============================================================================
# EMPTY SLOTS SOLVE ENDPOINT (v0.96)
# ============================================================================

@app.post("/solve/empty-slots", response_class=ORJSONResponse)
async def solve_empty_slots_endpoint(
    request: Request,
    payload: EmptySlotsRequest
):
    """
    Empty slots solver - Optimized mode that accepts only unfilled slots + locked context.
    
    **Key Benefits:**
    - **97% smaller payload**: Send only 50 empty slots vs 1,550 full assignments
    - **Faster processing**: No classification needed, direct to solving
    - **Clearer intent**: Explicit about what needs to be filled
    - **All constraints**: Full C1-C17 and S1-S16 support
    
    **Use Cases:**
    - Mid-month roster adjustments (only send unfilled slots)
    - New employee onboarding (fill their slots without full roster history)
    - Covering departures/leaves (fill freed slots)
    - Manual roster edits (fill released/modified slots)
    
    **How it works:**
    1. Client provides:
       - Empty slots (what needs filling)
       - Locked employee context (pre-computed hours, consecutive days, last work date)
       - Available employees
    2. Server:
       - Validates input
       - Builds demand items from empty slots (or uses provided)
       - Parses locked context (weekly hours, consecutive days, rotation offsets)
       - Invokes solver with all constraints (C1-C17, S1-S16)
       - Returns only new assignments
    
    **Constraint Compatibility:**
    - C1 MOM Daily Hours: ✓ Enforced
    - C2 Pattern Hours: ✓ Uses workPatternId from lockedContext
    - C3 Consecutive Days: ✓ Uses lockedConsecutiveDays
    - C4 Rest Between Shifts: ✓ Uses lastWorkDate
    - C5-C17: ✓ All enforced
    - S1-S16: ✓ All scored
    
    **Input Example:**
    ```json
    {
      "schemaVersion": "0.96",
      "planningReference": "JAN2026_CHANGIT1",
      "solveMode": "emptySlots",
      "emptySlots": [
        {
          "slotId": "D001-2026-01-15-D-abc",
          "date": "2026-01-15",
          "shiftCode": "D",
          "requirementId": "REQ_APO_DAY",
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
            "weeklyHours": {"2026-W02": 32.0},
            "monthlyHours": 44.0,
            "consecutiveWorkingDays": 3,
            "lastWorkDate": "2026-01-10",
            "rotationOffset": 0,
            "workPatternId": "4ON3OFF"
          }
        ]
      },
      "employees": [...],
      "planningHorizon": {
        "startDate": "2026-01-11",
        "endDate": "2026-01-31"
      }
    }
    ```
    
    **Output:**
    - assignments: List of new assignments (filled + unassigned)
    - emptySlotsMetadata: Coverage stats, reason breakdown
    - solverRun: Solver performance metadata
    - score: Soft constraint violations
    
    **Returns:**
    - 200: Solution completed (may have unassigned slots)
    - 400: Invalid request (missing data, validation errors)
    - 422: Schema validation error
    - 500: Solver execution error
    """
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    logger.info(f"[{request_id}] Empty slots solve request received")
    
    try:
        # Convert Pydantic model to dict
        request_data = payload.model_dump()
        
        # Generate unique run ID
        run_id = f"empty-{int(time.time())}-{request_id[:8]}"
        
        # Log request summary
        empty_slots = request_data.get("emptySlots", [])
        employees = request_data.get("employees", [])
        locked_ctx = request_data.get("lockedContext", {})
        
        logger.info(f"[{request_id}] Empty slots: {len(empty_slots)}")
        logger.info(f"[{request_id}] Employees: {len(employees)}")
        logger.info(f"[{request_id}] Cutoff date: {locked_ctx.get('cutoffDate')}")
        
        # Call empty slots solver
        from src.empty_slots_solver import solve_empty_slots
        
        result = solve_empty_slots(
            request_data=request_data,
            solver_engine=solve,  # Pass solver function
            run_id=run_id
        )
        
        logger.info(f"[{request_id}] Empty slots solve completed")
        logger.info(f"[{request_id}] Filled: {result.get('emptySlotsMetadata', {}).get('filledSlotCount', 0)}/{len(empty_slots)}")
        
        # Enrich result with meta information
        result.setdefault("meta", {})
        result["meta"]["requestId"] = request_id
        result["meta"]["runId"] = run_id
        result["meta"]["timestamp"] = datetime.now().isoformat()
        if "schemaVersion" not in result["meta"]:
            result["meta"]["schemaVersion"] = request_data.get("schemaVersion", "0.96")
        
        return result
        
    except Exception as e:
        logger.error(
            f"[{request_id}] Empty slots solve error: {str(e)}",
            exc_info=True
        )
        
        # Determine error type for appropriate HTTP status
        if "validation" in str(e).lower() or "missing" in str(e).lower():
            status_code = 400
        else:
            status_code = 500
        
        raise HTTPException(status_code=status_code, detail=str(e))


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(
        "Unhandled exception requestId=%s: %s",
        request_id,
        str(exc),
        exc_info=True
    )
    return {
        "status": "ERROR",
        "error": "Internal server error",
        "meta": {
            "requestId": request_id,
            "timestamp": datetime.now().isoformat()
        }
    }


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
