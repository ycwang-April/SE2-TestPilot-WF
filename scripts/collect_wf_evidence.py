"""Copy this project's saved, redacted run artifacts; never access credential files."""

import argparse
import json
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = args.run.resolve()
    if source.is_symlink() or not source.is_relative_to(root / "runs"):
        parser.error("Select an existing run inside this project's runs directory")
    report = json.loads((source / "final_report.json").read_text(encoding="utf-8"))
    if "test_version" not in report:
        parser.error("Not a TestPilot-WF report")
    destination = root / "docs/evidence" / source.name
    if destination.exists():
        parser.error("Evidence destination already exists; do not overwrite")
    allowed_roots = {"versions", "repairs", "rejected", "generated_tests", "generation_attempts"}
    allowed_files = {
        "final_report.json",
        "final_report.md",
        "trace.json",
        "messages.json",
        "llm_calls.json",
        "test_plan.json",
        "execution_result.json",
        "coverage_result.json",
        "state.json",
    }
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        if path.is_symlink() or not path.resolve().is_relative_to(source):
            raise ValueError("Symlink or escaped evidence refused")
        if path.is_file() and (
            relative.parts[0] in allowed_roots or relative.as_posix() in allowed_files
        ):
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    print(destination)


if __name__ == "__main__":
    main()
