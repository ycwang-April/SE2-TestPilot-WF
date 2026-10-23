"""Explicit fixed-response agents; pytest and coverage still execute for real."""

import json

from testpilot.llm.fake import DemoLLM, bundle
from testpilot_wf.schemas import Category, Diagnosis


class DemoGeneration(DemoLLM):
    def generate(self, context, plan):
        if self._target(context) == "shipping.py":
            return bundle(
                "test_shipping.py",
                "from shipping import shipping_fe\n\n"
                "def test_regular_small():\n    assert shipping_fe(1) == 5\n",
            )
        return super().generate(context, plan)

    def repair(self, context):
        self._target(context)
        data = json.loads(context)
        old = data["existing_tests"][0]
        # Repair an import typo with an alias, keeping assertion AST unchanged.
        return bundle(
            old["path"],
            old["content"].replace(
                "from shipping import shipping_fe\n",
                "from shipping import shipping_fee as shipping_fe\n",
            ),
        )


class DemoExecution:
    def diagnose(self, context):
        data = json.loads(context)
        result, coverage = data["execution"], data["coverage"]
        category = Category.PASS
        if data["environment_error"]:
            category = Category.ENVIRONMENT
        elif result and result["returncode"]:
            category = (
                Category.REPAIR
                if "cannot import name 'shipping_fe'" in result["traceback"]
                else Category.REVIEW
            )
        elif (
            coverage
            and data["coverage_policy"]["enabled"]
            and (
                coverage["line_coverage"] < data["coverage_policy"]["line_threshold"]
                or coverage["branch_coverage"] < data["coverage_policy"]["branch_threshold"]
            )
        ):
            category = Category.IMPROVE
        return Diagnosis(
            failure_category=category,
            suggested_action=category,
            diagnosis=f"DEMO scripted diagnosis: {category}; inspect referenced tool facts",
            evidence_refs=data["evidence_refs"],
            review_required=category == Category.REVIEW,
            uncertainty="Fixed demo response, not real LLM reasoning",
        )
