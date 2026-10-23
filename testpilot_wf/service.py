import json
from pathlib import Path

from testpilot.config import AppConfig
from testpilot.errors import TestPilotError
from testpilot.reporting.artifacts import ArtifactWriter, redact
from testpilot.reporting.runs import create_run_directory
from testpilot.runners.docker_runner import DockerTestRunner
from testpilot.runners.local_runner import LocalTestRunner
from testpilot_wf.agents import ExecutionAgent, GenerationAgent
from testpilot_wf.controller import decide
from testpilot_wf.demo import DemoExecution, DemoGeneration
from testpilot_wf.schemas import WorkflowState
from testpilot_wf.workflow import AgentRegistry, WorkflowBuilder


def run_project(
    project,
    *,
    config=None,
    target=None,
    demo=False,
    output="runs",
    generation_client=None,
    execution_client=None,
    runner=None,
    observer=None,
    extra_agents=(),
    chain=("generation", "execution"),
):
    config = (config or AppConfig()).model_copy(deep=True)
    config.execution.allow_local_fallback = False
    project = Path(project).resolve()
    directory = create_run_directory(
        Path(output), project.name, demo, config.execution.preferred_runner
    )
    artifacts = ArtifactWriter(directory)
    state = WorkflowState(
        project_path=str(project), requested_target=target, run_dir=str(directory), demo=demo
    )
    if demo:
        generation_client = generation_client or DemoGeneration()
        execution_client = execution_client or DemoExecution()
    runner = runner or (
        DockerTestRunner(config.execution)
        if config.execution.preferred_runner == "docker"
        else LocalTestRunner(config.execution)
    )

    def publish(current):
        artifacts.json("trace.json", current.trace)
        artifacts.json("messages.json", [m.model_dump() for m in current.messages])
        artifacts.json(
            "state.json",
            current.model_dump(
                mode="json",
                exclude={
                    "selected_context",
                    "generated_tests",
                    "execution_result",
                    "execution_history",
                    "project_index",
                    "repository",
                },
            ),
        )
        if observer:
            observer(current.model_copy(deep=True))

    def progress(current, phase):
        snapshot = current.model_copy(deep=True)
        snapshot.current_agent, snapshot.agent_phase = "execution", phase
        if observer:
            observer(snapshot)

    registry = AgentRegistry()
    registry.register(GenerationAgent(config, artifacts, generation_client))
    registry.register(ExecutionAgent(config, artifacts, runner, execution_client, progress))
    for agent in extra_agents:
        registry.register(agent)

    def calls():
        return [
            {"agent": name, **call}
            for name in ("generation", "execution")
            for call in getattr(registry.get(name).client, "diagnostics", [])
        ]

    def wrap(agent):
        def node(original):
            current = original.model_copy(deep=True)
            current.current_agent, current.agent_phase = agent.name, "RUNNING"
            if observer:
                observer(current.model_copy(deep=True))
            error = None
            before = len(current.messages)
            call_start = len(getattr(getattr(agent, "client", None), "diagnostics", []))
            try:
                updates = agent.invoke(current.model_copy(deep=True))
                if set(updates) - agent.writes:
                    raise ValueError("Agent attempted to update unowned fields")
                if agent.name not in {"generation", "execution"} and set(updates) - {"extensions"}:
                    raise ValueError("Extension agents may only update extensions")
                current = WorkflowState.model_validate({**current.model_dump(), **updates})
                # Revalidate every envelope even for an injected/custom agent.
                for index, message in enumerate(current.messages, 1):
                    if message.sequence != index:
                        raise ValueError("Non-monotonic message sequence")
                if len({m.message_id for m in current.messages}) != len(current.messages):
                    raise ValueError("Duplicate message identity")
            except Exception as exc:
                current = original.model_copy(deep=True)
                error = redact(str(exc)) if isinstance(exc, TestPilotError) else type(exc).__name__
                current.error = f"{agent.name}: {type(exc).__name__}: {error}"
                current.failure_stage = agent.name
            current.current_agent, current.agent_phase = (
                agent.name,
                "ERROR" if error else "COMPLETED",
            )
            current.trace.append(
                {
                    "step": len(current.trace) + 1,
                    "agent": agent.name,
                    "task": str(current.mode)
                    if agent.name == "generation"
                    else "PREFLIGHT/EXECUTE/DIAGNOSE"
                    if agent.name == "execution"
                    else "EXTENSION",
                    "test_version": current.test_version,
                    "status": current.agent_phase,
                    "input_message": original.messages[-1].message_id
                    if original.messages
                    else None,
                    "output_messages": [m.message_id for m in current.messages[before:]],
                    "repair_count": current.repair_count,
                    "coverage_round": current.coverage_round,
                    "error": current.error,
                    "llm_mode": "DEMO_FIXED_RESPONSE" if demo else "MODEL",
                    "llm_calls": getattr(getattr(agent, "client", None), "diagnostics", [])[
                        call_start:
                    ],
                    "evidence_refs": [
                        ref
                        for message in current.messages[before:]
                        for ref in message.evidence_refs
                    ],
                }
            )
            artifacts.json("llm_calls.json", calls())
            publish(current)
            return current.model_dump()

        return node

    def controller(original):
        update = decide(original, config)
        current = WorkflowState.model_validate({**original.model_dump(), **update})
        current.current_agent, current.agent_phase = "controller", current.workflow_status
        current.trace.append(
            {
                "step": len(current.trace) + 1,
                "agent": "controller",
                "test_version": current.test_version,
                "decision": update,
                "repair_count": current.repair_count,
                "coverage_round": current.coverage_round,
            }
        )
        publish(current)
        return current.model_dump()

    last = state.model_dump()
    try:
        graph = WorkflowBuilder(registry, chain).build(wrap, controller)
        limit = (len(chain) + 1) * (
            1 + config.agent.max_repair_rounds + config.coverage.max_improvement_rounds
        ) + 5
        for value in graph.stream(last, {"recursion_limit": limit}, stream_mode="values"):
            last = value
        state = WorkflowState.model_validate(last)
    except Exception as exc:
        state = WorkflowState.model_validate(last)
        state.workflow_status, state.reason = "FAIL", f"Workflow error: {type(exc).__name__}"
        state.error = state.reason
    report = {
        "project": project.name,
        "status": state.workflow_status,
        "demo": demo,
        "reason": state.reason,
        "error": state.error,
        "test_version": state.test_version,
        "repair_rounds": state.repair_count,
        "coverage_rounds": state.coverage_round,
        "execution_backend": state.execution_result.backend
        if state.execution_result
        else "not executed",
        "execution": state.execution_result.model_dump(exclude={"coverage_data"})
        if state.execution_result
        else None,
        "coverage": state.coverage.model_dump() if state.coverage else None,
        "feedback": state.feedback.model_dump() if state.feedback else None,
        "model_calls": calls(),
        "config": config.model_dump(),
        "limitations": [
            "Snapshots are evidence, not resumable checkpoints",
            "Only generated tests execute; original test suite is preserved",
            "Static preflight is not a security sandbox; Local is for trusted code",
            "Assertion preservation is conservative, not proof of semantic correctness",
        ],
    }
    artifacts.json("final_report.json", report)
    artifacts.json("test_plan.json", [p.model_dump() for p in state.test_plan])
    artifacts.json("execution_result.json", report["execution"])
    artifacts.json("coverage_result.json", report["coverage"])
    for test in state.generated_tests:
        path = directory / "generated_tests" / test.path
        path.parent.mkdir(exist_ok=True)
        path.write_text(redact(test.content), encoding="utf-8")
    (directory / "final_report.md").write_text(
        redact(
            "# TestPilot-WF Run Report\n\n"
            f"- Mode: {'DEMO (no LLM calls)' if demo else 'Real model mode; see call status'}\n"
            f"- Status: {state.workflow_status}\n- Reason: {state.reason}\n"
            f"- Test version: {state.test_version}\n- Backend: {report['execution_backend']}\n"
            f"- Repair / coverage rounds: {state.repair_count} / {state.coverage_round}\n\n"
            "```json\n" + json.dumps(report, ensure_ascii=False, indent=2) + "\n```\n"
        ),
        encoding="utf-8",
    )
    publish(state)
    return state
