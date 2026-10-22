"""Demo: Market Researcher Agent with Time-Travel Debugging in Chronos.

This script simulates an autonomous agent workflow that encounters an error
at Step 3, demonstrating how Chronos allows instant rewinding and branching.
"""

import sys
import time
from pathlib import Path

# Add src to path for running directly from source
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import chronos
from chronos import EventType


def run_agent_workflow(session: chronos.ChronosSession, clean_data_prompt: bool = False):
    print(f"\n🚀 Running Agent on Branch: '{session.branch_id}' (Mode: {session.mode})")

    # Step 1: Tool call - Fetch market data
    def fetch_data():
        time.sleep(0.5)  # Simulate network latency
        return {"raw_text": "TechCorp reported Q3 revenue of $4.2B with 18% YoY growth."}

    step1_out = session.step(
        name="fetch_sec_filing",
        event_type=EventType.TOOL,
        inputs={"ticker": "TECH", "filing": "10-Q"},
        fn=fetch_data
    )

    # Step 2: LLM call - Extract metrics
    prompt = (
        "Extract raw numbers as clean floats: revenue in billions, growth rate as decimal."
        if clean_data_prompt
        else "Extract metrics: revenue, growth rate."
    )

    def extract_metrics():
        time.sleep(0.8)  # Simulate LLM inference latency
        if clean_data_prompt:
            # Fixed behavior: returns clean parseable numbers
            return {"revenue_billion": 4.2, "growth_decimal": 0.18}
        else:
            # Buggy prompt behavior: returns formatted string with '$' and 'B'
            return {"revenue_billion": "$4.2B", "growth_decimal": "18%"}

    step2_out = session.step(
        name="gemini-2.5-flash",
        event_type=EventType.LLM,
        inputs={"prompt": prompt, "source": step1_out["raw_text"]},
        fn=extract_metrics
    )

    # Step 3: Tool call - Compute projected valuation
    def compute_valuation():
        rev = step2_out["revenue_billion"]
        # Bug trigger: If rev is a string like '$4.2B', float(rev) crashes!
        return float(rev) * 12.5

    step3_out = session.step(
        name="compute_projected_valuation",
        event_type=EventType.TOOL,
        inputs={"revenue": step2_out["revenue_billion"], "multiple": 12.5},
        fn=compute_valuation
    )

    # Step 4: Final LLM synthesis
    def synthesize_report():
        time.sleep(0.4)
        return f"Projected valuation is ${step3_out:.2f}B based on 12.5x multiple."

    final_report = session.step(
        name="synthesize_summary",
        event_type=EventType.LLM,
        inputs={"valuation": step3_out},
        fn=synthesize_report
    )

    return final_report


def main():
    db_file = "demo_chronos.db"

    print("=" * 65)
    print("RUN 1: The Agent Runs and Crashes at Step 3 (The Nightmare)")
    print("=" * 65)
    session1 = chronos.init(name="market-research-demo", db_path=db_file)

    failed_step_id = None
    step2_checkpoint_id = None

    try:
        run_agent_workflow(session1, clean_data_prompt=False)
    except Exception as e:
        print(f"\n💥 Crash Occurred: {type(e).__name__}: {e}")
        # Note the parent of the failed step is Step 2
        failed_step = session1.store.get_checkpoint(session1.parent_checkpoint_id)
        step2_checkpoint_id = failed_step.parent_id
        print(f"Failed at Checkpoint: {failed_step.checkpoint_id}")
        print(f"Parent Checkpoint to rewind to (Step 2): {step2_checkpoint_id}")

    print("\n" + "=" * 65)
    print("RUN 2: Chronos Time-Travel Rewind & Multiverse Branch")
    print("=" * 65)
    print("Rewinding back to Step 1... Replaying Step 1 instantly from cache...")
    print("Patching Step 2 prompt... Executing only the fix forward!")

    # Fork from Step 1's checkpoint (so Step 1 is replayed, and Step 2 receives the prompt fix)
    step1_chk = session1.store.get_checkpoint(step2_checkpoint_id).parent_id
    session2 = chronos.fork(
        parent_checkpoint_id=step1_chk,
        new_branch_name="fix-clean-prompt",
        db_path=db_file
    )

    result = run_agent_workflow(session2, clean_data_prompt=True)
    print(f"\n🎉 Success! Final Agent Output:\n{result}")


if __name__ == "__main__":
    main()
