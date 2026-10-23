"""Launch: python -m streamlit run testpilot_wf/ui.py"""

import json
from pathlib import Path

import streamlit as st

from testpilot.config import load_config
from testpilot.errors import TestPilotError
from testpilot.reporting.artifacts import redact
from testpilot.ui.results import downloads, generated_files, read_json
from testpilot_wf.service import run_project
from testpilot_wf.ui_state import (
    LABELS,
    NODES,
    TERMINAL,
    active_node,
    communication_rows,
    from_state,
    load_run,
    node_states,
    phase_label,
    timeline_rows,
)

ROOT = Path(__file__).resolve().parents[1]
PALETTE = {
    "PENDING": ("#f8fafc", "#cbd5e1"),
    "RUNNING": ("#eff6ff", "#0284c7"),
    "COMPLETED": ("#f0fdf4", "#16a34a"),
    "FAILED": ("#fef2f2", "#dc2626"),
    "REVIEW_REQUIRED": ("#fffbeb", "#d97706"),
}

# Streamlit's Graphviz theme applies a uniform rem font size to all SVG text,
# overriding Graphviz's font-size/font-family attributes and its measured alignment.
# Restore only the sizes used by this chart; do not affect other page typography.
WORKFLOW_FONT_CSS = """
<style>
[data-testid="stGraphVizChart"] svg text { font-family: Arial, sans-serif; }
[data-testid="stGraphVizChart"] svg text[font-size="18.00"] { font-size: 18px; }
[data-testid="stGraphVizChart"] svg text[font-size="12.00"] { font-size: 12px; }
[data-testid="stGraphVizChart"] svg text[font-size="11.00"] { font-size: 11px; }
[data-testid="stGraphVizChart"] svg text[font-size="10.00"] { font-size: 10px; }
</style>
"""


def workflow_dot(current="", *, states=None, active=None):
    """Use fixed node/status labels; project input never enters DOT syntax."""
    active = current if active is None else active
    states = states or {node: "RUNNING" if node == current else "PENDING" for node in NODES}
    subtitles = {
        "generation": "Generate · Repair · Improve",
        "execution": "Preflight · Execute · Diagnose",
        "controller": "Routing · Budgets",
        "report": "Final artifacts · No LLM",
    }
    nodes = []
    for node in NODES:
        status = states.get(node, "PENDING")
        status = status if status in PALETTE else "PENDING"
        fill, border = PALETTE[status]
        text_color = "#64748b" if status == "PENDING" else border
        group = "left" if node in {"generation", "controller"} else "right"
        nodes.append(
            f'{node} [group="{group}", fillcolor="{fill}", color="{border}", '
            f"penwidth={3 if node == active else 1.3}, "
            'label=<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="2">'
            f'<TR><TD ALIGN="CENTER"><FONT POINT-SIZE="18"><B>{LABELS[node]}</B></FONT></TD></TR>'
            f'<TR><TD ALIGN="CENTER"><FONT POINT-SIZE="12">{subtitles[node]}</FONT></TD></TR>'
            f'<TR><TD ALIGN="CENTER"><FONT POINT-SIZE="11" COLOR="{text_color}">'
            f"{status}</FONT></TD></TR></TABLE>>];"
        )
    return (
        """digraph workflow {
    graph [rankdir=TB, bgcolor="transparent", nodesep=0.55, ranksep=0.65, pad=0.2];
    node [shape=box, style="rounded,filled", fontname="Arial", fontsize=16, margin="0.2,0.16"];
    edge [fontname="Arial", fontsize=10, color="#64748b", arrowsize=0.7];
    """
        + "\n".join(nodes)
        + """
    {rank=same; generation; execution;}
    {rank=same; controller; report;}
    generation -> execution [label="test delivery"];
    execution -> controller [label="evidence + diagnosis"];
    controller -> report [label="FINISH / FAIL / REVIEW"];
    controller -> generation [style=dashed, color="#0284c7", fontcolor="#0284c7",
        label="REPAIR / IMPROVE\\nwithin budgets"];
    }"""
    )


def value(item):
    return "—" if item is None else redact(str(item))


def percentage(item):
    return "—" if item is None else f"{item:g}%"


def mode_label(demo):
    return {
        True: "DEMO · 固定响应，无真实模型调用",
        False: "Real DeepSeek 模式 · 调用状态见证据",
    }.get(demo, "运行模式未知")


def show_table(rows):
    safe = [
        {key: redact(cell) if isinstance(cell, str) else cell for key, cell in row.items()}
        for row in rows
    ]
    config = {}
    for name in safe[0] if safe else ():
        if name in {"顺序", "版本", "Repair", "Improve"}:
            config[name] = st.column_config.NumberColumn(alignment="center")
        elif name == "人工检查":
            config[name] = st.column_config.CheckboxColumn(alignment="center")
        else:
            width = {
                "任务 / 阶段": 240,
                "任务 / 反馈": 180,
                "建议动作": 180,
                "说明": 320,
                "摘要": "large",
            }.get(name)
            config[name] = st.column_config.TextColumn(alignment="center", width=width)
    st.dataframe(safe, hide_index=True, width="stretch", column_config=config)


def show_dashboard(view, *, final_check=False):
    status = view.get("status", "PENDING")
    st.caption(f"{mode_label(view.get('demo'))}  ·  Project: {value(view.get('project'))}")
    left, right = st.columns([1.8, 1], gap="large")
    with left:
        st.subheader("Workflow")
        st.graphviz_chart(
            workflow_dot(states=node_states(view), active=active_node(view)), width="stretch"
        )
        st.caption("灰：待执行  ·  蓝：执行中  ·  绿：节点完成  ·  红：失败  ·  琥珀：待检查")
    with right:
        st.subheader("Current Status")
        if status == "RUNNING":
            st.info("RUNNING · Workflow 执行中")
        elif status == "FINISH" and not view.get("report_ready"):
            st.info(
                "FINISH · Workflow 执行已完成。"
                if final_check
                else "FINISH · Workflow 执行已完成，正在生成最终报告。"
            )
        elif status in TERMINAL:
            reason = value(view.get("reason"))
            {"FINISH": st.success, "FAIL": st.error, "REVIEW_REQUIRED": st.warning}[status](
                f"{status}: {reason[:160]}" + ("…" if len(reason) > 160 else "")
            )
        else:
            st.info("PENDING · 尚未启动 Workflow")
        agent = "Report" if view.get("report_ready") else LABELS.get(view.get("current_agent"), "—")
        st.write(f"Current Agent: {agent}")
        st.write(f"Current Phase / Task: {phase_label(view)}")
        st.write(
            f"Repair: {value(view.get('repair_count'))} / {value(view.get('max_repair'))}  ·  "
            f"Improve: {value(view.get('coverage_round'))} / {value(view.get('max_improvement'))}"
        )
        # This slot is emitted on EVERY render. Otherwise a shorter final container can
        # retain its previous last child (the pre-report caption) in Streamlit's tree.
        report_notice = st.empty()
        if not view.get("report_ready"):
            if final_check and view.get("directory"):
                report_notice.error("报告异常：运行已结束，但最终报告缺失或无法读取。")
            elif status in TERMINAL:
                report_notice.caption("正在生成最终报告…")
    st.subheader("Execution Timeline")
    rows = timeline_rows(view)
    if rows:
        show_table(rows[-12:])
        if len(rows) > 12:
            with st.expander(f"查看全部历史（{len(rows)} 条）"):
                show_table(rows)
    else:
        st.caption("尚无执行记录。运行后按真实 Trace 顺序展示。")
    st.caption("内部阶段只来自实时 observer；持久化历史按 Trace 重建，Report 为 UI 产物记录。")
    st.subheader("Agent Communication")
    messages = view.get("messages", [])
    if messages:
        show_table(communication_rows(messages[-8:]))
        if len(messages) > 8:
            with st.expander(f"查看全部消息（{len(messages)} 条）"):
                show_table(communication_rows(messages))
        with st.expander("消息详情与 evidence_refs"):
            st.json(redact(json.dumps(messages, ensure_ascii=False)))
    else:
        st.caption("尚无 AgentMessage。Controller 路由仅显示在 Timeline。")
    for issue in view.get("issues", []):
        st.caption(issue)


def show_result(directory, report=None):
    report = report or read_json(directory, "final_report.json")
    st.subheader("Results & Artifacts")
    result, coverage = report.get("execution") or {}, report.get("coverage") or {}
    metrics = [
        (
            "Passed / Collected",
            f"{value(result.get('passed'))} / {value(result.get('collected_test_cases'))}",
        ),
        ("Failed / Errors", f"{value(result.get('failed'))} / {value(result.get('errors'))}"),
        ("Line Coverage", percentage(coverage.get("line_coverage"))),
        ("Branch Coverage", percentage(coverage.get("branch_coverage"))),
    ]
    for col, (label, content) in zip(st.columns(4), metrics, strict=True):
        col.metric(label, content)
    st.caption(
        f"Skipped: {value(result.get('skipped'))} · Return code: {value(result.get('returncode'))}"
    )
    with st.expander("终止原因与运行信息"):
        st.text(value(report.get("reason") or report.get("error")))
        st.text(str(directory))
    feedback = report.get("feedback") or {}
    if feedback:
        st.write(
            f"诊断: {value(feedback.get('failure_category'))} · "
            f"建议: {value(feedback.get('suggested_action'))} · "
            f"人工检查: {value(feedback.get('review_required'))}"
        )
        with st.expander("详细诊断与不确定性"):
            st.text(redact(feedback.get("diagnosis") or "—"))
            st.text(redact(feedback.get("uncertainty") or "—"))
    with st.container(horizontal=True):
        for label, filename, mime, data in downloads(directory):
            st.download_button(label, data, file_name=filename, mime=mime, on_click="ignore")
        path = directory / "messages.json"
        if path.is_file() and not path.is_symlink():
            st.download_button(
                "下载 Agent 消息",
                path.read_bytes(),
                file_name="agent-messages.json",
                mime="application/json",
                on_click="ignore",
            )
    for label, name in [
        ("Final Report", "final_report.json"),
        ("Agent Messages", "messages.json"),
        ("Execution Trace", "trace.json"),
        ("LLM Call Records", "llm_calls.json"),
        ("pytest Results", "execution_result.json"),
        ("Coverage Details", "coverage_result.json"),
        ("Test Plan", "test_plan.json"),
    ]:
        with st.expander(label):
            path = directory / name
            if path.is_file() and not path.is_symlink():
                try:
                    st.json(redact(path.read_text(encoding="utf-8")))
                except (OSError, UnicodeError):
                    st.caption("产物暂不可读取")
            else:
                st.caption("该历史产物不可用")
    with st.expander("Generated Tests"):
        for path in generated_files(directory):
            st.caption(path.name)
            st.code(redact(path.read_text(encoding="utf-8")), language="python")


def main():
    st.set_page_config(page_title="TestPilot-WF", page_icon="🧪", layout="wide")
    st.html(WORKFLOW_FONT_CSS)
    st.title("TestPilot-WF")
    st.caption("双 Agent 测试工作流 · 独立诊断 · 有界反馈循环")
    try:
        config = load_config()
    except TestPilotError as exc:
        st.error(redact(str(exc)))
        return
    with st.sidebar:
        st.header("运行配置")
        demo = st.checkbox("Demo（固定响应）", value=True)
        backend = st.selectbox("执行后端", ["docker", "local"])
        trusted = (
            st.checkbox("我确认 Local 输入代码可信", value=False) if backend == "local" else True
        )
        target = st.text_input("目标模块（留空为全部）")
        config.coverage.enabled = st.checkbox("检查覆盖率", value=config.coverage.enabled)
        config.coverage.line_threshold = st.slider(
            "行覆盖率目标", 0, 100, int(config.coverage.line_threshold)
        )
        config.coverage.branch_threshold = st.slider(
            "分支覆盖率目标", 0, 100, int(config.coverage.branch_threshold)
        )
        config.agent.max_repair_rounds = st.number_input(
            "最大修复轮数", 0, 10, config.agent.max_repair_rounds
        )
        config.coverage.max_improvement_rounds = st.number_input(
            "最大补测轮数", 0, 10, config.coverage.max_improvement_rounds
        )
        st.caption("Docker 不可用会保留失败报告。Local 不提供宿主隔离。")
    config.execution.preferred_runner = backend
    controls, action = st.columns([3, 1], vertical_alignment="bottom")
    with controls:
        example = st.selectbox(
            "项目", ["edge_cases", "basic", "multi_module", "advanced_project", "自定义路径"]
        )
        project = (
            st.text_input("项目路径")
            if example == "自定义路径"
            else str(ROOT / "examples" / example)
        )
    with action:
        start = st.button(
            "运行 Workflow", type="primary", disabled=not trusted or not project, width="stretch"
        )
    dashboard = st.empty()
    idle = {
        "demo": demo,
        "project": Path(project).name,
        "requested_backend": backend,
        "max_repair": config.agent.max_repair_rounds,
        "max_improvement": config.coverage.max_improvement_rounds,
    }

    def render(view, *, results=False, final_check=False):
        # A multi-element placeholder keeps unmatched children unless explicitly cleared.
        # In particular, a pre-report notification must not survive final rendering.
        dashboard.empty()
        with dashboard.container():
            show_dashboard(view, final_check=final_check)
            if results and view.get("report"):
                show_result(Path(view["directory"]), view["report"])

    if start:
        for key in ("wf_run", "wf_live"):
            st.session_state.pop(key, None)
        render(idle)

        def observe(state):
            view = from_state(state, config)
            if state.workflow_status in TERMINAL:
                view = load_run(state.run_dir, view)
            st.session_state["wf_live"] = view
            render(view)

        try:
            with st.spinner("Workflow 运行中"):
                state = run_project(
                    project,
                    config=config,
                    demo=demo,
                    target=target.strip() or None,
                    observer=observe,
                    output=ROOT / "runs",
                )
            st.session_state["wf_run"] = state.run_dir
        except (TestPilotError, OSError, ValueError) as exc:
            st.error(f"启动或产物读取失败: {redact(str(exc))}")
    if "wf_run" in st.session_state:
        view = load_run(st.session_state["wf_run"], st.session_state.get("wf_live"))
        st.session_state["wf_live"] = view
        render(
            view,
            results=True,
            final_check=True,
        )
    elif "wf_live" in st.session_state:
        view = st.session_state["wf_live"]
        if view.get("directory"):
            view = load_run(view["directory"], view)
            st.session_state["wf_live"] = view
        render(view, final_check=True)
    elif not start:
        render(idle)


if __name__ == "__main__":
    main()
