"""
Kitchen Duty Rotation Bot
=========================
Runs weekly (via GitHub Actions). Each run:
  1. Reads state.json (who's left in the current rotation cycle, who was
     picked last week).
  2. Pulls the current member list of #berlinoffice from Slack.
  3. Picks 4 people for THIS week, without repeating anyone until every
     member has had a turn in the current cycle.
  4. Posts the message, thanking LAST week's 4 and announcing THIS week's 4.
  5. Saves the updated state back to state.json.

State is committed back to the git repo by the GitHub Actions workflow
after every run, so the rotation memory persists between runs.
"""

import json
import os
import random
import sys
from pathlib import Path

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

STATE_PATH = Path(__file__).parent / "state.json"
CHANNEL_NAME = "berlinoffice"

MESSAGE_TEMPLATE = """🧽 Kitchen Duty Rotation
Hi <!channel>,

A big thank you 🙌 to our Kitchen Duty heroes from last week{last_week_thanks} — great job! Your effort and commitment are truly appreciated.

Here is the new rotation for next week:

   {this_week_mentions}

Don't forget your mission 🎯:
- ☕ Kindly remind teammates to collect their cups and glasses
- 🧴 If you are on the Sales floor, please make sure to bring all empty cups and glasses down to the kitchen
- 🍽️ Run the dishwasher when needed, especially after lunch and/or at the end of the day
- 🔪 Make sure cutting items are clean and returned to their proper place

Coffee machine care ☕:
- 💧 Clean the drip tray
- 🌱 Empty the coffee grounds
- 🚰 Refill the water

Thank you 💛 for helping keep our shared space clean and enjoyable for everyone!"""

EXCLUDED_EMAIL_MARKER = ".ext"  # skip anyone whose email local-part contains this


def load_state() -> dict:
    """Read state.json. If it doesn't exist yet, start fresh."""
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"used_pool": [], "last_week": []}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2))


def get_channel_members(client: WebClient) -> list[str]:
    """Return user IDs of all human (non-bot) members of #berlinoffice."""
    # Find the channel ID by name
    channel_id = None
    cursor = None
    while True:
        resp = client.conversations_list(types="public_channel,private_channel", cursor=cursor, limit=200)
        for ch in resp["channels"]:
            if ch["name"] == CHANNEL_NAME:
                channel_id = ch["id"]
                break
        if channel_id or not resp.get("response_metadata", {}).get("next_cursor"):
            break
        cursor = resp["response_metadata"]["next_cursor"]

    if not channel_id:
        raise RuntimeError(f"Could not find channel #{CHANNEL_NAME}")

    # Get member IDs
    member_ids = []
    cursor = None
    while True:
        resp = client.conversations_members(channel=channel_id, cursor=cursor, limit=200)
        member_ids.extend(resp["members"])
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    # Filter out bots and anyone whose email marks them as external
    # (email local-part contains ".ext", e.g. john.ext@andercore.com)
    human_ids = []
    excluded = []
    missing_email = []
    for uid in member_ids:
        info = client.users_info(user=uid)["user"]
        if info.get("is_bot")
