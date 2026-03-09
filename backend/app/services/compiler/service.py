import asyncio
import json
import os
import re
import tempfile
from typing import Any

class CompilerService:
    """Service to safely sandbox and execute Python code."""
    
    @staticmethod
    async def run_python(code: str, stdin: str = "") -> dict[str, Any]:
        """Run standalone Python code with a 5s timeout."""
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                full_code = (
                    "from typing import *\nfrom collections import *\nfrom heapq import *\nfrom bisect import *\nimport math\n\n"
                    + code
                )
                f.write(full_code)
                path = f.name
            try:
                proc = await asyncio.create_subprocess_exec(
                    "python3",
                    path,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(input=stdin.encode() if stdin else None),
                    timeout=5.0,
                )
                return {
                    "stdout": stdout.decode(),
                    "stderr": stderr.decode(),
                    "exit_code": proc.returncode or 0,
                }
            finally:
                os.unlink(path)
        except asyncio.TimeoutError:
            raise Exception("Execution timed out (max 5s)")
        except Exception as e:
            raise Exception(f"run_python failed: {str(e)}")

    @staticmethod
    async def run_examples(code: str, raw_examples: str, expected_outputs: list[str], public_cases_count: int, order_independent: bool = False) -> tuple[list[dict], str]:
        """Run user code against multiple example test cases using a driver script."""
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
        while lines and not lines[0].strip(): lines.pop(0)
        while lines and not lines[-1].strip(): lines.pop()
        
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
                        if not expected_str:
                            expected_serialization = None
                        else:
                            try:
                                parsed_expected = json.loads(expected_str)
                            except json.JSONDecodeError:
                                parsed_expected = expected_str
                    else:
                        parsed_expected = expected
                    
                    if expected_serialization is not None or (isinstance(expected, str) and expected.strip()) or not isinstance(expected, str):
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
        print(json.dumps([{"error": "Driver error: " + str(e)}]))

if __name__ == "__main__":
    raw = __EXAMPLES_JSON__
    expected = __EXPECTED_JSON__
    run_all_tests(raw, expected)
"""
        driver = driver_template.replace("__USER_CODE__", code)
        driver = driver.replace("__EXAMPLES_JSON__", examples_json)
        driver = driver.replace("__EXPECTED_JSON__", expected_outputs_json)
        driver = driver.replace("__PUBLIC_CASES_COUNT__", str(public_cases_count))
        driver = driver.replace("__ORDER_INDEPENDENT__", "True" if order_independent else "False")
        
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(driver)
                path = f.name
            try:
                proc = await asyncio.create_subprocess_exec(
                    "python3",
                    path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10.0)
                out_str = stdout.decode().strip()
                err_str = stderr.decode().strip()

                try:
                    results = json.loads(out_str) if out_str else []
                    results = [dict(r) | {"verified": False} for r in results]
                    return results, err_str
                except json.JSONDecodeError:
                    match = re.search(r"\[.*\]", out_str, re.DOTALL)
                    if match:
                        results = json.loads(match.group(0))
                        results = [dict(r) | {"verified": False} for r in results]
                        return results, err_str
                    return [{"input": "All", "error": "Execution failed to return valid JSON. Output: " + out_str, "verified": False}], err_str
            finally:
                os.unlink(path)
        except asyncio.TimeoutError:
            raise Exception("Execution timed out (max 10s)")
        except Exception as e:
            raise Exception(f"run_examples failed: {str(e)}")
