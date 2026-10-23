"""Opt-in only: real, separately recorded LLM calls and real Docker execution."""

import json
import os
from pathlib import Path

import pytest

from testpilot.config import AppConfig
from testpilot_wf.service import run_project


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("TESTPILOT_RUN_INTEGRATION") != "1" or not os.getenv("DEEPSEEK_API_KEY"),
    reason="Requires explicit integration opt-in and a valid DeepSeek API key",
)
def test_real_two_agents_docker(example_root, tmp_path):
    config = AppConfig()
    config.execution.allow_local_fallback = False
    state = run_project(example_root / "basic", config=config, output=tmp_path / "runs")
    assert state.workflow_status == "FINISH", state.reason
    assert state.execution_result.backend == "docker"
    calls = json.loads((Path(state.run_dir) / "llm_calls.json").read_text(encoding="utf-8"))
    assert {c["agent"] for c in calls if c["status"] == "completed"} == {"generation", "execution"}
