import ast
import hashlib
import json
from collections import Counter

from testpilot.errors import LLMOutputValidationError
from testpilot.schemas.test_plan import TestBundle
from testpilot.tools.test_validator import retain_tests, validate_tests


def digest(tests):
    data = [(t.path, t.content) for t in tests]
    return hashlib.sha256(json.dumps(data, ensure_ascii=False).encode()).hexdigest()


def preflight(tests):
    tests = TestBundle.model_validate({"files": tests}).files
    validate_tests(tests)
    for test in tests:
        try:
            tree = ast.parse(test.content)
        except SyntaxError as exc:
            raise LLMOutputValidationError(f"{test.path}: SyntaxError line {exc.lineno}") from exc
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in {"skip", "skipif", "xfail"}:
                raise LLMOutputValidationError("skip/skipif/xfail are forbidden")
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                modules = (
                    [a.name for a in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                )
                if any(
                    m.split(".")[0] in {"subprocess", "socket", "requests", "httpx"}
                    for m in modules
                ):
                    raise LLMOutputValidationError("process/network imports are forbidden")
            if isinstance(node, ast.Call):
                name = ast.unparse(node.func)
                if name in {"eval", "exec", "__import__", "os.system", "os.popen"}:
                    raise LLMOutputValidationError("dynamic/process execution is forbidden")
    return tests


def preserve_assertions(previous, candidate):
    """Conservative policy: no removal/change of existing asserts or raises contexts."""
    retain_tests(previous, candidate)
    current = {t.path: t for t in candidate}

    def checks(content):
        tree = ast.parse(content)
        return Counter(
            ast.dump(n, include_attributes=False)
            for n in ast.walk(tree)
            if isinstance(n, ast.Assert)
            or (isinstance(n, ast.Call) and ast.unparse(n.func) == "pytest.raises")
        )

    for old in previous:
        if checks(old.content) - checks(current[old.path].content):
            raise LLMOutputValidationError("Existing assertions changed; manual review required")
