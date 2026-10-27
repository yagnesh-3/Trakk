"""Run the Project Tracker MCP server over stdio.

Environment:
    PT_API_TOKEN  required: a personal API token (create one under "API tokens")
    PT_API_URL    API origin, default http://localhost:8100
    PT_WEB_URL    web app origin used for issue links, default http://localhost:5180
                  (set to "" to omit links)
"""

import logging
import os
import sys

from tracker_mcp.client import TrackerClient
from tracker_mcp.server import build_server


def main() -> int:
    token = os.environ.get("PT_API_TOKEN", "").strip()
    if not token:
        print("PT_API_TOKEN is not set. Create a token in the tracker under API tokens.", file=sys.stderr)
        return 1
    api_url = os.environ.get("PT_API_URL", "http://localhost:8100")
    web_url = os.environ.get("PT_WEB_URL", "http://localhost:5180") or None
    # httpx logs every request at INFO; keep the client's MCP log pane readable.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    build_server(TrackerClient(api_url, token), web_url).run("stdio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
