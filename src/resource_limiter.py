"""Resource limiter to prevent solver from consuming all system resources.

This module sets hard limits on memory and CPU usage to prevent system crashes
when solving complex problems with millions of decision variables.
"""

import resource
import psutil
import os
import sys
from typing import Optional


def get_system_memory_gb() -> float:
    """Get total system memory in GB."""
    return psutil.virtual_memory().total / (1024 ** 3)


def set_memory_limit(max_memory_gb: Optional[float] = None, percentage: float = 75):
    """Set maximum memory limit for the process.
    
    Args:
        max_memory_gb: Explicit memory limit in GB (overrides percentage)
        percentage: Percentage of system RAM to use (default: 75%)
        
    Example:
        set_memory_limit(max_memory_gb=8)  # Hard limit at 8GB
        set_memory_limit(percentage=75)     # Use 75% of system RAM
    """
    system_memory_gb = get_system_memory_gb()
    
    if max_memory_gb is None:
        max_memory_gb = system_memory_gb * (percentage / 100)
    
    max_memory_bytes = int(max_memory_gb * 1024 ** 3)
    
    try:
        # Set virtual memory limit (address space)
        resource.setrlimit(resource.RLIMIT_AS, (max_memory_bytes, max_memory_bytes))
        print(f"[ResourceLimiter] ✓ Memory limit set: {max_memory_gb:.1f} GB ({percentage:.0f}% of {system_memory_gb:.1f} GB system RAM)")
        return True
    except ValueError as e:
        print(f"[ResourceLimiter] ⚠️  Could not set memory limit: {e}")
        return False
    except Exception as e:
        print(f"[ResourceLimiter] ⚠️  Unexpected error setting memory limit: {e}")
        return False


def set_cpu_time_limit(max_seconds: int):
    """Set maximum CPU time limit for the process.
    
    Args:
        max_seconds: Maximum CPU seconds (not wall-clock time)
        
    Note: This is CPU time, not real time. A 300s CPU limit might be 600s wall-clock
          if the process is using 50% CPU on average.
    """
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (max_seconds, max_seconds))
        print(f"[ResourceLimiter] ✓ CPU time limit set: {max_seconds} seconds")
        return True
    except Exception as e:
        print(f"[ResourceLimiter] ⚠️  Could not set CPU time limit: {e}")
        return False


def get_current_memory_usage_gb() -> float:
    """Get current process memory usage in GB."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 ** 3)


def check_memory_usage(threshold_percentage: float = 90) -> bool:
    """Check if current memory usage exceeds threshold.
    
    Args:
        threshold_percentage: Percentage of system RAM (default: 90%)
        
    Returns:
        True if within limits, False if exceeded
    """
    system_memory = psutil.virtual_memory()
    used_percentage = system_memory.percent
    
    if used_percentage >= threshold_percentage:
        print(f"[ResourceLimiter] ⚠️  Memory usage critical: {used_percentage:.1f}% (threshold: {threshold_percentage}%)")
        return False
    
    return True


class ResourceMonitor:
    """Context manager for monitoring resource usage during solver execution."""
    
    def __init__(self, max_memory_gb: Optional[float] = None, memory_percentage: float = 75):
        self.max_memory_gb = max_memory_gb
        self.memory_percentage = memory_percentage
        self.initial_memory_gb = None
        
    def __enter__(self):
        self.initial_memory_gb = get_current_memory_usage_gb()
        set_memory_limit(self.max_memory_gb, self.memory_percentage)
        print(f"[ResourceMonitor] Starting with {self.initial_memory_gb:.2f} GB memory usage")
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        final_memory_gb = get_current_memory_usage_gb()
        peak_memory_gb = final_memory_gb  # Approximate (actual peak might be higher)
        
        print(f"[ResourceMonitor] Memory usage:")
        print(f"  Initial: {self.initial_memory_gb:.2f} GB")
        print(f"  Final: {final_memory_gb:.2f} GB")
        print(f"  Delta: +{final_memory_gb - self.initial_memory_gb:.2f} GB")
        
        if exc_type is MemoryError:
            print(f"[ResourceMonitor] ❌ OUT OF MEMORY - Process exceeded memory limit")
            print(f"  Recommendation: Reduce problem complexity or increase memory limit")
            return False  # Don't suppress the exception


def apply_solver_resource_limits(max_memory_gb: Optional[float] = None, 
                                 memory_percentage: float = 75,
                                 max_cpu_seconds: Optional[int] = None):
    """Apply resource limits before starting solver.
    
    Args:
        max_memory_gb: Explicit memory limit in GB (default: None = use percentage)
        memory_percentage: Percentage of system RAM to use (default: 75%)
        max_cpu_seconds: Maximum CPU seconds (default: None = no limit)
        
    Example:
        # Use 75% of system RAM
        apply_solver_resource_limits()
        
        # Use explicit 12GB limit
        apply_solver_resource_limits(max_memory_gb=12)
        
        # Use 60% RAM + 600s CPU limit
        apply_solver_resource_limits(memory_percentage=60, max_cpu_seconds=600)
    """
    print(f"[ResourceLimiter] Applying resource limits...")
    print(f"  System: {get_system_memory_gb():.1f} GB RAM, {psutil.cpu_count()} CPUs")
    
    # Set memory limit
    set_memory_limit(max_memory_gb, memory_percentage)
    
    # Set CPU limit if specified
    if max_cpu_seconds:
        set_cpu_time_limit(max_cpu_seconds)
    
    print(f"[ResourceLimiter] ✓ Resource limits applied")


if __name__ == "__main__":
    # Test the resource limiter
    print("Resource Limiter Test")
    print("=" * 60)
    
    system_mem = get_system_memory_gb()
    print(f"System Memory: {system_mem:.1f} GB")
    print(f"Current Usage: {get_current_memory_usage_gb():.2f} GB")
    print()
    
    print("Setting 75% memory limit...")
    apply_solver_resource_limits(memory_percentage=75)
    print()
    
    print("Memory check:")
    print(f"  Within limits: {check_memory_usage(90)}")
