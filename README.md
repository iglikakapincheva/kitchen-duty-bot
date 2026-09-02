# Kitchen Duty Rotation Bot — Setup Guide

This posts your Kitchen Duty message to **#berlinoffice** every Friday,
automatically, forever — with no repeats until everyone in the channel
has had a turn.

## How it works (the short version)

- **kitchen_duty.py** — the actual logic: pull channel members → pick 4 →
  post message → remember who was picked.
- **state.json** — a tiny memory file. It stores who's still "owed" a
  turn, and who was picked last week (so they can be thanked by name).
- **.github/workflows/kitchen-duty.yml** — tells GitHub "run kitchen_duty.py
  every Friday at 13:00 UTC." GitHub runs it on their own servers — nothing
  runs on your laptop.
- Each run **commits the updated state.json back to the repo**, so next
  Friday's run picks up where this one left off.

## Setup — two parts

### Part 1: Create a Slack bot (~5 min)

1. Go to https://api.slack.com/apps → **Create New App** → **From scratch**.
2. Name it (e.g. "Kitchen Duty Bot"), pick your Andercore workspace.
3. In the left sidebar, go to **OAuth & Permissions**.
4. Under **Scopes → Bot Token Scopes**, add:
   - `channels:read`
   - `groups:read` (only needed if #berlinoffice is private)
   - `chat:write`
   - `users:read`
5. Scroll up, click **Install to Workspace**, approve it.
6. Copy the **Bot User OAuth Token** (starts with `xoxb-`). Keep this
   secret — treat it like a password.
7. In Slack, go to **#berlinoffice** → channel settings → **Integrations**
   → **Add an App** → add the bot you just created.

### Part 2: Deploy to GitHub (~5 min)

1. Go to https://github.com/new. Create a **private** repo, e.g.
   `kitchen-duty-bot`. Don't add a README (you already have one).
2. Upload all the files from this folder into that repo (drag-and-drop
   works on the GitHub web UI, or use `git push` if you're comfortable
   with git).
3. In the repo, go to **Settings → Secrets and variables → Actions →
   New repository secret**.
   - Name: `SLACK_BOT_TOKEN`
   - Value: the `xoxb-...` token from Part 1, step 6.
4. Go to the **Actions** tab → you should see "Kitchen Duty Rotation" →
   click **Run workflow** to test it immediately (don't wait for Friday).
5. Check #berlinoffice — the message should appear. Check the repo —
   `state.json` should now show 4 user IDs under `last_week`.

That's it. It will now run automatically every Friday at 13:00 UTC
(14:00 Berlin winter / 15:00 Berlin summer) with no further action from
you.

## Adjusting the day/time

Edit the `cron` line in `.github/workflows/kitchen-duty.yml`. Format is
`minute hour day month weekday` in UTC, weekday `5` = Friday.
Example: `0 12 * * 5` = 12:00 UTC every Friday.

## Adjusting daylight saving (optional)

Cron doesn't shift for DST. If you want it to land at exactly 14:00
Berlin time year-round, change the cron line twice a year (or just
accept the 1-hour drift for half the year — most people do).

## First run

The very first time this runs, there's no "last week" to thank yet —
the script automatically skips that name list and keeps the line
generic. From the second run onward, it thanks last week's 4 by name.
