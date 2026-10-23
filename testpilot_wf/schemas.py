from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from testpilot.agent.state import AgentState
from testpilot.schemas.test_plan import TestPlan


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Mode(StrEnum):
    INITIAL = "INITIAL_GENERATION"
    REPAIR = "REPAIR_TESTS"
    IMPROVE = "IMPROVE_COVERAGE"


class Category(StrEnum):
    PASS = "PASS"
    REPAIR = "REPAIR_TEST"
    IMPROVE = "IMPROVE_COVERAGE"
    SOURCE = "SUSPECTED_SOURCE_BUG"
    ENVIRONMENT = "ENVIRONMENT_ERROR"
    REVIEW = "REVIEW_REQUIRED"
    DIAGNOSIS = "DIAGNOSIS_ERROR"


class Diagnosis(Contract):
    failure_category: Category
    diagnosis: str = Field(min_length=1, max_length=6000)
    suggested_action: Category
    evidence_refs: list[str] = Field(min_length=1, max_length=20)
    review_required: bool
    uncertainty: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def coherent(self):
        if self.suggested_action != self.failure_category:
            raise ValueError("diagnosis category and action must agree")
        if self.failure_category in (Category.SOURCE, Category.REVIEW) and not self.review_required:
            raise ValueError("uncertain/source diagnosis requires review")
        return self


class ExecutionFeedback(Diagnosis):
    test_version: int = Field(ge=1)
    execution_ref: str
    coverage_ref: str
    diagnosis_status: Literal["completed", "error"]


class GenerationResult(Contract):
    mode: Mode
    test_version: int = Field(ge=1)
    test_plan: list[TestPlan]
    tests_ref: str
    digest: str
    summary: str
    warnings: list[str] = Field(default_factory=list)


class AgentMessage(Contract):
    message_id: str = Field(default_factory=lambda: uuid4().hex)
    sender: Literal["generation", "execution"]
    receiver: Literal["generation", "execution"]
    message_type: Literal["generation_result", "execution_feedback"]
    test_version: int = Field(ge=1)
    sequence: int = Field(ge=1)
    evidence_refs: list[str] = Field(min_length=1)
    payload: GenerationResult | ExecutionFeedback

    @model_validator(mode="after")
    def envelope(self):
        expected = (
            ("generation", "execution", "generation_result")
            if isinstance(self.payload, GenerationResult)
            else ("execution", "generation", "execution_feedback")
        )
        if (self.sender, self.receiver, self.message_type) != expected:
            raise ValueError("message direction/type mismatch")
        if self.test_version != self.payload.test_version:
            raise ValueError("message version mismatch")
        return self


class WorkflowState(AgentState):
    mode: Mode = Mode.INITIAL
    test_version: int = Field(default=0, ge=0)
    test_digest: str = ""
    generation: GenerationResult | None = None
    feedback: ExecutionFeedback | None = None
    messages: list[AgentMessage] = Field(default_factory=list)
    workflow_status: Literal["RUNNING", "FINISH", "FAIL", "REVIEW_REQUIRED"] = "RUNNING"
    route: Literal["generation", "end"] = "end"
    reason: str = ""
    current_agent: str = ""
    agent_phase: str = ""
    trace: list[dict] = Field(default_factory=list)
    extensions: dict = Field(default_factory=dict)
