"""
NGRS Solver API v2 Router.

This router provides enhanced API endpoints with new features:
- dailyHeadcount support for variable staffing per day
- dayType field for PH/EveOfPH classification
- Enhanced output with dailyCoverage summary

v2 Features:
- Supports dailyHeadcount array in requirements (for demandBased mode)
- dayType field: "Normal", "PublicHoliday", "EveOfPH"
- Variable slots per day based on dailyHeadcount
- Backward compatible: falls back to static headcount if dailyHeadcount missing

Endpoints:
- POST /solve - Synchronous solve with dailyHeadcount support
- POST /solve/async - Asynchronous solve with dailyHeadcount support
- GET /solve/async/{job_id} - Get job status
- GET /solve/async/{job_id}/result - Get job result
"""

from fastapi import APIRouter

router = APIRouter(tags=["v2"])

# Import and include solve endpoints
from .solve import router as solve_router
router.include_router(solve_router)
