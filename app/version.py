# ── App version ───────────────────────────────────────────────────────────────
# This file is auto-updated by running:  python app/version.py
# Do not edit VERSION manually — run the script before each build instead.

VERSION     = "v1.0.0"
GITHUB_REPO = "your-username/Garlic-Phone"   # ← set this once


# ── Self-update logic (only runs when executed directly) ──────────────────────

if __name__ == "__main__":
    import urllib.request
    import json
    import os
    import sys
    import re

    print(f"Fetching latest release from github.com/{GITHUB_REPO}...")

    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        req = urllib.request.Request(url, headers={"User-Agent": "GarlicPhone-Builder"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())

        tag = data.get("tag_name", "")
        if not tag:
            raise ValueError("No release tag found — have you published a GitHub release yet?")

        # Rewrite this file with the new version
        this_file = os.path.abspath(__file__)
        with open(this_file, "r") as f:
            src = f.read()

        src = re.sub(
            r'^VERSION\s*=\s*".*?"',
            f'VERSION     = "{tag}"',
            src,
            flags=re.MULTILINE
        )

        with open(this_file, "w") as f:
            f.write(src)

        print(f"✓  VERSION updated → {tag}")
        print()
        print("Now run:  pyinstaller garlic_phone.spec")

    except Exception as e:
        print(f"✗  Failed: {e}")
        print("Check that GITHUB_REPO is correct and you have a published release.")
        sys.exit(1)