import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from testpilot_wf.ui_state import load_run, timeline_rows

UI = Path(__file__).resolve().parents[2] / "testpilot_wf/ui.py"


def graph_text(app):
    return app.get("graphviz_chart")[0].proto.spec


def assert_compact_current_status(app):
    assert not {"当前测试集版本", "执行后端"} & {m.label for m in app.metric}
    assert not any("首次生成记为" in c.value or "请求后端" in c.value for c in app.caption)


def assert_no_report_pending(app):
    assert not any("正在生成最终报告" in item.value for item in [*app.caption, *app.info])


def test_wf_initial_page_is_pending():
    app = AppTest.from_file(str(UI)).run()
    assert not app.exception
    assert len(app.get("graphviz_chart")) == 1
    assert "RUNNING" not in graph_text(app)
    assert not app.success
    assert any("PENDING" in x.value for x in app.info)
    assert_compact_current_status(app)
    # DOT sizes alone are insufficient: Streamlit's theme overrides SVG attributes.
    # The page must also emit the narrowly scoped restoration stylesheet.
    stylesheet = app.get("html")[0].proto.body
    assert '[data-testid="stGraphVizChart"] svg text' in stylesheet
    assert "font-family: Arial, sans-serif" in stylesheet
    for size in (18, 12, 11):
        assert f'text[font-size="{size}.00"] {{ font-size: {size}px; }}' in stylesheet
    app.run()
    assert app.get("html")[0].proto.body == stylesheet
    assert {x.value for x in app.subheader} >= {
        "Execution Timeline",
        "Agent Communication",
        "Current Status",
    }


def saved_report(directory, status="FINISH", demo=True, trace=None):
    directory.mkdir(parents=True, exist_ok=True)
    trace = trace or [
        {
            "step": 1,
            "agent": "controller",
            "test_version": 1,
            "decision": {"workflow_status": status, "route": "end"},
        }
    ]
    report = {
        "project": "Mock UI fixture",
        "status": status,
        "demo": demo,
        "reason": "Mock result requiring inspection"
        if status != "FINISH"
        else "Mock completed run",
        "test_version": 1,
        "repair_rounds": 0,
        "coverage_rounds": 0,
        "execution_backend": "not executed",
        "execution": None,
        "coverage": None,
        "model_calls": [],
        "feedback": {
            "failure_category": status,
            "diagnosis": "Mock diagnostic details",
            "uncertainty": "Mock, no real API request",
            "suggested_action": status,
            "review_required": status == "REVIEW_REQUIRED",
        },
    }
    for name, data in (("final_report.json", report), ("trace.json", trace), ("messages.json", [])):
        (directory / name).write_text(json.dumps(data), encoding="utf-8")
    (directory / "final_report.md").write_text("# Mock UI report", encoding="utf-8")
    return report


@pytest.mark.parametrize(
    "status,color", [("FINISH", "#16a34a"), ("FAIL", "#dc2626"), ("REVIEW_REQUIRED", "#d97706")]
)
@pytest.mark.parametrize("demo", [True, False])
def test_saved_terminal_modes_and_rerender(tmp_path, status, color, demo):
    saved_report(tmp_path, status, demo)
    app = AppTest.from_file(str(UI))
    app.session_state["wf_run"] = str(tmp_path)
    app.run()
    assert not app.exception
    assert f'color="{color}", penwidth=3' in graph_text(app)
    assert "RUNNING" not in graph_text(app)
    alerts = {"FINISH": app.success, "FAIL": app.error, "REVIEW_REQUIRED": app.warning}[status]
    assert any(status in a.value for a in alerts)
    if status != "FINISH":
        assert not app.success
        assert "Mock result requiring inspection" in alerts[0].value
    else:
        assert not app.warning and not app.error
    assert (
        any("固定响应" in c.value for c in app.caption)
        if demo
        else any("Real DeepSeek 模式" in c.value for c in app.caption)
    )
    assert next(m for m in app.metric if m.label == "Line Coverage").value == "—"
    assert next(m for m in app.metric if m.label == "Passed / Collected").value == "— / —"
    assert app.dataframe[0].value.iloc[-1]["状态"] == "FINALIZED"
    assert "Mock diagnostic details" in [t.value for t in app.text]
    app.run()
    assert not app.exception and "Current Agent: Report" in [x.value for x in app.markdown]
    assert_no_report_pending(app)
    if status == "FINISH":
        assert not app.warning and not app.error


def test_observer_phases_and_report_file_boundary(tmp_path, monkeypatch):
    import streamlit as st

    from testpilot_wf.schemas import WorkflowState
    from testpilot_wf.ui_state import active_node, phase_label

    captured = []

    def fake_run(project, *, config, observer, demo, **kwargs):
        assert "wf_run" not in st.session_state and "wf_live" not in st.session_state
        state = WorkflowState(project_path=str(project), run_dir=str(tmp_path), demo=demo)

        def notify():
            (tmp_path / "trace.json").write_text(json.dumps(state.trace), encoding="utf-8")
            (tmp_path / "messages.json").write_text("[]", encoding="utf-8")
            observer(state)
            view = st.session_state["wf_live"]
            captured.append((active_node(view), phase_label(view), view["report_ready"]))

        state.current_agent, state.agent_phase = "generation", "RUNNING"
        notify()
        state.test_version = 1
        state.trace.append(
            {
                "step": 1,
                "agent": "generation",
                "status": "COMPLETED",
                "task": "INITIAL_GENERATION",
                "test_version": 1,
            }
        )
        state.current_agent = "execution"
        for phase in ("PREFLIGHT", "EXECUTE", "DIAGNOSE"):
            state.agent_phase = phase
            notify()
        state.trace.append(
            {
                "step": 2,
                "agent": "execution",
                "status": "COMPLETED",
                "task": "PREFLIGHT/EXECUTE/DIAGNOSE",
                "test_version": 1,
            }
        )
        state.current_agent, state.agent_phase = "controller", "RUNNING"
        state.trace.append(
            {
                "step": 3,
                "agent": "controller",
                "test_version": 1,
                "decision": {"route": "generation", "mode": "REPAIR_TESTS"},
            }
        )
        notify()
        state.workflow_status, state.agent_phase = "FINISH", "FINISH"
        state.trace[-1]["decision"] = {"workflow_status": "FINISH", "route": "end"}
        notify()  # Terminal Controller visit; report has not been produced yet.
        saved_report(tmp_path, trace=state.trace)
        notify()  # Same observer state after real report files were written.
        return state

    monkeypatch.setattr("testpilot_wf.service.run_project", fake_run)
    app = AppTest.from_file(str(UI)).run()
    app.button[0].click().run()
    assert not app.exception
    assert captured[:5] == [
        ("generation", "INITIAL_GENERATION", False),
        ("execution", "PREFLIGHT", False),
        ("execution", "EXECUTE", False),
        ("execution", "DIAGNOSE", False),
        ("controller", "RUNNING", False),
    ]
    assert captured[5][0] == "" and captured[5][2] is False
    assert captured[6] == ("report", "FINALIZED", True)
    assert "RUNNING" not in graph_text(app)
    assert app.success and not app.warning and not app.error
    assert_no_report_pending(app)


def test_second_run_startup_failure_clears_old_report(tmp_path, monkeypatch):
    saved_report(tmp_path)

    def fail(*args, **kwargs):
        raise OSError("Mock startup failure")

    monkeypatch.setattr("testpilot_wf.service.run_project", fail)
    app = AppTest.from_file(str(UI))
    app.session_state["wf_run"] = str(tmp_path)
    app.run()
    assert app.success
    app.button[0].click().run()
    assert not app.exception and not app.success
    assert "COMPLETED" not in graph_text(app) and "RUNNING" not in graph_text(app)
    assert any("Mock startup failure" in x.value for x in app.error)
    assert_no_report_pending(app)


def test_wf_ui_runs_demo_and_retains_result():
    app = AppTest.from_file(
        str(Path(__file__).resolve().parents[2] / "testpilot_wf/ui.py"), default_timeout=30
    )
    app.run()
    assert not app.exception
    next(x for x in app.selectbox if x.label == "执行后端").set_value("local").run()
    next(x for x in app.checkbox if x.label == "我确认 Local 输入代码可信").check().run()
    next(x for x in app.button if x.label == "运行 Workflow").click().run(timeout=30)
    assert not app.exception
    assert app.success and "FINISH" in app.success[0].value
    assert_no_report_pending(app)
    assert_compact_current_status(app)
    assert not app.warning and not app.error
    assert "Current Agent: Report" in [x.value for x in app.markdown]
    assert 'report [group="right"' in graph_text(app)
    assert 'color="#16a34a", penwidth=3' in graph_text(app)
    assert "RUNNING" not in graph_text(app)
    timeline, messages = app.dataframe[:2]
    assert timeline.value.iloc[-1]["节点"] == "Report"
    assert len(messages.value) == 6
    directory = app.session_state["wf_run"]
    view = load_run(directory)
    assert len(timeline_rows(view)) == 10
    assert timeline.value.iloc[-1]["版本"] == 3
    assert messages.value["版本"].tolist() == [1, 1, 2, 2, 3, 3]
    assert view["report"]["test_version"] == 3
    assert view["report"]["execution_backend"] == "local"
    app.run()
    assert app.success and not app.exception
    assert_no_report_pending(app)
    assert_compact_current_status(app)
    assert not app.warning and not app.error
    assert "RUNNING" not in graph_text(app)
    # A second run must replace, not append, the previous run's timeline/messages.
    next(x for x in app.selectbox if x.label == "项目").set_value("basic").run()
    next(x for x in app.button if x.label == "运行 Workflow").click().run(timeout=30)
    assert not app.exception
    assert app.session_state["wf_run"] != directory
    assert app.dataframe[0].value["节点"].tolist() == [
        "Generation Agent",
        "Execution Agent",
        "Controller",
        "Report",
    ]
    assert len(app.dataframe[1].value) == 2
    assert_no_report_pending(app)


@pytest.mark.parametrize("missing", ["final_report.md", "final_report.json"])
def test_finish_missing_report_is_an_error_after_run_and_rerender(tmp_path, missing):
    saved_report(tmp_path)
    (tmp_path / missing).unlink()
    app = AppTest.from_file(str(UI))
    app.session_state["wf_run"] = str(tmp_path)
    app.session_state["wf_live"] = {"status": "FINISH", "test_version": 1, "demo": True}
    for _ in range(2):
        app.run()
        assert not app.exception and not app.success
        assert any("报告异常" in x.value for x in app.error)
        assert not app.warning
        assert_no_report_pending(app)
        report_node = graph_text(app).split("report [", 1)[1].split("];", 1)[0]
        assert "PENDING" in report_node and "COMPLETED" not in report_node


def render_report_being_written(directory):
    from testpilot_wf.ui import show_dashboard
    from testpilot_wf.ui_state import load_run

    show_dashboard(load_run(directory, {"status": "FINISH", "test_version": 1}), final_check=False)


def test_report_writing_notification_is_not_missing_report_warning(tmp_path):
    saved_report(tmp_path)
    (tmp_path / "final_report.md").unlink()
    app = AppTest.from_function(render_report_being_written, args=(str(tmp_path),)).run()
    assert not app.exception and not app.warning and not app.error and not app.success
    assert any("正在生成最终报告" in item.value for item in app.info)
    assert any("正在生成最终报告" in item.value for item in app.caption)


def test_live_snapshot_refreshes_report_files_on_rerender(tmp_path):
    saved_report(tmp_path)
    app = AppTest.from_file(str(UI))
    app.session_state["wf_live"] = {
        "directory": str(tmp_path),
        "status": "FINISH",
        "report_ready": False,
        "phase": "FINISH",
    }
    for _ in range(2):
        app.run()
        assert not app.exception and not app.error
        assert app.success
        assert_no_report_pending(app)
        assert app.session_state["wf_live"]["report_ready"] is True
        assert "Current Phase / Task: FINALIZED" in [x.value for x in app.markdown]
        assert app.dataframe[0].value.iloc[-1]["状态"] == "FINALIZED"


def test_report_write_failure_clears_pending_caption_and_survives_rerender(tmp_path, monkeypatch):
    from testpilot_wf.schemas import WorkflowState

    def fail_report(project, *, observer, **kwargs):
        state = WorkflowState(project_path=str(project), run_dir=str(tmp_path), demo=True)
        state.workflow_status = "FINISH"
        observer(state)
        raise OSError("Mock report write failed")

    monkeypatch.setattr("testpilot_wf.service.run_project", fail_report)
    app = AppTest.from_file(str(UI)).run()
    app.button[0].click().run()
    assert any("Mock report write failed" in x.value for x in app.error)
    for _ in range(2):
        assert not app.exception and not app.success
        assert any("报告异常" in x.value for x in app.error)
        assert_no_report_pending(app)
        assert "FINALIZED" not in app.dataframe[0].value["状态"].tolist()
        app.run()


def render_tables(view, messages):
    from testpilot_wf.ui import show_table
    from testpilot_wf.ui_state import communication_rows, timeline_rows

    show_table(timeline_rows(view))
    show_table(communication_rows(messages))


def test_table_alignment_preserves_values_order_and_native_types():
    from pandas.api.types import is_bool_dtype, is_numeric_dtype

    from testpilot_wf.ui_state import communication_rows

    view = {
        "trace": [
            {
                "agent": "generation",
                "task": "INITIAL_GENERATION",
                "status": "COMPLETED",
                "test_version": 1,
                "repair_count": 0,
                "coverage_round": 0,
            }
        ]
    }
    messages = [
        {
            "sequence": index + 1,
            "sender": "execution",
            "receiver": "generation",
            "message_type": "ExecutionFeedback",
            "test_version": 1,
            "payload": {
                "failure_category": "TEST_FAILURE",
                "diagnosis": "中文诊断 with details",
                "suggested_action": "REPAIR_TESTS",
                "review_required": review,
            },
        }
        for index, review in enumerate([False, True, None])
    ]
    original = json.dumps([view, messages], ensure_ascii=False)
    expected = [timeline_rows(view), communication_rows(messages)]
    app = AppTest.from_function(render_tables, args=(view, messages)).run()
    assert not app.exception
    for table, rows in zip(app.dataframe, expected, strict=True):
        assert list(table.value.columns) == list(rows[0])
        columns = json.loads(table.proto.columns)
        for name in rows[0]:
            assert columns[name]["alignment"] == "center"
            kind = columns[name]["type_config"]["type"]
            if name in {"顺序", "版本", "Repair", "Improve"}:
                assert kind == "number" and is_numeric_dtype(table.value[name])
            elif name == "人工检查":
                assert kind == "checkbox"
                assert table.value[name].tolist() == [False, True, None]
                assert is_bool_dtype(table.value[name].dropna().infer_objects())
            else:
                assert kind == "text"
            assert table.value[name].tolist() == [row[name] for row in rows]
    assert json.dumps([view, messages], ensure_ascii=False) == original
