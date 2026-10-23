import json
from pathlib import Path

import pytest

from testpilot.errors import LLMError, LLMOutputValidationError, LLMTimeoutError
from testpilot.llm.fake import BASIC, bundle
from testpilot.reporting.artifacts import ArtifactWriter
from testpilot_wf.agents import GenerationAgent
from testpilot_wf.demo import DemoGeneration
from testpilot_wf.schemas import Mode, WorkflowState
from testpilot_wf.validation import digest
from tests.wf.test_workflow import run


class InitialClient(DemoGeneration):
    def __init__(self, candidates):
        self.candidates = iter(candidates)
        self.contexts = []
        self.plans = 0

    def plan(self, context):
        self.plans += 1
        return super().plan(context)

    def generate(self, context, plan):
        self.contexts.append(json.loads(context))
        candidate = next(self.candidates)
        if isinstance(candidate, Exception):
            raise candidate
        return bundle("test_calculator.py", candidate)


def records(state):
    return [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted((Path(state.run_dir) / "rejected").glob("*-attempt-*.json"))
    ]


def test_first_valid_no_extra_call(example_root, local_config, tmp_path):
    client = InitialClient([BASIC])
    state = run(example_root, local_config, tmp_path, generation_client=client)
    assert state.workflow_status == "FINISH"
    assert len(client.contexts) == client.plans == 1
    assert "validation_feedback" not in client.contexts[0]
    assert not records(state)


@pytest.mark.parametrize(
    "bad",
    [
        "def test_bad(:\n",
        "import subprocess\n" + BASIC,
        "import pytest\n@pytest.mark.skipif(True, reason='bad')\n"
        + "def test_bad(): assert f() == 1\n",
    ],
)
def test_one_correction_commits_once(example_root, local_config, tmp_path, bad):
    client = InitialClient([bad, BASIC])
    state = run(example_root, local_config, tmp_path, generation_client=client)
    assert state.workflow_status == "FINISH", state.reason
    assert len(client.contexts) == 2 and client.plans == 1
    feedback = client.contexts[1]["validation_feedback"]
    assert feedback["source"] == "generation_preflight"
    assert feedback["files"] == ["test_calculator.py"]
    assert feedback["error"] == records(state)[0]["validation_feedback"]["error"]
    if bad.startswith("def"):
        assert feedback["line"] == 1 and "SyntaxError" in feedback["error"]
    assert client.contexts[1]["existing_tests"] == []
    assert client.contexts[1]["execution_agent_feedback"] is None
    assert state.test_version == 1 and state.test_digest == digest(state.generated_tests)
    assert state.repair_count == state.coverage_round == 0
    assert len(state.messages) == 2 and state.execution_result.passed == 7
    assert len(records(state)) == 1 and not records(state)[0]["accepted"]
    refs = state.trace[0]["evidence_refs"]
    accepted = next(ref for ref in refs if ref.endswith("accepted-02.json"))
    assert json.loads((Path(state.run_dir) / accepted).read_text(encoding="utf-8"))["accepted"]


def test_two_invalid_candidates_stop_and_redact(example_root, local_config, tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "private-preflight-sentinel")
    bad = "# private-preflight-sentinel\ndef test_bad(:\n"
    client = InitialClient([bad, bad, BASIC])
    state = run(example_root, local_config, tmp_path, generation_client=client)
    assert state.workflow_status == "FAIL" and "2 candidate attempts" in state.reason
    assert len(client.contexts) == 2 and state.test_version == 0
    assert state.generated_tests == [] and state.messages == []
    assert state.execution_result is None
    rejected = records(state)
    assert [r["attempt"] for r in rejected] == [1, 2]
    assert all(not r["accepted"] for r in rejected)
    assert len(list((Path(state.run_dir) / "rejected").glob("*.json"))) == 2
    for path in (Path(state.run_dir) / "rejected").glob("*.json"):
        assert "private-preflight-sentinel" not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "error",
    [
        LLMError("API failed"),
        LLMTimeoutError("timeout"),
        LLMOutputValidationError("adapter rejected"),
        RuntimeError("bug"),
    ],
)
def test_model_errors_not_locally_retried(example_root, local_config, tmp_path, error):
    client = InitialClient([error, BASIC])
    state = run(example_root, local_config, tmp_path, generation_client=client)
    assert state.workflow_status == "FAIL" and len(client.contexts) == 1
    assert not records(state)


def test_analysis_failure_never_generates(local_config, tmp_path):
    client = InitialClient([BASIC])
    from testpilot_wf.service import run_project

    state = run_project(
        tmp_path / "missing",
        demo=True,
        config=local_config,
        generation_client=client,
        output=tmp_path / "runs",
    )
    assert state.workflow_status == "FAIL" and client.contexts == []


@pytest.mark.parametrize("mode", [Mode.REPAIR, Mode.IMPROVE])
def test_feedback_modes_retry_without_polluting_state(example_root, local_config, tmp_path, mode):
    class Client(DemoGeneration):
        contexts = []

        def repair(self, context):
            result = super().repair(context)
            if mode == Mode.REPAIR:
                self.contexts.append(json.loads(context))
                if len(self.contexts) == 1:
                    result.files[0].content = "import subprocess\n" + result.files[0].content
            return result

        def improve(self, context):
            result = super().improve(context)
            if mode == Mode.IMPROVE:
                self.contexts.append(json.loads(context))
                if len(self.contexts) == 1:
                    result.files[0].content = "def test_extra(:\n"
            return result

    client = Client()
    state = run(example_root, local_config, tmp_path, "edge_cases", generation_client=client)
    assert state.workflow_status == "FINISH", state.reason
    assert len(client.contexts) == 2
    first, second = client.contexts
    assert first["existing_tests"] == second["existing_tests"]
    assert first["execution_agent_feedback"] == second["execution_agent_feedback"]
    assert first["execution"] == second["execution"]
    assert second["validation_feedback"]["source"] == "generation_preflight"
    assert state.repair_count == state.coverage_round == 1
    assert state.test_version == 3 and state.execution_result.passed == 9
    assert [m.test_version for m in state.messages] == [1, 1, 2, 2, 3, 3]
    assert state.test_digest == digest(state.generated_tests)
    if mode == Mode.REPAIR:
        root = Path(state.run_dir)
        assert list(root.glob("repairs/01/*/attempt-01.json"))
        assert list(root.glob("generation_attempts/*/02/repairs/01/*/attempt-01.json"))


def test_assertion_violation_precedes_preflight_retry(example_root, local_config, tmp_path):
    class Client(DemoGeneration):
        calls = 0

        def repair(self, context):
            self.calls += 1
            result = super().repair(context)
            result.files[0].content = "import subprocess\n" + result.files[0].content.replace(
                "== 5", ">= 0"
            )
            return result

    client = Client()
    state = run(example_root, local_config, tmp_path, "edge_cases", generation_client=client)
    assert state.workflow_status == "FAIL" and client.calls == 1
    assert state.test_version == 1 and "== 5" in state.generated_tests[0].content
    assert not records(state)


def test_state_input_is_unchanged_after_correction(example_root, local_config, tmp_path):
    state = WorkflowState(project_path=str(example_root / "basic"), demo=True)
    before = state.model_dump()
    client = InitialClient(["def test_bad(:\n", BASIC])
    result = GenerationAgent(local_config, ArtifactWriter(tmp_path), client).invoke(state)
    assert state.model_dump() == before
    assert result["test_version"] == 1 and len(result["messages"]) == 1
    assert "repair_count" not in result and "coverage_round" not in result


def test_real_adapter_receives_feedback_in_model_messages(example_root, local_config, tmp_path):
    from testpilot_wf.llm import GenerationLLM
    from tests.wf.test_contracts import Model

    context = json.dumps(
        {
            "targets": ["calculator.py"],
            "source": {
                "calculator.py": (example_root / "basic/calculator.py").read_text(encoding="utf-8")
            },
        }
    )
    plan = DemoGeneration().plan(context)
    model = Model(
        [
            plan,
            bundle("test_calculator.py", "def test_bad(:\n"),
            bundle("test_calculator.py", BASIC),
        ]
    )
    client = GenerationLLM(local_config.llm, model=model, sleep=lambda _: None)
    state = run(example_root, local_config, tmp_path, generation_client=client)
    assert state.workflow_status == "FINISH"
    assert len(model.prompts) == 3  # One plan, two generation calls; no adapter retries.
    assert "generation_preflight" not in model.prompts[1][1].content
    assert '"source": "generation_preflight"' in model.prompts[2][1].content
    assert "SyntaxError line 1" in model.prompts[2][1].content


def test_stale_state_does_not_call_model(local_config, tmp_path):
    client = InitialClient([BASIC])
    state = WorkflowState(project_path=str(tmp_path), mode=Mode.REPAIR)
    with pytest.raises(LLMOutputValidationError, match="Stale"):
        GenerationAgent(local_config, ArtifactWriter(tmp_path), client).invoke(state)
    assert client.contexts == [] and client.plans == 0


def test_second_candidate_cannot_bypass_assertion_protection(example_root, local_config, tmp_path):
    class Client(DemoGeneration):
        calls = 0

        def repair(self, context):
            self.calls += 1
            result = super().repair(context)
            if self.calls == 1:
                result.files[0].content = "import subprocess\n" + result.files[0].content
            else:
                result.files[0].content = result.files[0].content.replace("== 5", ">= 0")
            return result

    client = Client()
    state = run(example_root, local_config, tmp_path, "edge_cases", generation_client=client)
    assert state.workflow_status == "FAIL" and client.calls == 2
    assert state.test_version == 1 and state.repair_count == 1
    assert len(state.messages) == 2 and "== 5" in state.generated_tests[0].content
    assert "Existing assertions changed" in state.error
