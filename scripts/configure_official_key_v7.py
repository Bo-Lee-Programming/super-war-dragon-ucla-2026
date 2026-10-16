"""Interactive local-only Official Agent Key setup. Never prints the key."""
from getpass import getpass
from pathlib import Path
import re

from dotenv import set_key


def main():
    root = Path(__file__).resolve().parents[1]
    print("Paste your own Official Agent Key from Agent Configuration.")
    print("Input is hidden. Nothing will be sent to the platform by this setup.")
    key = getpass("Official Agent Key: ").strip()
    if not re.fullmatch(r"eak_live_[0-9a-f]{64}", key):
        print("Invalid key format. Existing configuration was not changed.")
        return 1
    set_key(root / ".env", "ALTRUAGENT_OFFICIAL_AGENT_KEY", key)
    print("Saved locally in the starter .env. Never publish or share this file.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
