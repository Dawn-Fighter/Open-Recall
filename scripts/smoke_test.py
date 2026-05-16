from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from incident_agent.memory import IncidentMemory
from incident_agent.router import CascadeFlowRouter
from incident_agent.workflow import IncidentWorkflow


def main() -> None:
    os.environ.setdefault("CASCADEFLOW_LIVE_GROQ", "false")
    os.environ.setdefault("HINDSIGHT_BASE_URL", "http://127.0.0.1:9")

    samples = json.loads((ROOT / "data" / "sample_alerts.json").read_text())
    memory = IncidentMemory()
    router = CascadeFlowRouter()
    workflow = IncidentWorkflow(memory, router)

    results = [workflow.analyze(sample["raw_alert"]) for sample in samples]

    assert all(result.route_trace for result in results), "each run must emit route trace"
    assert all(result.verification_commands for result in results), (
        "each run must emit verification commands"
    )
    assert any(result.memory_matches for result in results), (
        "seed memory should produce at least one recall hit"
    )
    assert any(trace.escalated for result in results for trace in result.route_trace), (
        "at least one scenario should escalate"
    )
    assert any(
        not trace.escalated for result in results for trace in result.route_trace
    ), "at least one scenario should stay on the standard route"

    print(
        "smoke ok:"
        f" samples={len(results)}"
        f" fallback={memory.fallback_mode}"
        f" traces={sum(len(result.route_trace) for result in results)}"
    )


if __name__ == "__main__":
    main()
