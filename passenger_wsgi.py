"""Passenger entry point for cPanel "Setup Python App".

cPanel Passenger expects a WSGI callable named `application` at this path.
Our actual server is an ASGI app (Starlette + MCP SSE), so we bridge it
through a2wsgi.

cPanel will create the virtualenv automatically and install dependencies
from requirements.txt. After any change, restart the app from the cPanel
"Setup Python App" UI (or `touch tmp/restart.txt` in the app directory).
"""

import os
import sys

# Add this directory to sys.path so `import ptpge_mcp` works.
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from a2wsgi import ASGIMiddleware  # noqa: E402

from ptpge_mcp.server import app as asgi_app  # noqa: E402

# WSGI callable that Passenger will invoke.
application = ASGIMiddleware(asgi_app)
