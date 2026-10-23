"""Read-only projections of existing state and artifacts; no workflow mutations."""

import json
from pathlib import Path

TERMINAL = {"FINISH", "FAIL", "REVIEW_REQUIRED"}
NODES = ("generation", "execution", "controller", "report")
LABELS = {
    "generation": "Generation Agent",
    "execution": "Execution Agent",
    "controller": "Controller",
    "report": "Report",
}


def from_state(state, config):
    return {
        "directory": state.run_dir,
        "project": Path(state.project_path).name,
        "demo": state.demo,
        "status": state.workflow_status,
        "current_agent": state.current_agent,
        "phase": state.agent_phase,
        "mode": str(state.mode),
        "test_version": state.test_version,
        "repair_count": state.repair_count,
        "coverage_round": state.coverage_round,
        "max_repair": config.agent.max_repair_rounds,
        "max_improvement": config.coverage.max_improvement_rounds,
        "backend": state.execution_result.backend if state.execution_result else None,
        "requested_backend": config.execution.preferred_runner,
        "reason": state.reason or state.error,
        "trace": state.trace,
        "messages": [m.model_dump(mode="json") for m in state.messages],
        "report_ready": False,
        "report": None,
        "issues": [],
    }


def load_run(directory, fallback=None):
    """Controller terminal state alone is not proof that reporting has finished."""
    directory = Path(directory)
    view, issues = dict(fallback or {}), []

    def read(name, kind):
        path = directory / name
        if not path.is_file() or path.is_symlink():
            issues.append(f"{name} 尚未生成或不可读取")
            return kind()
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, kind):
                raise ValueError("unexpected artifact type")
            return value
        except (OSError, UnicodeError, ValueError):
            issues.append(f"{name} 无法解析")
            return kind()

    trace, messages = read("trace.json", list), read("messages.json", list)
    report = read("final_report.json", dict)
    valid = report.get("status") in TERMINAL
    ready = (
        valid
        and (directory / "final_report.md").is_file()
        and not (directory / "final_report.md").is_symlink()
    )
    if valid:
        config = report.get("config") or {}
        view.update(
            project=report.get("project"),
            demo=report.get("demo"),
            status=report["status"],
            test_version=report.get("test_version"),
            repair_count=report.get("repair_rounds"),
            coverage_round=report.get("coverage_rounds"),
            max_repair=config.get("agent", {}).get("max_repair_rounds"),
            max_improvement=config.get("coverage", {}).get("max_improvement_rounds"),
            requested_backend=config.get("execution", {}).get("preferred_runner"),
            backend=report.get("execution_backend"),
            reason=report.get("reason") or report.get("error"),
            current_agent="report" if ready else "",
            phase="FINALIZED" if ready else "REPORT_PENDING",
        )
    view.update(
        directory=str(directory),
        trace=trace,
        messages=messages,
        report=report if valid else None,
        report_ready=ready,
        issues=issues,
    )
    return view


def active_node(view):
    if view.get("report_ready") and view.get("status") in TERMINAL:
        return "report"
    if view.get("status") != "RUNNING":
        return ""
    current = view.get("current_agent")
    if current in NODES and view.get("phase") in {"RUNNING", "PREFLIGHT", "EXECUTE", "DIAGNOSE"}:
        return current
    return ""


def node_states(view):
    states = dict.fromkeys(NODES, "PENDING")
    for event in view.get("trace", []):
        agent = event.get("agent")
        if agent in states:
            states[agent] = (
                "COMPLETED"
                if agent == "controller"
                else {"ERROR": "FAILED", "COMPLETED": "COMPLETED"}.get(
                    event.get("status"), "PENDING"
                )
            )
    active = active_node(view)
    if active and active != "report":
        states[active] = "RUNNING"
    if active == "report":
        states["report"] = {
            "FINISH": "COMPLETED",
            "FAIL": "FAILED",
            "REVIEW_REQUIRED": "REVIEW_REQUIRED",
        }[view["status"]]
    return states


def phase_label(view):
    if view.get("current_agent") == "generation":
        return view.get("mode") or "—"
    return view.get("phase") or "—"


def timeline_rows(view):
    rows, terminal_seen = [], False
    for index, event in enumerate(view.get("trace", []), 1):
        decision = event.get("decision") or {}
        terminal = decision.get("workflow_status") in TERMINAL
        terminal_seen |= terminal
        controller = event.get("agent") == "controller"
        rows.append(
            {
                "顺序": event.get("step", index),
                "节点": LABELS.get(event.get("agent"), event.get("agent", "—")),
                "任务 / 阶段": (decision.get("mode") or decision.get("workflow_status") or "ROUTE")
                if controller
                else event.get("task", "—"),
                "版本": event.get("test_version"),
                "状态": ("END" if terminal else "ROUTE")
                if controller
                else event.get("status", "—"),
                "Repair": event.get("repair_count"),
                "Improve": event.get("coverage_round"),
                "说明": decision.get("reason")
                or event.get("error")
                or (f"route → {decision['route']}" if decision.get("route") else "Trace"),
            }
        )
    active = active_node(view)
    controller_recorded = active == "controller" and rows and rows[-1]["节点"] == "Controller"
    if active not in {"", "report"} and not controller_recorded:
        rows.append(
            {
                "顺序": len(rows) + 1,
                "节点": LABELS[active],
                "任务 / 阶段": phase_label(view),
                "版本": view.get("test_version"),
                "状态": "RUNNING",
                "Repair": view.get("repair_count"),
                "Improve": view.get("coverage_round"),
                "说明": "实时 observer，尚未写入 Trace",
            }
        )
    if view.get("status") in TERMINAL and not terminal_seen:
        rows.append(
            {
                "顺序": len(rows) + 1,
                "节点": "Workflow",
                "任务 / 阶段": view["status"],
                "版本": view.get("test_version"),
                "状态": "END",
                "Repair": view.get("repair_count"),
                "Improve": view.get("coverage_round"),
                "说明": view.get("reason") or "终态来自最终报告 / observer",
            }
        )
    if view.get("report_ready"):
        rows.append(
            {
                "顺序": len(rows) + 1,
                "节点": "Report",
                "任务 / 阶段": view["status"],
                "版本": view.get("test_version"),
                "状态": "FINALIZED",
                "Repair": view.get("repair_count"),
                "Improve": view.get("coverage_round"),
                "说明": "final_report.json + final_report.md 已生成（UI 产物记录）",
            }
        )
    return rows


def communication_rows(messages):
    return [
        {
            "顺序": message.get("sequence"),
            "方向": f"{LABELS.get(message.get('sender'), message.get('sender', '—'))} → "
            f"{LABELS.get(message.get('receiver'), message.get('receiver', '—'))}",
            "消息类型": message.get("message_type"),
            "版本": message.get("test_version"),
            "任务 / 反馈": message.get("payload", {}).get("mode")
            or message.get("payload", {}).get("failure_category", "—"),
            "摘要": (
                message.get("payload", {}).get("summary")
                or message.get("payload", {}).get("diagnosis")
                or "—"
            )[:180],
            "建议动作": message.get("payload", {}).get("suggested_action", "—"),
            "人工检查": message.get("payload", {}).get("review_required"),
        }
        for message in messages
    ]
