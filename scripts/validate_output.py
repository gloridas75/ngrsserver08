#!/usr/bin/env python3
"""
Output Format Validator for NGRS Solver v0.95

Validates solver output files against the specification in:
docs/OUTPUT_FORMAT_SPECIFICATION_v095.md

Usage:
    python scripts/validate_output.py --file output/roster.json
    python scripts/validate_output.py --dir output/
    python scripts/validate_output.py --file output/roster.json --strict
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict
from datetime import datetime

# ANSI color codes
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


class OutputValidator:
    """Validates NGRS Solver output against v0.95 specification."""
    
    REQUIRED_TOP_LEVEL_KEYS = [
        'schemaVersion', 'planningReference', 'solverRun', 'score',
        'scoreBreakdown', 'assignments', 'employeeRoster', 'rosterSummary',
        'solutionQuality', 'unmetDemand', 'meta'
    ]
    
    VALID_STATUS_VALUES = ['ASSIGNED', 'OFF_DAY', 'UNASSIGNED']
    DEPRECATED_STATUS_VALUES = ['OFF']
    
    REQUIRED_ASSIGNMENT_FIELDS = [
        'assignmentId', 'employeeId', 'status', 'date', 'shiftCode',
        'startDateTime', 'endDateTime'
    ]
    
    def __init__(self, strict_mode: bool = False):
        self.strict_mode = strict_mode
        self.errors = []
        self.warnings = []
        self.info = []
        
    def validate_file(self, filepath: str) -> Tuple[bool, Dict]:
        """Validate a single output file."""
        self.errors = []
        self.warnings = []
        self.info = []
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON: {e}")
            return False, self._get_summary()
        except FileNotFoundError:
            self.errors.append(f"File not found: {filepath}")
            return False, self._get_summary()
        
        # Run validation checks
        self._validate_schema_version(data)
        self._validate_top_level_structure(data)
        self._validate_assignments(data.get('assignments', []))
        self._validate_meta_block(data.get('meta', {}))
        
        # Determine overall result
        has_errors = len(self.errors) > 0
        has_critical_warnings = self.strict_mode and len(self.warnings) > 0
        success = not (has_errors or has_critical_warnings)
        
        return success, self._get_summary()
    
    def _validate_schema_version(self, data: Dict):
        """Check schema version."""
        version = data.get('schemaVersion')
        if not version:
            self.errors.append("Missing 'schemaVersion' field")
        elif version != "0.95":
            self.warnings.append(f"Schema version is '{version}', expected '0.95'")
        else:
            self.info.append(f"Schema version: {version} ✓")
    
    def _validate_top_level_structure(self, data: Dict):
        """Check top-level keys."""
        missing = [k for k in self.REQUIRED_TOP_LEVEL_KEYS if k not in data]
        if missing:
            self.errors.append(f"Missing top-level keys: {', '.join(missing)}")
        else:
            self.info.append(f"All {len(self.REQUIRED_TOP_LEVEL_KEYS)} top-level keys present ✓")
        
        # Check types
        if 'assignments' in data and not isinstance(data['assignments'], list):
            self.errors.append("'assignments' must be an array")
        if 'employeeRoster' in data and not isinstance(data['employeeRoster'], dict):
            self.errors.append("'employeeRoster' must be an object")
    
    def _validate_assignments(self, assignments: List[Dict]):
        """Validate all assignments."""
        if not assignments:
            self.warnings.append("No assignments found in output")
            return
        
        self.info.append(f"Total assignments: {len(assignments)}")
        
        # Count by status
        status_counts = defaultdict(int)
        for a in assignments:
            status_counts[a.get('status', 'MISSING')] += 1
        
        # Check for deprecated status values
        for status, count in status_counts.items():
            if status in self.DEPRECATED_STATUS_VALUES:
                self.errors.append(
                    f"Found {count} assignments with DEPRECATED status '{status}' "
                    f"(should be 'OFF_DAY')"
                )
            elif status not in self.VALID_STATUS_VALUES and status != 'MISSING':
                self.errors.append(f"Found {count} assignments with INVALID status '{status}'")
        
        # Report status breakdown
        for status in self.VALID_STATUS_VALUES:
            if status in status_counts:
                self.info.append(f"  {status}: {status_counts[status]}")
        
        # Detailed validation of each assignment
        null_timing_count = 0
        missing_fields_count = 0
        invalid_timing_format = 0
        
        for idx, assignment in enumerate(assignments):
            # Check required fields
            missing = [f for f in self.REQUIRED_ASSIGNMENT_FIELDS if f not in assignment]
            if missing:
                missing_fields_count += 1
                if missing_fields_count <= 3:  # Report first 3
                    self.errors.append(
                        f"Assignment {idx} missing fields: {', '.join(missing)}"
                    )
            
            # Check timing (CRITICAL)
            status = assignment.get('status')
            start = assignment.get('startDateTime')
            end = assignment.get('endDateTime')
            
            if start is None or end is None:
                null_timing_count += 1
                if null_timing_count <= 3:  # Report first 3
                    self.errors.append(
                        f"Assignment {idx} ({status}): NULL timing detected "
                        f"(startDateTime={start}, endDateTime={end})"
                    )
            else:
                # Validate ISO 8601 format
                try:
                    datetime.fromisoformat(start)
                    datetime.fromisoformat(end)
                except (ValueError, AttributeError):
                    invalid_timing_format += 1
                    if invalid_timing_format <= 3:
                        self.errors.append(
                            f"Assignment {idx}: Invalid ISO 8601 format "
                            f"(start={start}, end={end})"
                        )
            
            # Status-specific validation
            if status == 'OFF_DAY':
                if assignment.get('shiftCode') != 'O':
                    self.warnings.append(
                        f"Assignment {idx}: OFF_DAY should have shiftCode='O', "
                        f"got '{assignment.get('shiftCode')}'"
                    )
                
                # Check hours are zero
                for hour_field in ['normalHours', 'overtimeHours', 'publicHolidayHours']:
                    if assignment.get(hour_field, 0) != 0:
                        self.warnings.append(
                            f"Assignment {idx}: OFF_DAY should have {hour_field}=0.0, "
                            f"got {assignment.get(hour_field)}"
                        )
            
            elif status == 'UNASSIGNED':
                if assignment.get('employeeId') is not None:
                    self.errors.append(
                        f"Assignment {idx}: UNASSIGNED should have employeeId=null, "
                        f"got '{assignment.get('employeeId')}'"
                    )
            
            elif status == 'ASSIGNED':
                if assignment.get('employeeId') is None:
                    self.errors.append(
                        f"Assignment {idx}: ASSIGNED must have employeeId, got null"
                    )
                
                # Check hours
                total_hours = (
                    assignment.get('normalHours', 0) +
                    assignment.get('overtimeHours', 0) +
                    assignment.get('publicHolidayHours', 0)
                )
                if total_hours <= 0:
                    self.warnings.append(
                        f"Assignment {idx}: ASSIGNED has zero hours "
                        f"(normal={assignment.get('normalHours')}, "
                        f"ot={assignment.get('overtimeHours')}, "
                        f"ph={assignment.get('publicHolidayHours')})"
                    )
        
        # Summary of systematic issues
        if null_timing_count > 3:
            self.errors.append(
                f"... and {null_timing_count - 3} more assignments with NULL timing"
            )
        if missing_fields_count > 3:
            self.errors.append(
                f"... and {missing_fields_count - 3} more assignments with missing fields"
            )
        if invalid_timing_format > 3:
            self.errors.append(
                f"... and {invalid_timing_format - 3} more assignments with invalid timing format"
            )
        
        # Critical timing check summary
        if null_timing_count == 0:
            self.info.append("✓ All assignments have valid timing (no null values)")
        else:
            self.errors.append(
                f"❌ CRITICAL: {null_timing_count} assignments have NULL timing "
                f"(violates v0.95 specification)"
            )
    
    def _validate_meta_block(self, meta: Dict):
        """Validate meta block."""
        rostering_basis = meta.get('rosteringBasis')
        if rostering_basis:
            self.info.append(f"Rostering basis: {rostering_basis}")
            
            if rostering_basis == 'outcome-based':
                generation_mode = meta.get('generationMode')
                if generation_mode:
                    self.info.append(f"Generation mode: {generation_mode}")
        else:
            self.warnings.append("Missing 'rosteringBasis' in meta block")
    
    def _get_summary(self) -> Dict:
        """Get validation summary."""
        return {
            'errors': self.errors,
            'warnings': self.warnings,
            'info': self.info,
            'error_count': len(self.errors),
            'warning_count': len(self.warnings)
        }


def print_results(filepath: str, success: bool, summary: Dict):
    """Print validation results with colors."""
    print(f"\n{BOLD}{'='*80}{RESET}")
    print(f"{BOLD}Validating: {Path(filepath).name}{RESET}")
    print(f"{BOLD}{'='*80}{RESET}")
    
    # Status
    if success:
        print(f"\n{GREEN}{BOLD}✓ VALIDATION PASSED{RESET}")
    else:
        print(f"\n{RED}{BOLD}✗ VALIDATION FAILED{RESET}")
    
    # Info
    if summary['info']:
        print(f"\n{BLUE}{BOLD}Information:{RESET}")
        for msg in summary['info']:
            print(f"  {BLUE}ℹ{RESET} {msg}")
    
    # Warnings
    if summary['warnings']:
        print(f"\n{YELLOW}{BOLD}Warnings ({len(summary['warnings'])}):{RESET}")
        for msg in summary['warnings']:
            print(f"  {YELLOW}⚠{RESET} {msg}")
    
    # Errors
    if summary['errors']:
        print(f"\n{RED}{BOLD}Errors ({len(summary['errors'])}):{RESET}")
        for msg in summary['errors']:
            print(f"  {RED}✗{RESET} {msg}")
    
    print(f"\n{BOLD}{'='*80}{RESET}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Validate NGRS Solver output against v0.95 specification',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/validate_output.py --file output/roster.json
  python scripts/validate_output.py --dir output/ 
  python scripts/validate_output.py --file output/roster.json --strict
        """
    )
    parser.add_argument('--file', help='Path to output file to validate')
    parser.add_argument('--dir', help='Directory of output files to validate')
    parser.add_argument('--strict', action='store_true',
                       help='Treat warnings as errors')
    
    args = parser.parse_args()
    
    if not args.file and not args.dir:
        parser.error("Must specify either --file or --dir")
    
    validator = OutputValidator(strict_mode=args.strict)
    
    # Collect files to validate
    files_to_validate = []
    if args.file:
        files_to_validate.append(args.file)
    elif args.dir:
        output_dir = Path(args.dir)
        if not output_dir.exists():
            print(f"{RED}Error: Directory not found: {args.dir}{RESET}")
            sys.exit(1)
        files_to_validate = list(output_dir.glob('*.json'))
        if not files_to_validate:
            print(f"{YELLOW}Warning: No JSON files found in {args.dir}{RESET}")
            sys.exit(0)
    
    # Validate each file
    results = []
    for filepath in files_to_validate:
        success, summary = validator.validate_file(str(filepath))
        results.append((filepath, success, summary))
        print_results(str(filepath), success, summary)
    
    # Overall summary
    if len(results) > 1:
        passed = sum(1 for _, success, _ in results if success)
        failed = len(results) - passed
        
        print(f"\n{BOLD}{'='*80}{RESET}")
        print(f"{BOLD}OVERALL SUMMARY{RESET}")
        print(f"{BOLD}{'='*80}{RESET}")
        print(f"Total files: {len(results)}")
        print(f"{GREEN}Passed: {passed}{RESET}")
        print(f"{RED}Failed: {failed}{RESET}")
        
        if failed > 0:
            print(f"\n{RED}{BOLD}Failed files:{RESET}")
            for filepath, success, _ in results:
                if not success:
                    print(f"  {RED}✗{RESET} {Path(filepath).name}")
        
        print(f"{BOLD}{'='*80}{RESET}\n")
    
    # Exit code
    all_passed = all(success for _, success, _ in results)
    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()
