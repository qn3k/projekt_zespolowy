from typing import Dict, List, Any
import ast
import sys
from io import StringIO
from contextlib import redirect_stdout
import traceback
import time


class CodeExecutionService:
    def __init__(self):
        self.TIMEOUT = 5
        self.MAX_MEMORY = 100 * 1024 * 1024

    def _validate_code(self, code: str) -> bool:
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    return False

                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in ['eval', 'exec', 'open', '__import__', 'exit', 'quit']:
                            return False
                    elif isinstance(node.func, ast.Attribute):
                        if node.func.attr in ['eval', 'exec', 'open', '__import__', 'exit', 'quit']:
                            return False
                        if isinstance(node.func.value, ast.Name):
                            if node.func.value.id == 'sys' and node.func.attr == 'exit':
                                return False

            return True
        except SyntaxError:
            return False

    def execute_test_case_with_solution(self, user_code: str, correct_solution: str, test_input: str) -> Dict[str, Any]:
        """
        Compare user's code output with the correct solution's output
        """
        if not self._validate_code(user_code):
            return {
                'success': False,
                'error': 'Niedozwolone operacje w kodzie użytkownika'
            }

        if not self._validate_code(correct_solution):
            return {
                'success': False,
                'error': 'Nieprawidłowy kod rozwiązania wzorcowego'
            }

        try:
            # Execute user's code
            user_result = self._execute_code(user_code, test_input)
            if not user_result['success']:
                return user_result

            # Execute correct solution
            solution_result = self._execute_code(correct_solution, test_input)
            if not solution_result['success']:
                return {
                    'success': False,
                    'error': 'Błąd w rozwiązaniu wzorcowym'
                }

            # Compare outputs
            user_output = user_result['output']
            expected_output = solution_result['output']

            if str(user_output).strip() == str(expected_output).strip():
                return {
                    'success': True,
                    'output': user_output,
                    'expected_output': expected_output,
                    'execution_time': user_result['execution_time'],
                    'stdout': user_result['stdout']
                }
            else:
                return {
                    'success': False,
                    'error': f'Nieprawidłowy wynik. Oczekiwano: {expected_output}, otrzymano: {user_output}',
                    'expected_output': expected_output,
                    'actual_output': user_output,
                    'execution_time': user_result['execution_time'],
                    'stdout': user_result['stdout']
                }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }

    def _execute_code(self, code: str, test_input: str) -> Dict[str, Any]:
        """
        Execute a piece of code with given input and return the result
        """
        local_vars = {}
        stdout = StringIO()

        try:
            with redirect_stdout(stdout):
                exec(code, local_vars)

            if 'solution' not in local_vars:
                return {
                    'success': False,
                    'error': 'Brak funkcji solution()'
                }

            start_time = time.time()
            result = local_vars['solution'](eval(test_input))
            execution_time = time.time() - start_time

            return {
                'success': True,
                'output': result,
                'execution_time': execution_time,
                'stdout': stdout.getvalue()
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }

    def run_all_tests_with_solution(self, user_code: str, correct_solution: str, test_cases: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Run all test cases comparing user code with correct solution
        """
        results = []
        all_passed = True

        for test_case in test_cases:
            result = self.execute_test_case_with_solution(
                user_code,
                correct_solution,
                test_case['input_data']
            )
            
            # Add test case info to result
            result.update({
                'input': test_case['input_data'],
                'is_hidden': test_case.get('is_hidden', False)
            })
            
            results.append(result)
            if not result['success']:
                all_passed = False

        return {
            'success': all_passed,
            'results': results
        }

    # Keep the old methods for backward compatibility
    def execute_test_case(self, user_code: str, test_input: str, expected_output: str) -> Dict[str, Any]:
        if not self._validate_code(user_code):
            return {
                'success': False,
                'error': 'Niedozwolone operacje w kodzie'
            }

        local_vars = {}
        stdout = StringIO()

        try:
            with redirect_stdout(stdout):
                exec(user_code, local_vars)

            if 'solution' not in local_vars:
                return {
                    'success': False,
                    'error': 'Brak funkcji solution()'
                }

            start_time = time.time()
            result = local_vars['solution'](eval(test_input))
            execution_time = time.time() - start_time

            if str(result).strip() == str(expected_output).strip():
                return {
                    'success': True,
                    'output': result,
                    'execution_time': execution_time,
                    'stdout': stdout.getvalue()
                }
            else:
                return {
                    'success': False,
                    'error': f'Nieprawidłowy wynik. Oczekiwano: {expected_output}, otrzymano: {result}',
                    'execution_time': execution_time,
                    'stdout': stdout.getvalue()
                }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }

    def run_all_tests(self, user_code: str, test_cases: List[Dict[str, str]]) -> Dict[str, Any]:
        results = []
        all_passed = True

        for test_case in test_cases:
            result = self.execute_test_case(
                user_code,
                test_case['input_data'],
                test_case['expected_output']
            )
            results.append(result)
            if not result['success']:
                all_passed = False

        return {
            'success': all_passed,
            'results': results
        }