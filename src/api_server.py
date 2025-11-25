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
from context.engine.config_optimizer import optimize_all_requirements, format_output_config
from src.models import (
    SolveRequest, SolveResponse, HealthResponse, 
    Score, SolverRunMetadata, Meta, Violation,
    AsyncJobRequest, AsyncJobResponse, JobStatusResponse, AsyncStatsResponse
)
from src.output_builder import build_output
from src.redis_job_manager import RedisJobManager
from src.redis_worker import start_worker_pool

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
    description="REST API for NGRS Shift Scheduling Solver",
    version="0.1.0",
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


@app.get("/version")
async def get_version():
    """Get API and solver version information."""
    return {
        "apiVersion": "0.1.0",
        "solverVersion": "optfold-py-0.4.2",
        "schemaVersion": "0.43",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/solve", response_model=SolveResponse, response_class=ORJSONResponse)
async def solve_endpoint(
    request: Request,
    file: Optional[UploadFile] = File(None),
    time_limit: int = Query(15, ge=1, le=120),
    strict: int = Query(0, ge=0, le=1),
    validate: int = Query(0, ge=0, le=1),
):
    """
    Solve a scheduling problem.
    
    Accepts input via:
    - JSON body: {"input_json": {...}} or raw NGRS input
    - Uploaded file: multipart/form-data with file field
    
    Query parameters:
    - time_limit: Max solve time in seconds (1-120, default 15)
    - strict: If 1, error if both body and file provided (default 0)
    - validate: If 1, validate input against schema (default 0)
    
    Returns:
    - 200: Solution found (regardless of solver status)
    - 400: Invalid input (missing input, or strict mode both provided)
    - 422: Malformed JSON or validation error
    - 500: Internal server error
    """
    
    request_id = request.state.request_id
    start_time = time.perf_counter()
    warnings = []
    
    try:
        # ====== PARSE INPUT ======
        # Extract raw body JSON to support both wrapped and raw formats
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
        
        # Check for dual input and strict mode
        has_body = raw_body_json is not None
        has_file = uploaded_json is not None
        
        if has_body and has_file and strict:
            raise HTTPException(
                status_code=400,
                detail="Provide either input_json or file, not both (strict mode enabled)."
            )
        
        # Get input JSON and collect warnings
        # Pass raw_body_json to support both wrapped {"input_json": {...}} and raw NGRS input
        input_json, input_warnings = get_input_json(None, uploaded_json, raw_body_json)
        warnings.extend(input_warnings)
        
        # ====== LOAD DATA ======
        ctx = load_input(input_json)
        ctx["timeLimit"] = time_limit
        
        # ====== OPTIONAL: SCHEMA VALIDATION ======
        if validate:
            # TODO: Add jsonschema validation if context/schemas/input.schema.json exists
            # For now, schema validation is deferred to solver
            pass
        
        # ====== SOLVE ======
        status_code, solver_result, assignments, violations = solve(ctx)
        
        # ====== BUILD OUTPUT ======
        output_dict = build_output(
            input_json, ctx, status_code, solver_result, assignments, violations
        )
        
        # ====== ENRICH RESPONSE ======
        output_dict["meta"]["requestId"] = request_id
        output_dict["meta"]["warnings"] = warnings
        
        # ====== SAVE OUTPUT TO FILE ======
        try:
            timestamp = datetime.now().strftime("%d%m_%H%M")
            outfile_name = f"output_{timestamp}.json"
            outfile_path = pathlib.Path("output") / outfile_name
            outfile_path.parent.mkdir(parents=True, exist_ok=True)
            outfile_path.write_text(json.dumps(output_dict, indent=2), encoding="utf-8")
            logger.info("solve output saved to %s", outfile_path)
        except Exception as e:
            logger.warning("Failed to save output file: %s", str(e))
        
        # ====== LOG ======
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.info(
            "solve requestId=%s status=%s hard=%s soft=%s assignments=%s durMs=%s",
            request_id,
            output_dict["solverRun"]["status"],
            output_dict["score"]["hard"],
            output_dict["score"]["soft"],
            len(assignments),
            elapsed_ms
        )
        
        return SolveResponse(**output_dict)
    
    except HTTPException:
        raise
    
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        error_msg = f"Internal error: {str(e)}"
        logger.error(
            "solve requestId=%s error=%s durMs=%s",
            request_id,
            str(e),
            elapsed_ms,
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=error_msg)


@app.get("/schema")
async def get_schemas():
    """
    Get JSON schemas for input and output validation.
    
    Returns schemas from context/schemas/ directory if available.
    """
    # TODO: Load actual schemas from context/schemas/
    return {
        "inputSchema": {
            "description": "NGRS input schema (v0.43)"
        },
        "outputSchema": {
            "description": "NGRS output schema (v0.43)"
        }
    }


@app.post("/configure", response_class=ORJSONResponse)
async def configure_endpoint(
    request: Request,
    file: Optional[UploadFile] = File(None),
):
    """
    Configuration Optimizer: Find optimal work patterns and staffing.

    This endpoint analyzes requirements and suggests:
    1. Optimal work patterns for each requirement
    2. Minimum employee count needed per shift type
    3. Recommended rotation offsets for maximum coverage

    Input Schema (required):
    - JSON body: {
        "requirements": [
            {
                "id": "REQ_MIXED",
                "name": "Mixed Day/Night Coverage",
                "shiftTypes": ["D", "N"],
                "headcountPerShift": {"D": 50, "N": 50},
                ...
            }
        ],
        "constraints": {...},
        "planningHorizon": {...}
      }
    - Uploaded file: multipart/form-data with file field (same schema)

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

        # ====== OPTIMIZE ======
        optimized_result = optimize_all_requirements(
            requirements=config_input["requirements"],
            constraints=constraints,
            planning_horizon=config_input["planningHorizon"]
        )

        # ====== FORMAT OUTPUT ======
        output_config = format_output_config(
            optimized_result,
            config_input["requirements"]
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
    - Wrapped format: {"input_json": {...NGRS input...}, "priority": 5}
    - Raw format: {...NGRS input directly...} (without input_json wrapper)
    
    Query parameters (optional):
    - priority: Job priority 0-10 (default 0)
    - ttl_seconds: Result TTL 60-86400 seconds (default 3600)
    
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
        
        if payload:
            priority = payload.priority or 0
            ttl_seconds = payload.ttl_seconds
        elif raw_body_json:
            # Check if raw body has these fields (for backward compatibility)
            priority = raw_body_json.get("priority", 0)
            ttl_seconds = raw_body_json.get("ttl_seconds")
        
        # Create job
        job_id = job_manager.create_job(input_json)
        
        queue_length = job_manager.get_queue_length()
        logger.info(
            "async_job_created requestId=%s jobId=%s queueLength=%s",
            request_id, job_id, queue_length
        )
        
        return AsyncJobResponse(
            job_id=job_id,
            status="queued",
            created_at=datetime.now().isoformat(),
            message="Job submitted successfully"
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
    
    Path parameters:
    - job_id: UUID returned from POST /solve/async
    
    Returns:
    - 200: Job cancelled/deleted
    - 404: Job not found
    
    Note: Jobs already in_progress cannot be stopped mid-execution,
    but will be removed from system once completed.
    """
    deleted = job_manager.delete_job(job_id)
    
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found"
        )
    
    return {
        "message": f"Job {job_id} cancelled/deleted",
        "job_id": job_id
    }


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
