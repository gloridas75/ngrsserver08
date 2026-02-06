"""
NGRS Solver API Routers Package.

This package contains versioned API routers:
- v1: Original API (backward compatible, uses static headcount)
- v2: Enhanced API (supports dailyHeadcount for demand-based rostering)
"""

from .v1 import router as v1_router
from .v2 import router as v2_router

__all__ = ['v1_router', 'v2_router']
