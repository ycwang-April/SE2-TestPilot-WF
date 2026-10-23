import json
from pathlib import Path

import pytest

from testpilot.config import AppConfig
from testpilot_wf.schemas import WorkflowState
from testpilot_wf.ui import workflow_dot
from testpilot_wf.ui_state import (
    active_node,
    communication_rows,
    from_state,
    load_run,
    node_states,
    phase_label,
    timeline_rows,
)

EVIDENCE = (
    Path(__file__).resolve().parents[2]
    / "docs/evidence/edge_cases-demo-docker-20261013-114413-c26ce206"
)


def test_initial_nodes_pending():
    assert set(node_states({}).values()) == {"PENDING"}
    assert active_node({}) == "" and timeline_rows({}) == []


@pytest.mark.parametrize(
    "agent,phase",
    [
        ("generation", "RUNNING"),
        ("execution", "PREFLIGHT"),
        ("execution", "EXECUTE"),
        ("execution", "DIAGNOSE"),
        ("controller", "RUNNING"),
    ],
)
def test_live_phase_highlight(agent, phase):
    state = WorkflowState(project_path="examples/basic", current_agent=agent, agent_phase=phase)
    view = from_state(state, AppConfig())
    assert active_node(view) == agent and node_states(view)[agent] == "RUNNING"
    assert node_states(view)["report"] == "PENDING"
    assert phase_label(view) == ("INITIAL_GENERATION" if agent == "generation" else phase)
    assert "observer" in timeline_rows(view)[-1]["说明"]


def test_completed_execution_is_not_workflow_finish():
    view = {
        "status": "RUNNING",
        "current_agent": "execution",
        "phase": "COMPLETED",
        "trace": [{"agent": "execution", "status": "COMPLETED", "test_version": 1}],
    }
    assert node_states(view)["execution"] == "COMPLETED"
    assert node_states(view)["report"] == "PENDING" and active_node(view) == ""


@pytest.mark.parametrize(
    "status,expected",
    [
        ("FINISH", "COMPLETED"),
        ("FAIL", "FAILED"),
        ("REVIEW_REQUIRED", "REVIEW_REQUIRED"),
    ],
)
def test_report_gate_and_terminal_color(tmp_path, status, expected):
    report = {"status": status, "reason": "Actual reason", "project": "sample", "demo": True}
    (tmp_path / "final_report.json").write_text(json.dumps(report), encoding="utf-8")
    view = load_run(tmp_path)
    assert not view["report_ready"] and node_states(view)["report"] == "PENDING"
    assert not any(r["节点"] == "Report" for r in timeline_rows(view))
    (tmp_path / "final_report.md").write_text("# Actual report", encoding="utf-8")
    view = load_run(tmp_path)
    assert view["report_ready"] and active_node(view) == "report"
    assert node_states(view)["report"] == expected
    assert timeline_rows(view)[-1]["状态"] == "FINALIZED"


def test_controller_terminal_without_report_does_not_finalize(tmp_path):
    view = load_run(tmp_path, {"status": "FAIL", "current_agent": "controller", "phase": "FAIL"})
    assert not view["report_ready"] and active_node(view) == ""
    assert node_states(view)["report"] == "PENDING"


def test_invalid_report_is_not_success(tmp_path):
    (tmp_path / "final_report.json").write_text("not JSON", encoding="utf-8")
    (tmp_path / "final_report.md").write_text("# Partial", encoding="utf-8")
    view = load_run(tmp_path)
    assert not view["report_ready"] and view["report"] is None
    assert view["issues"] and active_node(view) == ""


def test_actual_loop_history_and_messages_rebuilt_from_artifacts():
    view = load_run(EVIDENCE)
    rows = timeline_rows(view)
    assert len(rows) == len(view["trace"]) + 1 == 10
    assert [r["任务 / 阶段"] for r in rows if r["节点"] == "Generation Agent"] == [
        "INITIAL_GENERATION",
        "REPAIR_TESTS",
        "IMPROVE_COVERAGE",
    ]
    assert [r["任务 / 阶段"] for r in rows if r["节点"] == "Controller"] == [
        "REPAIR_TESTS",
        "IMPROVE_COVERAGE",
        "FINISH",
    ]
    assert rows[-1]["节点"] == "Report" and active_node(view) == "report"
    assert node_states(view)["controller"] == "COMPLETED"
    messages = communication_rows(view["messages"])
    assert [r["顺序"] for r in messages] == list(range(1, 7))
    assert [r["版本"] for r in messages] == [1, 1, 2, 2, 3, 3]
    assert all("Controller" not in r["方向"] for r in messages)
    assert "Execution Agent → Generation Agent" == messages[1]["方向"]
    assert messages[1]["任务 / 反馈"] == "REPAIR_TEST"


def test_controller_visit_is_not_duplicated_as_live_event():
    view = {
        "status": "RUNNING",
        "current_agent": "controller",
        "phase": "RUNNING",
        "trace": [
            {"agent": "controller", "decision": {"mode": "REPAIR_TESTS", "route": "generation"}}
        ],
    }
    assert len(timeline_rows(view)) == 1 and active_node(view) == "controller"


def test_dot_only_contains_fixed_labels():
    malicious = '"]; injected [label="attacker"] //'
    dot = workflow_dot(malicious, states={"generation": malicious, malicious: "RUNNING"})
    assert "injected" not in dot and "attacker" not in dot
    assert 'style="rounded,filled"' in dot and "style=dashed" in dot
    assert "No LLM" in dot and "<B>Generation Agent</B>" in dot
    assert dot.count('ALIGN="CENTER"') == 12
    assert dot.count('POINT-SIZE="18"') == 4
    assert dot.count('POINT-SIZE="12"') == 4
    assert dot.count('POINT-SIZE="11"') == 4


def test_failure_retains_node_error_and_does_not_turn_other_nodes_red():
    view = {
        "status": "FAIL",
        "report_ready": True,
        "trace": [
            {"agent": "generation", "status": "ERROR"},
            {"agent": "controller", "decision": {"workflow_status": "FAIL"}},
        ],
    }
    states = node_states(view)
    assert states == {
        "generation": "FAILED",
        "execution": "PENDING",
        "controller": "COMPLETED",
        "report": "FAILED",
    }
