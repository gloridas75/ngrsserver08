"""
NGRS Solver API v1 Router.

This router provides the original API endpoints with backward compatibility.
All v1 endpoints use static headcount from requirements.

Endpoints:
- POST /solve - Synchronous solve
- POST /solve/async - Asynchronous solve with Redis queue
- GET /solve/async/{job_id} - Get job status
- GET /solve/async/{job_id}/result - Get job result
- POST /configure - ICPMP configuration optimizer
"""

from fastapi import APIRouter

router = APIRouter(tags=["v1"])

# Import and include solve endpoints
from .solve import router as solve_router
router.include_router(solve_router)
