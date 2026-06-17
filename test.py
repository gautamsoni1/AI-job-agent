"""
SELF-CONTAINED diagnostic script for the LinkedIn Apify actor.

Just run this:
    python test_linkedin_actor.py

It needs ZERO other code changes — it loads APIFY_TOKEN from your .env
(via python-dotenv, falls back to a plain os.environ read if that's not
installed) and has the actor ID hardcoded below. It does NOT import
app.config or app.services.apify_service, so it can't be broken by
anything else in your codebase — if THIS file fails, the problem is the
actor/token/network, not your project code.

What it does, in order:
  1. Loads APIFY_TOKEN from .env / environment.
  2. Calls curious_coder/linkedin-jobs-scraper directly with a few input
     shapes (since the exact schema isn't confirmed) and reports which
     one (if any) returns data.
  3. Dumps the raw keys of the first item it gets back, so you can see
     the actor's real field names with your own eyes.
  4. Tells you in plain language what to do next based on the result.
"""
import json
import sys

# ---------------------------------------------------------------------
# CONFIG — only these few lines matter; everything else is diagnostics
# ---------------------------------------------------------------------
ACTOR_ID = "curious_coder/linkedin-jobs-scraper"
TEST_KEYWORDS = "Python Developer"
TEST_LOCATION = "Bangalore"
MAX_ITEMS = 10
# ---------------------------------------------------------------------

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("(python-dotenv not installed — relying on already-exported env vars)")

import os

try:
    from apify_client import ApifyClient
except ImportError:
    print("FAIL: apify-client is not installed in this environment.")
    print("      Run: pip install apify-client")
    sys.exit(1)


def get_token() -> str:
    token = os.environ.get("APIFY_TOKEN", "").strip()
    if not token or token == "apify_api_token":
        print("FAIL: APIFY_TOKEN not found in environment or .env file.")
        print("      Make sure your .env (in the directory you're running")
        print("      this script from) has a line like:")
        print("        APIFY_TOKEN=apify_api_xxxxxxxxxxxxxxxxxxxx")
        sys.exit(1)
    return token


def build_url(keywords: str, location: str) -> str:
    from urllib.parse import urlencode
    params = urlencode({"keywords": keywords, "location": location})
    return f"https://www.linkedin.com/jobs/search/?{params}"


def try_run(client: "ApifyClient", label: str, run_input: dict) -> list[dict]:
    print()
    print(f"--- Attempt: {label} ---")
    print("Input sent:")
    print(json.dumps(run_input, indent=2))
    try:
        run = client.actor(ACTOR_ID).call(run_input=run_input)
    except Exception as e:
        print(f"RESULT: Actor call raised an exception -> {e}")
        return []

    dataset_id = (
        run.get("defaultDatasetId")
        if isinstance(run, dict)
        else getattr(run, "default_dataset_id", None) or getattr(run, "defaultDatasetId", None)
    )
    if not dataset_id:
        print("RESULT: No dataset ID returned from the run — actor likely failed.")
        return []

    items = list(client.dataset(dataset_id).iterate_items())
    print(f"RESULT: {len(items)} item(s) returned.")
    return items


def main():
    print("=" * 70)
    print(f"Testing Apify actor: {ACTOR_ID}")
    print("=" * 70)

    token = get_token()
    print(f"OK: APIFY_TOKEN loaded (length={len(token)})")
    client = ApifyClient(token)

    search_url = build_url(TEST_KEYWORDS, TEST_LOCATION)

    # Schema confirmed by actual actor validation error on first run:
    #   "Field input.count must be >= 10"
    #   "Field input.urls is required"
    # So urls is mandatory and count must be >= 10. We try the confirmed
    # shape first, then a couple of close variants in case more fields
    # are silently required once count is fixed.
    attempts = [
        ("urls + count(10)", {
            "urls": [search_url],
            "count": MAX_ITEMS,
        }),
        ("urls + count(10) + proxy", {
            "urls": [search_url],
            "count": MAX_ITEMS,
            "proxy": {"useApifyProxy": True},
        }),
        ("urls + count(10) + scrapeCompany", {
            "urls": [search_url],
            "count": MAX_ITEMS,
            "scrapeCompany": False,
        }),
    ]

    successful_items = []
    winning_label = None
    for label, run_input in attempts:
        items = try_run(client, label, run_input)
        if items:
            successful_items = items
            winning_label = label
            break

    print()
    print("=" * 70)
    print("VERDICT")
    print("=" * 70)

    if not successful_items:
        print("FAIL: None of the tried input shapes returned any data.")
        print()
        print("This means one of:")
        print("  1. None of the input shapes above match this actor's real schema")
        print("     -> Go to https://console.apify.com, open this actor, click")
        print("        'Try for free', and check the 'Input' tab for exact field")
        print("        names. Tell me those field names and I'll fix the code.")
        print("  2. The actor needs LinkedIn cookies/auth you haven't supplied")
        print("     -> Check the actor's README on Apify Store for auth requirements.")
        print("  3. The actor is being blocked by LinkedIn (rate-limit/anti-bot)")
        print("     -> Check the run's logs in Apify console for error details.")
        print("  4. APIFY_TOKEN doesn't have access to this actor (e.g. needs rent)")
        print("     -> Check if this actor requires a paid Apify plan or 'rental'.")
        sys.exit(1)

    print(f"SUCCESS: Input shape '{winning_label}' works — actor returned data.")
    print()
    print("Raw keys of first item (USE THESE to fix _normalize_linkedin):")
    print(list(successful_items[0].keys()))
    print()
    print("First item (truncated to 2000 chars):")
    print(json.dumps(successful_items[0], indent=2, default=str)[:2000])


if __name__ == "__main__":
    main()