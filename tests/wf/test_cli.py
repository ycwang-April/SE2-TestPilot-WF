import builtins
import json
from pathlib import Path

import pytest

from testpilot.config import AppConfig
from testpilot_wf import cli
from testpilot_wf.schemas import WorkflowState
from testpilot_wf.service import run_project


@pytest.mark.parametrize("example,rounds", [("basic", 1), ("edge_cases", 3)])
def test_cli_live_demo_phases_loops_messages_and_duplicate_observers(
    example_root, tmp_path, monkeypatch, capsys, example, rounds
):
    chunks, completed = [], []

    def run_with_duplicates(project, *, observer, **kwargs):
        assert observer is not None

        def notify(state):
            before = state.model_dump_json()
            observer(state)
            chunk = capsys.readouterr().out
            chunks.append(chunk)
            # Output is already available inside the callback, before run_project returns.
            assert "[Report] FINALIZED" not in chunk
            if state.current_agent == "generation" and state.agent_phase == "RUNNING":
                assert "[Generation Agent] START | Task:" in chunk
            if state.current_agent == "execution" and state.agent_phase == "EXECUTE":
                assert "[Execution Agent] EXECUTE | pytest" in chunk
            observer(state.model_copy(deep=True))
            assert capsys.readouterr().out == ""
            assert state.model_dump_json() == before

        state = run_project(project, observer=notify, **kwargs)
        completed.append(state)
        return state

    monkeypatch.setattr(cli, "run_project", run_with_duplicates)
    assert (
        cli.main(
            [str(example_root / example), "--demo", "--runner", "local", "--output", str(tmp_path)]
        )
        == 0
    )
    text = "".join(chunks) + capsys.readouterr().out
    state = completed[0]
    assert "[Workflow] START" in text and f"[Project] {example}" in text
    assert "[Mode] DEMO (fixed responses; no LLM calls; real pytest)" in text
    assert "[Runner] local (requested)" in text and "Backend: local" in text
    for agent in ("Generation", "Execution"):
        assert text.count(f"[{agent} Agent] START") == rounds
        assert text.count(f"[{agent} Agent] COMPLETED") == rounds
    for phase in ("PREFLIGHT", "EXECUTE", "DIAGNOSE"):
        assert text.count(f"[Execution Agent] {phase}") == rounds
    lines = [line for line in text.splitlines() if line.startswith("[Communication]")]
    assert len(lines) == len(state.messages) == rounds * 2
    for line, message in zip(lines, state.messages, strict=True):
        assert f"{message.sender.title()} -> {message.receiver.title()}" in line
        assert message.message_type in line and line.endswith(f"v{message.test_version}")
        if message.message_type == "execution_feedback":
            assert str(message.payload.failure_category) in line
    if rounds == 3:
        for decision in ("REPAIR_TESTS | Repair: 1/2", "IMPROVE_COVERAGE | Improve: 1/2"):
            assert text.count(f"[Controller] Decision: {decision}") == 1
        for version in (1, 2, 3):
            assert f"[Generation Agent] COMPLETED | Test Version: v{version}" in text
        assert state.repair_count == state.coverage_round == 1
    else:
        assert "REPAIR_TESTS" not in text and "IMPROVE_COVERAGE" not in text
    assert text.count("[Controller] Decision: FINISH") == 1
    assert text.count("[Report] FINALIZED") == 1
    assert text.index("[Controller] Decision: FINISH") < text.index("[Report] FINALIZED")
    assert f"Artifacts: {state.run_dir}" in text
    assert text.index("[Report] FINALIZED") < text.index("\nFINISH:")
    assert "ANALYZE" not in text and "PLAN" not in text


def install_terminal_run(monkeypatch, tmp_path, status="FINISH", reason="Mock final result"):
    state = WorkflowState(
        project_path="examples/basic",
        run_dir=str(tmp_path),
        workflow_status=status,
        reason=reason,
        current_agent="controller",
        agent_phase=status,
        test_version=1,
        trace=[
            {
                "step": 3,
                "agent": "controller",
                "decision": {"workflow_status": status, "route": "end"},
            }
        ],
    )
    (tmp_path / "final_report.json").write_text(
        json.dumps({"status": status, "test_version": 1}), encoding="utf-8"
    )
    (tmp_path / "final_report.md").write_text("# Mock report", encoding="utf-8")
    calls = []

    def fake_run(project, *, observer, **kwargs):
        calls.append((project, kwargs, observer))
        if observer:
            observer(state)
            observer(state.model_copy(deep=True))
        return state

    monkeypatch.setattr(cli, "run_project", fake_run)
    return state, calls


@pytest.mark.parametrize("status,code", [("FINISH", 0), ("FAIL", 1), ("REVIEW_REQUIRED", 2)])
def test_cli_terminal_status_and_exit_codes(tmp_path, monkeypatch, capsys, status, code):
    install_terminal_run(monkeypatch, tmp_path, status)
    assert cli.main(["examples/basic"]) == code
    text = capsys.readouterr().out
    assert "[Mode] REAL DEEPSEEK" in text  # Mock run; no actual model is constructed.
    assert text.count(f"[Controller] Decision: {status}") == 1
    assert "[Report] FINALIZED" in text
    assert f"{status}: Mock final result\nArtifacts: {tmp_path}" in text


@pytest.mark.parametrize(
    "problem",
    [
        "missing_json",
        "missing_markdown",
        "invalid_json",
        "wrong_status",
        "wrong_version",
        "empty_markdown",
        "unreadable_markdown",
    ],
)
def test_cli_never_finalizes_missing_or_inconsistent_report(tmp_path, monkeypatch, capsys, problem):
    state, _ = install_terminal_run(monkeypatch, tmp_path)
    path = tmp_path / "final_report.json"
    markdown = tmp_path / "final_report.md"
    if problem == "missing_json":
        path.unlink()
    elif problem == "missing_markdown":
        markdown.unlink()
    elif problem == "invalid_json":
        path.write_text("{", encoding="utf-8")
    elif problem in {"wrong_status", "wrong_version"}:
        path.write_text(
            json.dumps(
                {
                    "status": "FAIL" if problem == "wrong_status" else "FINISH",
                    "test_version": 9 if problem == "wrong_version" else 1,
                }
            ),
            encoding="utf-8",
        )
    elif problem == "empty_markdown":
        markdown.write_text("", encoding="utf-8")
    else:
        markdown.write_bytes(b"\xff")
    assert cli.main(["examples/basic"]) == 1
    text = capsys.readouterr().out
    assert "[Report] FINALIZED" not in text
    assert "[Report] ERROR" in text
    assert "FAIL: Final report error; Workflow result: FINISH" in text
    assert state.workflow_status == "FINISH"  # Presentation failure never mutates the Workflow.


def test_quiet_and_existing_cli_arguments(tmp_path, monkeypatch, capsys):
    _, calls = install_terminal_run(monkeypatch, tmp_path)
    config_files = []

    def load(path):
        config_files.append(path)
        return AppConfig()

    monkeypatch.setattr(cli, "load_config", load)
    assert (
        cli.main(
            [
                "examples/basic",
                "--quiet",
                "--demo",
                "--runner",
                "local",
                "--config",
                "selected.yaml",
                "--target",
                "calculator.py",
                "--output",
                str(tmp_path),
                "--max-repair",
                "3",
                "--max-improvement",
                "4",
                "--line-threshold",
                "85",
                "--branch-threshold",
                "75",
                "--no-coverage",
            ]
        )
        == 0
    )
    text = capsys.readouterr().out
    assert text == f"FINISH: Mock final result\nArtifacts: {tmp_path}\n"
    project, kwargs, observer = calls[0]
    assert project == "examples/basic" and observer is None and kwargs["demo"] is True
    assert kwargs["target"] == "calculator.py" and kwargs["output"] == str(tmp_path)
    assert config_files == ["selected.yaml"]
    config = kwargs["config"]
    assert config.execution.preferred_runner == "local"
    assert config.agent.max_repair_rounds == 3
    assert config.coverage.max_improvement_rounds == 4
    assert config.coverage.line_threshold == 85 and config.coverage.branch_threshold == 75
    assert config.coverage.enabled is False


def test_progress_flushes_and_does_not_dump_sensitive_payload(tmp_path, monkeypatch):
    secret = "mock-private-key-123456"
    monkeypatch.setenv("CLI_TEST_SECRET", secret)
    install_terminal_run(monkeypatch, tmp_path, reason=f"Diagnosis {secret}\n" + "details " * 200)
    printed = []
    monkeypatch.setattr(builtins, "print", lambda *args, **kwargs: printed.append((args, kwargs)))
    assert cli.main(["examples/basic"]) == 0
    assert printed and all(kwargs.get("flush") is True for _, kwargs in printed)
    text = "\n".join(str(args[0]) for args, _ in printed)
    assert secret not in text and "[REDACTED]" in text
    assert "... (see artifacts)" in text and len(text) < 1000


def test_configuration_error_does_not_start_workflow(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid configuration must not start a Workflow")

    monkeypatch.setattr(cli, "run_project", forbidden)
    assert cli.main(["examples/basic", "--max-repair", "-1"]) == 1
    text = capsys.readouterr().out
    assert "Configuration/input error" in text
    assert "[Workflow] START" not in text


def test_report_write_exception_is_safe_failure(tmp_path, monkeypatch, capsys):
    def failed(project, *, observer, **kwargs):
        observer(
            WorkflowState(project_path=project, current_agent="generation", agent_phase="RUNNING")
        )
        raise OSError("Mock report write failure")

    monkeypatch.setattr(cli, "run_project", failed)
    assert cli.main(["examples/basic", "--demo", "--output", str(tmp_path)]) == 1
    text = capsys.readouterr().out
    assert "[Generation Agent] START" in text
    assert "FAIL: Workflow/artifact I/O error: OSError" in text
    assert "FINALIZED" not in text


def test_cli_process_entrypoint_supports_quiet(tmp_path):
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "testpilot_wf",
            "examples/basic",
            "--demo",
            "--runner",
            "local",
            "--quiet",
            "--output",
            str(tmp_path),
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("FINISH:") and "Artifacts:" in result.stdout
    assert "[Generation Agent]" not in result.stdout
