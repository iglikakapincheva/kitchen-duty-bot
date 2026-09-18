def main():
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        print("ERROR: SLACK_BOT_TOKEN environment variable not set.")
        sys.exit(1)

    dry_run = os.environ.get("DRY_RUN", "false").lower() == "true"
    if dry_run:
        print("=== DRY RUN — no message will be posted, no state will be saved ===")

    client = WebClient(token=token)
    state = load_state()

    members, channel_id = get_channel_members(client)
    if len(members) < 4:
        print(f"ERROR: #{CHANNEL_NAME} has fewer than 4 human members.")
        sys.exit(1)

    this_week = pick_next_four(state, members)
    message = build_message(state.get("last_week", []), this_week)

    if dry_run:
        print("----- Message that WOULD be posted -----")
        print(message)
        print("-----------------------------------------")
        print("This week's 4 (not saved):", this_week)
        return

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
