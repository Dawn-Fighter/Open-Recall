import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from incident_agent.memory import IncidentMemory


if __name__ == "__main__":
    load_dotenv(Path(__file__).resolve().parent / ".env")
    parser = argparse.ArgumentParser(
        description="Seed Hindsight with incident memories."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Seed only the first N memories. 0 means all.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=None,
        help="Seconds to wait between retain calls.",
    )
    args = parser.parse_args()
    if args.delay is not None:
        os.environ["HINDSIGHT_SEED_DELAY_SECONDS"] = str(args.delay)
    if args.limit:
        os.environ["HINDSIGHT_SEED_LIMIT"] = str(args.limit)
    memory = IncidentMemory()
    try:
        print(memory.seed())
    finally:
        memory.close()
