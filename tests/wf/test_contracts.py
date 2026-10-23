import json

import pytest

from testpilot.config import LLMConfig
from testpilot.errors import LLMOutputValidationError
from testpilot.schemas.test_plan import GeneratedTest
from testpilot_wf.llm import EXECUTION_SYSTEM, GENERATION_SYSTEM, ExecutionLLM, GenerationLLM
from testpilot_wf.schemas import Category, Diagnosis
from testpilot_wf.validation import preflight, preserve_assertions


@pytest.mark.parametrize(
    "source",
    [
        "def test_x(:",
        "def test_x(): assert True",
        "def test_x(): pytest.skip()",
        "import pytest\n@pytest.mark.skip\ndef test_x(): assert f() == 1",
        "import pytest\n@pytest.mark.xfail\ndef test_x(): assert f() == 1",
        "import subprocess\ndef test_x(): assert f() == 1",
        "def test_x(): exec('anything')",
    ],
)
def test_preflight_rejects_invalid_or_unsafe(source):
    with pytest.raises(LLMOutputValidationError):
        preflight([GeneratedTest(path="test_x.py", content=source)])


@pytest.mark.parametrize(
    "new",
    [
        "def test_x(): assert f() >= 0",
        "def test_x(): pass",
        "def test_other(): assert f() == 1",
    ],
)
def test_assertion_retention(new):
    with pytest.raises(LLMOutputValidationError):
        preserve_assertions(
            [GeneratedTest(path="test_x.py", content="def test_x(): assert f() == 1")],
            [GeneratedTest(path="test_x.py", content=new)],
        )


class Model:
    def __init__(self, responses):
        self.responses, self.prompts = iter(responses), []

    def with_structured_output(self, schema, method):
        assert method == "json_mode"
        return self

    def invoke(self, messages, **kwargs):
        self.prompts.append(messages)
        value = next(self.responses)
        if isinstance(value, Exception):
            raise value
        return value


def diagnosis():
    return Diagnosis(
        failure_category=Category.PASS,
        suggested_action=Category.PASS,
        diagnosis="Actual passed tests and coverage verified",
        evidence_refs=["versions/001/execution.json"],
        review_required=False,
        uncertainty="Coverage cannot prove correctness",
    ).model_dump()


def test_execution_llm_has_separate_prompt_and_structured_retry():
    model = Model([{}, diagnosis()])
    client = ExecutionLLM(LLMConfig(), model=model, sleep=lambda _: None)
    assert client.diagnose("facts").failure_category == Category.PASS
    assert len(model.prompts) == 2
    assert model.prompts[0][0].content == EXECUTION_SYSTEM
    assert EXECUTION_SYSTEM != GENERATION_SYSTEM
    assert GenerationLLM.system_prompt == GENERATION_SYSTEM
    assert [c["status"] for c in client.diagnostics] == ["failed", "completed"]
    assert all(c["task"] == "DIAGNOSE" for c in client.diagnostics)


def test_execution_llm_temporary_timeout_retry():
    model = Model([TimeoutError(), diagnosis()])
    client = ExecutionLLM(LLMConfig(max_retries=1), model=model, sleep=lambda _: None)
    assert client.diagnose(json.dumps({"evidence": "facts"}))
    assert len(client.diagnostics) == 2
