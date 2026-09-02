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
• ☕ Kindly remind teammates to collect their cups and glasses
• 🧴 If you are on the Sales floor, please make sure to bring all empty cups and glasses down to the kitchen
• 🍽️ Run the dishwasher when needed, especially after lunch and/or at the end of the day
• 🔪 Make sure cutting items are clean and returned to their proper place

Coffee machine care ☕:
• 💧 Clean the drip tray
• 🌱 Empty the coffee grounds
• 🚰 Refill the water

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
    for uid in member_ids:
        info = client.users_info(user=uid)["user"]
        if info.get("is_bot") or uid == "USLACKBOT":
            continue
        email = info.get("profile", {}).get("email", "")
        local_part = email.split("@")[0] if email else ""
        if EXCLUDED_EMAIL_MARKER in local_part:
            continue
        human_ids.append(uid)

    return human_ids, channel_id


def pick_next_four(state: dict, current_members: list[str]) -> list[str]:
    """Pick 4 people, respecting the no-repeat-until-cycle-ends rule."""
    # Drop anyone no longer in the channel; add anyone new to the pool
    pool = [uid for uid in state["used_pool"] if uid in current_members]
    for uid in current_members:
        if uid not in pool and uid not in state.get("_picked_this_cycle", []):
            pool.append(uid)

    # If fewer than 4 remain in the pool, reset: everyone's eligible again
    if len(pool) < 4:
        pool = list(current_members)

    random.shuffle(pool)
    picked = pool[:4]
    remaining = [uid for uid in pool if uid not in picked]

    state["used_pool"] = remaining
    return picked


def mention(uid: str) -> str:
    return f"<@{uid}>"


def build_message(last_week: list[str], this_week: list[str]) -> str:
    if last_week:
        last_week_thanks = " " + ", ".join(mention(u) for u in last_week)
    else:
        last_week_thanks = ""  # first-ever run: skip the names, keep line generic

    this_week_mentions = ", ".join(mention(u) for u in this_week[:-1])
    this_week_mentions += f" and {mention(this_week[-1])}"

    return MESSAGE_TEMPLATE.format(
        last_week_thanks=last_week_thanks,
        this_week_mentions=this_week_mentions,
    )


def main():
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        print("ERROR: SLACK_BOT_TOKEN environment variable not set.")
        sys.exit(1)

    client = WebClient(token=token)
    state = load_state()

    members, channel_id = get_channel_members(client)
    if len(members) < 4:
        print(f"ERROR: #{CHANNEL_NAME} has fewer than 4 human members.")
        sys.exit(1)

    this_week = pick_next_four(state, members)
    message = build_message(state.get("last_week", []), this_week)

    try:
        client.chat_postMessage(channel=channel_id, text=message)
    except SlackApiError as e:
        print(f"ERROR posting message: {e.response['error']}")
        sys.exit(1)

    state["last_week"] = this_week
    save_state(state)
    print("Posted successfully. This week's 4:", this_week)


if __name__ == "__main__":
    main()
