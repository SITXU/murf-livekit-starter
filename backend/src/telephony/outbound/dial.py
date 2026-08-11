"""Trigger an outbound call.

The outbound agent doesn't call anyone on its own — it waits to be dispatched
into a room with a phone number attached. This script does that dispatch.

Make sure the worker is running first:

    uv run python src/telephony/outbound/agent.py dev

Then place a call:

    uv run python src/telephony/outbound/dial.py --to +15551234567

This is the scriptable equivalent of:

    lk dispatch create --agent-name outbound-agent --room my-room \\
      --metadata '{"phone_number": "+15551234567"}'
"""

import argparse
import asyncio
import json
import re
import sys
import uuid

from dotenv import load_dotenv
from livekit import api

load_dotenv(".env.local")

# Must match the agent_name in agent.py.
AGENT_NAME = "outbound-agent"

# E.164: a leading + and 7-15 digits, e.g. +15551234567.
E164 = re.compile(r"^\+[1-9]\d{6,14}$")


async def dial(phone_number: str, room_name: str, user_id: str) -> None:
    """Create the room and dispatch the outbound agent into it."""
    lk = api.LiveKitAPI()
    try:
        await lk.room.create_room(api.CreateRoomRequest(name=room_name))

        # The agent reads this metadata to know who to call.
        await lk.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name=AGENT_NAME,
                room=room_name,
                metadata=json.dumps({"phone_number": phone_number, "user_id": user_id}),
            )
        )
    finally:
        await lk.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Place an outbound call.")
    parser.add_argument(
        "--to",
        required=True,
        help="Number to call, in E.164 format (e.g. +15551234567)",
    )
    parser.add_argument(
        "--user-id",
        help="The user ID to fetch from the database",
        default="",
    )
    parser.add_argument(
        "--room",
        default=None,
        help="Room name to use. Defaults to a generated one.",
    )
    args = parser.parse_args()

    if not E164.match(args.to) and not args.to.startswith("sip:"):
        print(f"Warning: {args.to} does not look like an E.164 phone number or SIP URI.")

    user_id = args.user_id if args.user_id else args.to
    
    room_name = args.room or f"outbound-{uuid.uuid4().hex[:8]}"

    asyncio.run(dial(args.to, room_name, user_id))

    print(f"Dispatched {AGENT_NAME} to room '{room_name}' to call {args.to}.")
    print("Watch the worker terminal for call progress.")


if __name__ == "__main__":
    main()
