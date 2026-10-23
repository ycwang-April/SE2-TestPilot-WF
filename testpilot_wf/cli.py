import argparse
import json
from pathlib import Path

from testpilot.config import load_config
from testpilot.errors import TestPilotError
from testpilot.reporting.artifacts import redact
from testpilot_wf.schemas import Mode
from testpilot_wf.service import run_project


def brief(value, limit=240):
    """Keep terminal output short, single-line and free of known environment secrets."""
    text = " ".join(redact(str(value)).split())
    return text if len(text) <= limit else text[:limit] + "... (see artifacts)"


class CLIProgressReporter:
    """Render existing observer snapshots without changing workflow state."""

    def __init__(self, config):
        self.config = config
        self.phases = set()
        self.decisions = set()
        self.messages = set()

    def start(self, project, demo):
        print("=" * 50, flush=True)
        print("TestPilot-WF | Multi-Agent Testing Workflow", flush=True)
        print("=" * 50, flush=True)
        print("[Workflow] START", flush=True)
        print(f"[Project] {brief(Path(project).name)}", flush=True)
        mode = "DEMO (fixed responses; no LLM calls; real pytest)" if demo else "REAL DEEPSEEK"
        print(f"[Mode] {mode}", flush=True)
        print(f"[Runner] {self.config.execution.preferred_runner} (requested)", flush=True)

    def __call__(self, state):
        agent, phase = state.current_agent, state.agent_phase
        key = (
            agent,
            phase,
            len(state.trace),
            state.test_version,
            state.mode,
            state.repair_count,
            state.coverage_round,
        )
        if agent and agent != "controller" and key not in self.phases:
            self.phases.add(key)
            label = {"generation": "Generation Agent", "execution": "Execution Agent"}.get(
                agent, brief(agent)
            )
            if phase == "RUNNING":
                task = f" | Task: {state.mode}" if agent == "generation" else ""
                print(f"[{label}] START{task}", flush=True)
            elif phase in {"COMPLETED", "ERROR"}:
                backend = (
                    f" | Backend: {brief(state.execution_result.backend)}"
                    if agent == "execution" and state.execution_result
                    else ""
                )
                print(
                    f"[{label}] {phase} | Test Version: v{state.test_version}{backend}", flush=True
                )
            elif agent == "execution" and phase in {"PREFLIGHT", "EXECUTE", "DIAGNOSE"}:
                task = " | pytest" if phase == "EXECUTE" else ""
                print(f"[{label}] {phase}{task}", flush=True)

        for message in state.messages:
            if message.message_id in self.messages:
                continue
            self.messages.add(message.message_id)
            category = (
                f" | {message.payload.failure_category}"
                if message.message_type == "execution_feedback"
                else ""
            )
            print(
                f"[Communication] {message.sender.title()} -> {message.receiver.title()}"
                f" | {message.message_type}{category} | v{message.test_version}",
                flush=True,
            )

        for index, event in enumerate(state.trace, 1):
            if event.get("agent") != "controller":
                continue
            step = event.get("step", index)
            if step in self.decisions:
                continue
            self.decisions.add(step)
            decision = event.get("decision") or {}
            task = (
                decision.get("mode")
                if decision.get("route") == "generation"
                else decision.get("workflow_status")
            )
            if not task:
                continue
            budget = ""
            if task == Mode.REPAIR:
                budget = f" | Repair: {event.get('repair_count', state.repair_count)}/{self.config.agent.max_repair_rounds}"
            elif task == Mode.IMPROVE:
                budget = f" | Improve: {event.get('coverage_round', state.coverage_round)}/{self.config.coverage.max_improvement_rounds}"
            print(f"[Controller] Decision: {brief(task)}{budget}", flush=True)


def final_report_ready(state):
    """Called only after run_project returns, never from an intermediate observer."""
    if not state.run_dir or state.workflow_status not in {"FINISH", "FAIL", "REVIEW_REQUIRED"}:
        return False
    directory = Path(state.run_dir)
    paths = [directory / name for name in ("final_report.json", "final_report.md")]
    try:
        if any(not path.is_file() or path.is_symlink() for path in paths):
            return False
        report = json.loads(paths[0].read_text(encoding="utf-8"))
        with paths[1].open(encoding="utf-8") as markdown:
            readable_markdown = bool(markdown.read(1))
        return (
            isinstance(report, dict)
            and report.get("status") == state.workflow_status
            and report.get("test_version") == state.test_version
            and readable_markdown
        )
    except (OSError, UnicodeError, ValueError):
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description="TestPilot-WF: two independent LLM agents")
    parser.add_argument("project")
    parser.add_argument("--config")
    parser.add_argument("--target")
    parser.add_argument(
        "--demo", action="store_true", help="Fixed responses, real pytest execution"
    )
    parser.add_argument(
        "--runner", choices=["docker", "local"], help="Local explicitly trusts input code"
    )
    parser.add_argument("--output", default="runs")
    parser.add_argument("--line-threshold", type=float)
    parser.add_argument("--branch-threshold", type=float)
    parser.add_argument("--max-repair", type=int)
    parser.add_argument("--max-improvement", type=int)
    parser.add_argument("--no-coverage", action="store_true")
    parser.add_argument(
        "--quiet", action="store_true", help="Show only final result and artifact errors"
    )
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        if args.runner:
            config.execution.preferred_runner = args.runner
        for group, field, value in (
            (config.coverage, "line_threshold", args.line_threshold),
            (config.coverage, "branch_threshold", args.branch_threshold),
            (config.agent, "max_repair_rounds", args.max_repair),
            (config.coverage, "max_improvement_rounds", args.max_improvement),
        ):
            if value is not None:
                setattr(group, field, value)
        if args.no_coverage:
            config.coverage.enabled = False
        config = type(config).model_validate(config.model_dump())
        reporter = None if args.quiet else CLIProgressReporter(config)
        if reporter:
            reporter.start(args.project, args.demo)
        state = run_project(
            args.project,
            config=config,
            target=args.target,
            demo=args.demo,
            output=args.output,
            observer=reporter,
        )
    except (TestPilotError, ValueError) as exc:
        print(f"Configuration/input error: {type(exc).__name__}", flush=True)
        return 1
    except OSError as exc:
        print(f"FAIL: Workflow/artifact I/O error: {type(exc).__name__}", flush=True)
        return 1
    ready = final_report_ready(state)
    if not ready:
        print("[Report] ERROR | Final report missing, unreadable or inconsistent", flush=True)
    elif not args.quiet:
        print("[Report] FINALIZED", flush=True)
    status = state.workflow_status if ready else "FAIL"
    reason = (
        state.reason if ready else f"Final report error; Workflow result: {state.workflow_status}"
    )
    print(f"{status}: {brief(reason)}\nArtifacts: {redact(state.run_dir)}", flush=True)
    return 0 if status == "FINISH" else 2 if status == "REVIEW_REQUIRED" else 1
