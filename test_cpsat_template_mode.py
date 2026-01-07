"""
Test CP-SAT template generation mode vs incremental validation mode.

This test validates:
1. Pattern validation now allows flexible patterns like ["D","D","D","D","D","D","D"]
2. Both templateGenerationMode options work correctly
3. optimizationMode setting is respected

Test Cases:
- TC1: Flexible pattern with incremental mode
- TC2: Flexible pattern with cpsat mode (minimizeEmployeeCount)
- TC3: Flexible pattern with cpsat mode (balanceWorkload)
- TC4: Pattern with explicit off-days (both modes)
"""

import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def create_test_input(template_mode: str, optimization_mode: str = "minimizeEmployeeCount") -> dict:
    """Create test input with specified template generation mode."""
    return {
        "schemaVersion": "0.95",
        "planningReference": {
            "scheme": "SchemeA",
            "planId": "TEST-CPSAT-MODE",
            "createdDate": "2024-06-01"
        },
        "planningHorizon": {
            "startDate": "2024-06-01",
            "endDate": "2024-06-14"  # 2 weeks for quick test
        },
        "solverConfig": {
            "maxSolveTimeSeconds": 30,
            "optimizationMode": optimization_mode,  # "minimizeEmployeeCount" or "balanceWorkload"
            "allowPartialSolution": True
        },
        "employees": [
            {
                "employeeId": "EMP001",
                "ouId": "OU-A",
                "rank": "SGT",
                "isAPO": False,
                "rotationOffset": 0,
                "employmentScheme": "SchemeA"
            },
            {
                "employeeId": "EMP002",
                "ouId": "OU-A",
                "rank": "SGT",
                "isAPO": False,
                "rotationOffset": 1,
                "employmentScheme": "SchemeA"
            },
            {
                "employeeId": "EMP003",
                "ouId": "OU-A",
                "rank": "SGT",
                "isAPO": False,
                "rotationOffset": 2,
                "employmentScheme": "SchemeA"
            }
        ],
        "demandItems": [
            {
                "demandId": "DEM-01",
                "positionId": "SECURITY-OFFICER",
                "locationId": "SITE-A",
                "sourceMode": "outcomeBased",
                "templateGenerationMode": template_mode,  # "incremental" or "cpsat"
                "shiftStartDate": "2024-06-01",  # Required for slot builder
                "shiftEndDate": "2024-06-14",    # Required for slot builder
                "shifts": [
                    {
                        "coverageDays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                        "shiftDetails": [
                            {
                                "shiftCode": "D",
                                "startTime": "07:00",
                                "endTime": "19:00"
                            }
                        ]
                    }
                ],
                "workRequirements": [
                    {
                        "requirementId": "REQ-01",
                        "requiredEmployeeCount": 3,
                        "minRank": "SGT",
                        "workPattern": ["D", "D", "D", "D", "D", "D", "D"],  # Flexible pattern
                        "rotationPatternName": "7D-AUTO",
                        "positionId": "SECURITY-OFFICER",
                        "locationId": "SITE-A"
                    }
                ]
            }
        ],
        "constraintList": [
            {"constraintId": "C1", "enabled": True},
            {"constraintId": "C2", "enabled": True},
            {"constraintId": "C4", "enabled": True},
            {"constraintId": "C5", "enabled": True},
            {"constraintId": "C8", "enabled": True},
            {"constraintId": "C9", "enabled": True}
        ]
    }


def test_incremental_mode():
    """Test TC1: Flexible pattern with incremental validation."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST CASE 1: Flexible Pattern + Incremental Mode")
    logger.info("=" * 80)
    
    test_input = create_test_input(template_mode="incremental")
    
    # Save test input
    with open("test_input_incremental.json", "w") as f:
        json.dump(test_input, f, indent=2)
    
    logger.info("✅ Test input created: test_input_incremental.json")
    logger.info(f"   Pattern: {test_input['demandItems'][0]['workRequirements'][0]['workPattern']}")
    logger.info(f"   Template Mode: {test_input['demandItems'][0]['templateGenerationMode']}")
    logger.info(f"   Optimization Mode: {test_input['solverConfig']['optimizationMode']}")
    
    return test_input


def test_cpsat_minimize():
    """Test TC2: Flexible pattern with CP-SAT (minimize employees)."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST CASE 2: Flexible Pattern + CP-SAT (Minimize)")
    logger.info("=" * 80)
    
    test_input = create_test_input(
        template_mode="cpsat",
        optimization_mode="minimizeEmployeeCount"
    )
    
    # Save test input
    with open("test_input_cpsat_minimize.json", "w") as f:
        json.dump(test_input, f, indent=2)
    
    logger.info("✅ Test input created: test_input_cpsat_minimize.json")
    logger.info(f"   Pattern: {test_input['demandItems'][0]['workRequirements'][0]['workPattern']}")
    logger.info(f"   Template Mode: {test_input['demandItems'][0]['templateGenerationMode']}")
    logger.info(f"   Optimization Mode: {test_input['solverConfig']['optimizationMode']}")
    
    return test_input


def test_cpsat_balance():
    """Test TC3: Flexible pattern with CP-SAT (balance workload)."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST CASE 3: Flexible Pattern + CP-SAT (Balance)")
    logger.info("=" * 80)
    
    test_input = create_test_input(
        template_mode="cpsat",
        optimization_mode="balanceWorkload"
    )
    
    # Save test input
    with open("test_input_cpsat_balance.json", "w") as f:
        json.dump(test_input, f, indent=2)
    
    logger.info("✅ Test input created: test_input_cpsat_balance.json")
    logger.info(f"   Pattern: {test_input['demandItems'][0]['workRequirements'][0]['workPattern']}")
    logger.info(f"   Template Mode: {test_input['demandItems'][0]['templateGenerationMode']}")
    logger.info(f"   Optimization Mode: {test_input['solverConfig']['optimizationMode']}")
    
    return test_input


def test_explicit_offdays():
    """Test TC4: Pattern with explicit off-days (both modes)."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST CASE 4: Explicit Off-Days Pattern")
    logger.info("=" * 80)
    
    test_input = create_test_input(template_mode="incremental")
    
    # Modify pattern to have explicit off-days
    test_input['demandItems'][0]['workRequirements'][0]['workPattern'] = [
        "D", "D", "D", "D", "D", "O", "O"
    ]
    
    # Save test input
    with open("test_input_explicit_offdays.json", "w") as f:
        json.dump(test_input, f, indent=2)
    
    logger.info("✅ Test input created: test_input_explicit_offdays.json")
    logger.info(f"   Pattern: {test_input['demandItems'][0]['workRequirements'][0]['workPattern']}")
    logger.info(f"   Template Mode: {test_input['demandItems'][0]['templateGenerationMode']}")
    
    return test_input


if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("CPSAT TEMPLATE MODE TEST SUITE")
    logger.info("=" * 80)
    logger.info("\nGenerating test inputs for all test cases...")
    
    test_incremental_mode()
    test_cpsat_minimize()
    test_cpsat_balance()
    test_explicit_offdays()
    
    logger.info("\n" + "=" * 80)
    logger.info("✅ ALL TEST INPUTS GENERATED")
    logger.info("=" * 80)
    logger.info("\nRun tests with:")
    logger.info("  python src/run_solver.py --in test_input_incremental.json --time 30")
    logger.info("  python src/run_solver.py --in test_input_cpsat_minimize.json --time 30")
    logger.info("  python src/run_solver.py --in test_input_cpsat_balance.json --time 30")
    logger.info("  python src/run_solver.py --in test_input_explicit_offdays.json --time 30")
    logger.info("\nExpected Behavior:")
    logger.info("  ✅ All patterns should pass validation")
    logger.info("  ✅ CP-SAT mode should produce optimal assignments")
    logger.info("  ✅ Minimize mode should prefer fewer work days")
    logger.info("  ✅ Balance mode should distribute work evenly")
    logger.info("  ✅ Explicit off-days should be respected in final roster")
