#!/usr/bin/env python3
"""
MCP Bridge: stdio-to-HTTP bridge for Claude Desktop.

This script allows Claude Desktop (which only supports stdio transport) to connect
to a Hindsight API running in Docker (HTTP transport).

Usage in claude_desktop_config.json:
{
  "mcpServers": {
    "hindsight": {
      "command": "python3",
      "args": ["/path/to/mcp-bridge.py"],
      "env": {
        "HINDSIGHT_URL": "http://localhost:8888",
        "HINDSIGHT_BANK_ID": "claude-desktop"
      }
    }
  }
}
"""

import json
import os
import sys
import urllib.request
import urllib.error

# Configuration from environment
HINDSIGHT_URL = os.environ.get("HINDSIGHT_URL", "http://localhost:8888")
HINDSIGHT_BANK_ID = os.environ.get("HINDSIGHT_BANK_ID", "claude-desktop")
BASE_URL = f"{HINDSIGHT_URL}/v1/default/banks/{HINDSIGHT_BANK_ID}"


def http_post(endpoint: str, data: dict) -> dict:
    """Make an HTTP POST request."""
    url = f"{BASE_URL}/{endpoint}"
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"error": f"Connection failed: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


def retain(content: str, context: str = "general") -> dict:
    """Store a memory via HTTP API."""
    result = http_post(
        "memories",
        {
            "items": [{"content": content, "context": context}],
        },
    )
    if "error" not in result:
        return {"status": "accepted", "message": "Memory storage initiated"}
    return result


def recall(query: str, max_tokens: int = 4096) -> dict:
    """Search memories via HTTP API."""
    result = http_post(
        "memories/recall",
        {
            "query": query,
            "max_tokens": max_tokens,
        },
    )
    if "error" in result:
        return {"error": result["error"], "results": []}
    return result


# MCP Protocol implementation
TOOLS = [
    {
        "name": "retain",
        "description": """Store important information to long-term memory.

Use this tool PROACTIVELY whenever the user shares:
- Personal facts, preferences, or interests
- Important events or milestones
- User history, experiences, or background
- Decisions, opinions, or stated preferences
- Goals, plans, or future intentions
- Relationships or people mentioned
- Work context, projects, or responsibilities""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The fact/memory to store (be specific and include relevant details)",
                },
                "context": {
                    "type": "string",
                    "description": "Category for the memory (e.g., 'preferences', 'work', 'hobbies', 'family')",
                    "default": "general",
                },
            },
            "required": ["content"],
        },
    },
    {
        "name": "recall",
        "description": """Search memories to provide personalized, context-aware responses.

Use this tool PROACTIVELY to:
- Check user's preferences before making suggestions
- Recall user's history to provide continuity
- Remember user's goals and context
- Personalize responses based on past interactions""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query",
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "Maximum tokens in the response",
                    "default": 4096,
                },
            },
            "required": ["query"],
        },
    },
]


def handle_request(request: dict) -> dict | None:
    """Handle an MCP JSON-RPC request."""
    method = request.get("method", "")
    req_id = request.get("id")
    params = request.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "hindsight-bridge", "version": "1.0.0"},
            },
        }

    elif method == "notifications/initialized":
        return None  # No response for notifications

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS},
        }

    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if tool_name == "retain":
            result = retain(
                content=arguments.get("content", ""),
                context=arguments.get("context", "general"),
            )
        elif tool_name == "recall":
            result = recall(
                query=arguments.get("query", ""),
                max_tokens=arguments.get("max_tokens", 4096),
            )
        else:
            result = {"error": f"Unknown tool: {tool_name}"}

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
            },
        }

    elif method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    else:
        # Unknown method - return error
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }


def main():
    """Main loop: read JSON-RPC requests from stdin, write responses to stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
            response = handle_request(request)

            if response is not None:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()

        except json.JSONDecodeError as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {e}"},
            }
            sys.stdout.write(json.dumps(error_response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
