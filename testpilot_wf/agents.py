import json
from pathlib import Path

from testpilot.agent.nodes import AgentNodes
from testpilot.errors import LLMOutputValidationError, TestPilotError
from testpilot.reporting.artifacts import ArtifactWriter, redact
from testpilot.tools.context_selector import ContextSelector
from testpilot.tools.coverage_analyzer import CoverageAnalyzer
from testpilot_wf.llm import ExecutionLLM, GenerationLLM
from testpilot_wf.schemas import (
    AgentMessage,
    Category,
    Diagnosis,
    ExecutionFeedback,
    GenerationResult,
    Mode,
)
from testpilot_wf.validation import digest, preflight, preserve_assertions


class FeedbackSelector(ContextSelector):
    def __init__(self, max_chars, validation_feedback=None):
        super().__init__(max_chars)
        self.validation_feedback = validation_feedback

    def select(self, state, *args, **kwargs):
        data = json.loads(super().select(state, *args, **kwargs))
        data["test_version"] = state.test_version
        data["execution_agent_feedback"] = state.feedback.model_dump() if state.feedback else None
        if self.validation_feedback is not None:
            # Preserve H1's per-file repair feedback separately from local preflight feedback.
            data["validation_feedback"] = {
                **self.validation_feedback,
                "repair_validation_feedback": data.get("validation_feedback"),
            }
        context = json.dumps(data, ensure_ascii=False)
        if len(context) > self.max_chars:
            raise LLMOutputValidationError("Feedback context exceeds context budget; select target")
        return context


class GenerationAgent:
    name = "generation"
    writes = {
        "repository",
        "project_index",
        "target_modules",
        "test_plan",
        "generated_tests",
        "generation",
        "test_version",
        "test_digest",
        "messages",
        "warnings",
    }

    def __init__(self, config, artifacts, client=None):
        self.config, self.artifacts, self.client = config, artifacts, client

    def invoke(self, state):
        work = state.model_copy(deep=True)
        if work.mode != Mode.INITIAL:
            if not work.feedback or work.feedback.test_version != work.test_version:
                raise LLMOutputValidationError("Stale feedback refused by Generation Agent")
            expected = Category.REPAIR if work.mode == Mode.REPAIR else Category.IMPROVE
            # Controller can override a false PASS on objectively low coverage.
            allowed = {expected, Category.PASS} if work.mode == Mode.IMPROVE else {expected}
            if work.feedback.suggested_action not in allowed or work.feedback.review_required:
                raise LLMOutputValidationError("Feedback does not authorize this generation task")
        if self.client is None:
            self.client = GenerationLLM(self.config.llm)
        # H1 tool methods, not H1 workflow/controller: no execution capability is provided.
        nodes = AgentNodes(self.config, None, self.artifacts, self.client)
        nodes.selector = FeedbackSelector(self.config.agent.context_max_chars)
        attempt = 1
        attempt_refs = []
        validation_feedback = None
        preflight_exhausted = False
        try:
            if work.mode == Mode.INITIAL:
                nodes.analyze(work)
                nodes.plan(work)
            baseline = work.model_copy(deep=True)
            for attempt in (1, 2):
                work = baseline.model_copy(deep=True)
                nodes.selector = FeedbackSelector(
                    self.config.agent.context_max_chars, validation_feedback
                )
                if attempt == 2:
                    # H1 repair attempt paths must not overwrite the first local attempt.
                    nodes.artifacts = ArtifactWriter(
                        self.artifacts.directory / f"generation_attempts/{len(state.trace):03d}/02"
                    )
                if work.mode == Mode.INITIAL:
                    nodes.generate(work)
                elif work.mode == Mode.REPAIR:
                    work.repair_count -= 1  # H1 increments only this private working copy.
                    nodes.repair(work)
                else:
                    work.coverage_round -= 1
                    nodes.improve_coverage(work)
                # Protection failures take precedence over recoverable preflight errors.
                # A malformed replacement of an existing test remains fail-closed under H1.
                if state.generated_tests:
                    preserve_assertions(state.generated_tests, work.generated_tests)
                new_digest = digest(work.generated_tests)
                if new_digest == state.test_digest:
                    raise LLMOutputValidationError("No actual test change; version not committed")
                try:
                    preflight(work.generated_tests)
                except LLMOutputValidationError as exc:
                    # Only errors from this exact content-validation boundary can retry.
                    # H1 validation/API/context errors above retain their existing behavior.
                    validation_feedback = {
                        "source": "generation_preflight",
                        "error_type": type(exc).__name__,
                        "files": [t.path for t in work.generated_tests],
                        "line": getattr(exc.__cause__, "lineno", None),
                        "error": redact(str(exc)),
                        "requirements": "Preserve test intent, all existing assertions and safety "
                        "constraints. Correct this candidate without changing production code.",
                    }
                    ref = f"rejected/{len(state.trace):03d}-attempt-{attempt:02d}.json"
                    self.artifacts.json(
                        ref,
                        {
                            "attempt": attempt,
                            "mode": work.mode,
                            "accepted": False,
                            "validation_feedback": validation_feedback,
                            "candidate": [t.model_dump() for t in work.generated_tests],
                        },
                    )
                    attempt_refs.append(ref)
                    if attempt == 2:
                        preflight_exhausted = True
                        raise LLMOutputValidationError(
                            f"Generation preflight failed after 2 candidate attempts: {exc}"
                        ) from exc
                    continue
                if attempt == 2:
                    ref = f"generation_attempts/{len(state.trace):03d}/accepted-02.json"
                    self.artifacts.json(
                        ref,
                        {
                            "attempt": attempt,
                            "mode": work.mode,
                            "accepted": True,
                            "validation_feedback": validation_feedback,
                            "candidate": [t.model_dump() for t in work.generated_tests],
                        },
                    )
                    attempt_refs.append(ref)
                    work.warnings.append("Generation preflight self-correction accepted: " + ref)
                break
        except Exception as exc:
            # Original terminal evidence boundary only; never retries arbitrary exceptions.
            if preflight_exhausted:
                raise  # Both rejected candidates already have their own durable records.
            self.artifacts.json(
                f"rejected/{len(state.trace):03d}.json",
                {
                    "mode": work.mode,
                    "attempt": attempt,
                    "accepted": False,
                    "error_type": type(exc).__name__,
                    "error": redact(str(exc))
                    if isinstance(exc, TestPilotError)
                    else type(exc).__name__,
                    "candidate": [t.model_dump() for t in work.generated_tests],
                },
            )
            raise
        version = state.test_version + 1
        ref = f"versions/{version:03d}/tests.json"
        self.artifacts.json(ref, [t.model_dump() for t in work.generated_tests])
        result = GenerationResult(
            mode=work.mode,
            test_version=version,
            test_plan=work.test_plan,
            tests_ref=ref,
            digest=new_digest,
            summary=f"{work.mode}: committed version {version}"
            + ("; preflight self-correction accepted" if attempt == 2 else ""),
            warnings=work.warnings,
        )
        message = AgentMessage(
            sender="generation",
            receiver="execution",
            message_type="generation_result",
            test_version=version,
            sequence=len(state.messages) + 1,
            evidence_refs=[ref, *attempt_refs],
            payload=result,
        )
        return {
            **{
                name: getattr(work, name)
                for name in (
                    "repository",
                    "project_index",
                    "target_modules",
                    "test_plan",
                    "generated_tests",
                    "warnings",
                )
            },
            "generation": result,
            "test_version": version,
            "test_digest": new_digest,
            "messages": state.messages + [message],
        }


class ExecutionAgent:
    name = "execution"
    writes = {"execution_result", "coverage", "feedback", "messages"}

    def __init__(self, config, artifacts, runner, client=None, progress=None):
        self.config, self.artifacts, self.runner = config, artifacts, runner
        self.client, self.progress = client, progress

    def invoke(self, state):
        def phase(name):
            if self.progress:
                self.progress(state, name)

        phase("PREFLIGHT")
        if (
            not state.generation
            or state.generation.test_version != state.test_version
            or digest(state.generated_tests) != state.test_digest
            or state.generation.digest != state.test_digest
            or not state.messages
            or state.messages[-1].payload != state.generation
        ):
            raise LLMOutputValidationError("Execution received stale/uncommitted tests")
        preflight(state.generated_tests)
        root = f"versions/{state.test_version:03d}"
        execution_ref, coverage_ref = f"{root}/execution.json", f"{root}/coverage.json"
        refs = [state.generation.tests_ref, execution_ref, coverage_ref]
        result, coverage, environment_error = None, None, None
        phase("EXECUTE")
        try:
            result = self.runner.run(
                Path(state.project_path),
                state.repository,
                state.generated_tests,
                self.config.coverage.enabled,
            )
            if self.config.coverage.enabled and result.coverage_data:
                coverage = CoverageAnalyzer().analyze(result.coverage_data, state.target_modules)
        except Exception as exc:
            environment_error = (
                redact(f"{type(exc).__name__}: {exc}")
                if isinstance(exc, TestPilotError)
                else type(exc).__name__
            )
        # Persist raw facts before any model call, including diagnosis failures.
        self.artifacts.json(
            execution_ref,
            {
                "result": result.model_dump() if result else None,
                "environment_error": environment_error,
            },
        )
        self.artifacts.json(coverage_ref, coverage.model_dump() if coverage else None)
        work = state.model_copy(deep=True)
        work.execution_result, work.coverage = result, coverage
        phase("DIAGNOSE")
        diagnosis_status = "completed"
        try:
            context = json.loads(
                ContextSelector(self.config.agent.context_max_chars).select(
                    work,
                    "IMPROVE_COVERAGE",
                    state.target_modules,
                )
            )
            context.update(
                # Reuse H1's evidence selection without inheriting its generation task.
                action="DIAGNOSE",
                test_version=state.test_version,
                test_plan=[p.model_dump() for p in state.test_plan],
                evidence_refs=refs,
                environment_error=environment_error,
                coverage_policy=self.config.coverage.model_dump(),
            )
            serialized = json.dumps(context, ensure_ascii=False)
            if len(serialized) > self.config.agent.context_max_chars:
                raise LLMOutputValidationError("Diagnosis context exceeds budget")
            if self.client is None:
                self.client = ExecutionLLM(self.config.llm)
            diagnosis = Diagnosis.model_validate(self.client.diagnose(serialized))
            if not set(diagnosis.evidence_refs).issubset(refs):
                raise LLMOutputValidationError("Diagnosis cites unknown evidence")
        except Exception as exc:
            diagnosis_status = "error"
            diagnosis = Diagnosis(
                failure_category=Category.DIAGNOSIS,
                suggested_action=Category.DIAGNOSIS,
                diagnosis=f"Independent diagnosis failed: {type(exc).__name__}",
                evidence_refs=refs,
                review_required=False,
                uncertainty="No valid model diagnosis; original execution facts retained",
            )
        if environment_error and diagnosis_status == "completed":
            # A model cannot turn an infrastructure exception into a test-repair permission.
            diagnosis = Diagnosis(
                failure_category=Category.ENVIRONMENT,
                suggested_action=Category.ENVIRONMENT,
                diagnosis=f"{environment_error}; model observation: {diagnosis.diagnosis}",
                evidence_refs=refs,
                review_required=False,
                uncertainty=diagnosis.uncertainty,
            )
        feedback = ExecutionFeedback(
            **diagnosis.model_dump(),
            test_version=state.test_version,
            execution_ref=execution_ref,
            coverage_ref=coverage_ref,
            diagnosis_status=diagnosis_status,
        )
        self.artifacts.json(f"{root}/feedback.json", feedback.model_dump())
        message = AgentMessage(
            sender="execution",
            receiver="generation",
            message_type="execution_feedback",
            test_version=state.test_version,
            sequence=len(state.messages) + 1,
            evidence_refs=refs,
            payload=feedback,
        )
        return {
            "execution_result": result,
            "coverage": coverage,
            "feedback": feedback,
            "messages": state.messages + [message],
        }
