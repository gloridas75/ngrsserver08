#!/usr/bin/env python3
"""
Regression Test Suite for NGRS Solver

Automatically runs all test inputs and validates outputs against baselines.
Use this before committing changes to ensure no regressions.

Usage:
    python test_regression.py                    # Run all tests
    python test_regression.py --update-baselines # Update expected results
    python test_regression.py --filter RST-      # Run only matching tests
    python test_regression.py --verbose          # Show detailed output
"""

import json
import sys
import os
import time
from pathlib import Path
from datetime import datetime
import argparse
import subprocess
from typing import Dict, List, Tuple, Optional

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def run_solver(input_path: str, output_path: str, timeout: int = 120) -> Tuple[bool, str, float]:
    """
    Run solver on input file and return success status.
    
    Returns:
        Tuple of (success, error_message, solve_time)
    """
    start_time = time.time()
    
    try:
        result = subprocess.run(
            ['python', 'src/run_solver.py', '--in', input_path, '--out', output_path, '--time', str(timeout)],
            capture_output=True,
            text=True,
            timeout=timeout + 10,  # Add buffer to subprocess timeout
            cwd=Path(__file__).parent
        )
        
        solve_time = time.time() - start_time
        
        if result.returncode != 0:
            # Extract error from stderr
            error_lines = result.stderr.strip().split('\n')[-10:]  # Last 10 lines
            error_msg = '\n'.join(error_lines)
            return False, f"Solver exited with code {result.returncode}:\n{error_msg}", solve_time
        
        return True, "", solve_time
        
    except subprocess.TimeoutExpired:
        return False, f"Solver timed out after {timeout}s", timeout
    except Exception as e:
        return False, f"Exception running solver: {str(e)}", time.time() - start_time

def extract_key_metrics(output_data: dict) -> dict:
    """Extract key metrics from solver output for comparison."""
    return {
        'status': output_data.get('solverRun', {}).get('status', 'UNKNOWN'),
        'total_assignments': len(output_data.get('assignments', [])),
        'assigned_count': sum(1 for a in output_data.get('assignments', []) if a.get('status') == 'ASSIGNED'),
        'unassigned_count': sum(1 for a in output_data.get('assignments', []) if a.get('status') == 'UNASSIGNED'),
        'hard_score': output_data.get('score', {}).get('hard', 0),
        'soft_score': output_data.get('score', {}).get('soft', 0),
        'hard_violations': len(output_data.get('scoreBreakdown', {}).get('hard', {}).get('violations', [])),
        'employees_used': len(set(a['employeeId'] for a in output_data.get('assignments', []) if a.get('employeeId'))),
    }

def compare_results(current: dict, baseline: dict, test_name: str) -> Tuple[bool, List[str]]:
    """
    Compare current results against baseline.
    
    Returns:
        Tuple of (passed, list_of_differences)
    """
    differences = []
    
    # Critical checks
    if current['status'] != baseline['status']:
        differences.append(f"Status changed: {baseline['status']} → {current['status']}")
    
    if current['hard_violations'] != baseline['hard_violations']:
        differences.append(
            f"Hard violations changed: {baseline['hard_violations']} → {current['hard_violations']}"
        )
    
    # Warning-level checks (not failures, but worth noting)
    if abs(current['assigned_count'] - baseline['assigned_count']) > 0:
        differences.append(
            f"⚠️  Assigned count changed: {baseline['assigned_count']} → {current['assigned_count']}"
        )
    
    if abs(current['employees_used'] - baseline['employees_used']) > 0:
        differences.append(
            f"⚠️  Employees used changed: {baseline['employees_used']} → {current['employees_used']}"
        )
    
    # Consider test passed if no critical differences
    passed = (
        current['status'] == baseline['status'] and
        current['hard_violations'] == baseline['hard_violations']
    )
    
    return passed, differences

def load_baseline(test_name: str) -> Optional[dict]:
    """Load baseline metrics for a test."""
    baseline_path = Path('test_baselines') / f"{test_name}.json"
    if baseline_path.exists():
        with open(baseline_path, 'r') as f:
            return json.load(f)
    return None

def save_baseline(test_name: str, metrics: dict):
    """Save baseline metrics for a test."""
    baseline_dir = Path('test_baselines')
    baseline_dir.mkdir(exist_ok=True)
    
    baseline_path = baseline_dir / f"{test_name}.json"
    with open(baseline_path, 'w') as f:
        json.dump(metrics, f, indent=2)

def discover_test_inputs(filter_pattern: Optional[str] = None) -> List[Path]:
    """Discover all test input JSONs in input/ folder."""
    input_dir = Path('input')
    
    if not input_dir.exists():
        return []
    
    # Find all JSON files that look like solver inputs
    all_jsons = list(input_dir.glob('*.json'))
    
    # Filter by pattern if provided
    if filter_pattern:
        all_jsons = [p for p in all_jsons if filter_pattern in p.name]
    
    return sorted(all_jsons)

def print_test_header():
    """Print test suite header."""
    print("=" * 80)
    print(f"{Colors.BOLD}NGRS SOLVER - REGRESSION TEST SUITE{Colors.RESET}")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()

def print_test_result(test_name: str, passed: bool, solve_time: float, differences: List[str] = None):
    """Print individual test result."""
    status_icon = f"{Colors.GREEN}✓{Colors.RESET}" if passed else f"{Colors.RED}✗{Colors.RESET}"
    status_text = f"{Colors.GREEN}PASS{Colors.RESET}" if passed else f"{Colors.RED}FAIL{Colors.RESET}"
    
    print(f"{status_icon} {test_name}: {status_text} ({solve_time:.2f}s)")
    
    if differences:
        for diff in differences:
            if diff.startswith('⚠️'):
                print(f"    {Colors.YELLOW}{diff}{Colors.RESET}")
            else:
                print(f"    {Colors.RED}{diff}{Colors.RESET}")

def print_summary(results: List[dict]):
    """Print test suite summary."""
    print()
    print("=" * 80)
    print(f"{Colors.BOLD}SUMMARY{Colors.RESET}")
    print("=" * 80)
    
    total = len(results)
    passed = sum(1 for r in results if r['passed'])
    failed = total - passed
    
    print(f"Total tests: {total}")
    print(f"{Colors.GREEN}Passed: {passed}{Colors.RESET}")
    if failed > 0:
        print(f"{Colors.RED}Failed: {failed}{Colors.RESET}")
    
    total_time = sum(r['solve_time'] for r in results)
    print(f"Total time: {total_time:.2f}s")
    print()
    
    if failed > 0:
        print(f"{Colors.RED}REGRESSION DETECTED - DO NOT COMMIT{Colors.RESET}")
        print("Review failures above and fix issues before pushing.")
        return False
    else:
        print(f"{Colors.GREEN}ALL TESTS PASSED - SAFE TO COMMIT{Colors.RESET}")
        return True

def main():
    parser = argparse.ArgumentParser(description='Run regression tests for NGRS Solver')
    parser.add_argument('--update-baselines', action='store_true',
                        help='Update baseline results for all tests')
    parser.add_argument('--filter', type=str,
                        help='Filter tests by name pattern (e.g., "RST-2026")')
    parser.add_argument('--verbose', action='store_true',
                        help='Show detailed solver output')
    parser.add_argument('--timeout', type=int, default=120,
                        help='Solver timeout in seconds (default: 120)')
    
    args = parser.parse_args()
    
    # Change to script directory
    os.chdir(Path(__file__).parent)
    
    print_test_header()
    
    # Discover test inputs
    test_inputs = discover_test_inputs(args.filter)
    
    if not test_inputs:
        print(f"{Colors.YELLOW}No test inputs found in input/ folder{Colors.RESET}")
        if args.filter:
            print(f"Filter pattern: {args.filter}")
        return 1
    
    print(f"Found {len(test_inputs)} test input(s)")
    if args.filter:
        print(f"Filter: {args.filter}")
    print()
    
    results = []
    
    for input_path in test_inputs:
        test_name = input_path.stem  # Filename without extension
        output_path = Path('output') / f"test_regression_{test_name}.json"
        
        if args.verbose:
            print(f"\n{Colors.BLUE}Running: {test_name}{Colors.RESET}")
        
        # Run solver
        success, error_msg, solve_time = run_solver(str(input_path), str(output_path), args.timeout)
        
        if not success:
            print_test_result(test_name, False, solve_time, [error_msg])
            results.append({
                'test_name': test_name,
                'passed': False,
                'solve_time': solve_time,
                'error': error_msg
            })
            continue
        
        # Load output
        try:
            with open(output_path, 'r') as f:
                output_data = json.load(f)
        except Exception as e:
            print_test_result(test_name, False, solve_time, [f"Failed to load output: {str(e)}"])
            results.append({
                'test_name': test_name,
                'passed': False,
                'solve_time': solve_time,
                'error': str(e)
            })
            continue
        
        # Extract metrics
        current_metrics = extract_key_metrics(output_data)
        
        if args.update_baselines:
            # Update baseline mode
            save_baseline(test_name, current_metrics)
            print_test_result(test_name, True, solve_time, ["Baseline updated"])
            results.append({
                'test_name': test_name,
                'passed': True,
                'solve_time': solve_time,
                'baseline_updated': True
            })
        else:
            # Comparison mode
            baseline = load_baseline(test_name)
            
            if baseline is None:
                print_test_result(test_name, True, solve_time, 
                                ["⚠️  No baseline - run with --update-baselines to create"])
                results.append({
                    'test_name': test_name,
                    'passed': True,  # Pass if no baseline exists
                    'solve_time': solve_time,
                    'no_baseline': True
                })
            else:
                # Compare against baseline
                passed, differences = compare_results(current_metrics, baseline, test_name)
                print_test_result(test_name, passed, solve_time, differences)
                results.append({
                    'test_name': test_name,
                    'passed': passed,
                    'solve_time': solve_time,
                    'differences': differences
                })
    
    # Print summary
    all_passed = print_summary(results)
    
    # Return exit code
    return 0 if all_passed else 1

if __name__ == '__main__':
    sys.exit(main())
