"""Domain service for secure Python code execution and test-case orchestration.

This module provides the high-level logic for evaluating user solutions
against Data Structures and Algorithms (DSA) problems. It generates
driver scripts to handle complex objects and provides structured results.
"""

import json
import re
from typing import Any

from app.infrastructure.compiler.executor import compiler_infra


class CompilerService:
    """Orchestrates the evaluation of Python code against test suites."""

    @staticmethod
    async def run_python(code: str, stdin: str = "") -> dict[str, Any]:
        """Safely executes raw Python code in a sandboxed environment.

        Args:
            code (str): The raw Python code to execute.
            stdin (str, optional): Standard input for the script.

        Returns:
            Dict[str, Any]: Execution results including stdout, stderr, and exit_code.
        """
        return await compiler_infra.run_raw_python(code, stdin)

    @staticmethod
    async def run_examples(
        code: str,
        raw_examples: str,
        expected_outputs: list[str],
        public_cases_count: int,
        order_independent: bool = False,
    ) -> tuple[list[dict[str, Any]], str]:
        """Runs user code against multiple test cases using a driver script.

        Args:
            code (str): The user's Python solution code.
            raw_examples (str): Newline-separated JSON strings representing inputs.
            expected_outputs (List[str]): List of expected result serializations.
            public_cases_count (int): How many cases are shown to the user initially.
            order_independent (bool): If True, compares lists by sorting them first.

        Returns:
            Tuple[List[Dict[str, Any]], str]: (Structured test results, stderr).
        """
        expected_outputs_json = json.dumps(expected_outputs)
        examples_json = json.dumps(raw_examples)

        driver_template = r"""
import json
import sys
import inspect
from typing import *
from collections import *
from heapq import *
from bisect import *
import math

__USER_CODE__

def serialize(obj):
    if obj is None: return "null"
    return json.dumps(obj)

def run_all_tests(raw_examples, expected_outputs):
    try:
        if "Solution" not in globals():
            print(json.dumps([{"error": "Class 'Solution' not found."}]))
            return

        sol = Solution()
        methods = [m for m in inspect.getmembers(sol, predicate=inspect.ismethod) 
                   if not m[0].startswith("__")]
        if not methods:
            print(json.dumps([{"error": "No solution method found in Solution class."}]))
            return
        
        name, method = methods[0]
        sig = inspect.signature(method)
        n_args = len([p for p in sig.parameters.values() if p.name != 'self'])
        if n_args == 0: n_args = 1 

        lines = [l for l in raw_examples.split("\n") if l.strip()]
        
        if not lines:
            print(json.dumps([]))
            return

        results = []
        for i in range(0, len(lines), n_args):
            input_lines = lines[i:i+n_args]
            if len(input_lines) < n_args: break
            
            case_idx = i // n_args
            expected = expected_outputs[case_idx] if case_idx < len(expected_outputs) else None
            
            try:
                args = [json.loads(line) for line in input_lines]
                result_val = method(*args)
                
                passed = True
                expected_serialization = None
                if expected is not None:
                    if isinstance(expected, str):
                        expected_str = expected.strip()
                        try:
                            parsed_expected = json.loads(expected_str)
                        except json.JSONDecodeError:
                            parsed_expected = expected_str
                    else:
                        parsed_expected = expected
                    
                    if isinstance(parsed_expected, str):
                        passed = str(result_val).strip() == parsed_expected.strip()
                    else:
                        passed = json.dumps(result_val, sort_keys=True) == json.dumps(parsed_expected, sort_keys=True)
                        if __ORDER_INDEPENDENT__ and not passed and isinstance(result_val, list) and isinstance(parsed_expected, list):
                            try:
                                passed = sorted(result_val) == sorted(parsed_expected)
                            except Exception:
                                pass
                    expected_serialization = serialize(parsed_expected)
                
                results.append({
                    "input": "\n".join(input_lines),
                    "expected": expected_serialization,
                    "output": serialize(result_val),
                    "passed": passed,
                    "is_hidden": case_idx >= __PUBLIC_CASES_COUNT__
                })
            except Exception as e:
                results.append({
                    "input": "\n".join(input_lines),
                    "error": str(e),
                    "passed": False,
                    "is_hidden": case_idx >= __PUBLIC_CASES_COUNT__
                })
        
        print(json.dumps(results))
    except Exception as e:
        print(json.dumps([{"error": "DRIVER_FATAL: " + str(e)}]))

if __name__ == "__main__":
    run_all_tests(__EXAMPLES_JSON__, __EXPECTED_JSON__)
"""
        driver = driver_template.replace("__USER_CODE__", code)
        driver = driver.replace("__EXAMPLES_JSON__", examples_json)
        driver = driver.replace("__EXPECTED_JSON__", expected_outputs_json)
        driver = driver.replace("__PUBLIC_CASES_COUNT__", str(public_cases_count))
        driver = driver.replace(
            "__ORDER_INDEPENDENT__", "True" if order_independent else "False"
        )

        try:
            out_str, err_str = await compiler_infra.run_driver_script(driver)

            try:
                results = json.loads(out_str) if out_str else []
                return [dict(r) | {"verified": False} for r in results], err_str
            except json.JSONDecodeError:
                match = re.search(r"\[.*\]", out_str, re.DOTALL)
                if match:
                    results = json.loads(match.group(0))
                    return [dict(r) | {"verified": False} for r in results], err_str
                return [
                    {
                        "input": "SYSTEM",
                        "error": "Failed to parse execution output as structured JSON.",
                        "verified": False,
                    }
                ], err_str
        except Exception as e:
            raise Exception(f"SERVICE: run_examples failed: {str(e)}")
