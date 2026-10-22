import hmac

import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse

from app.db import SessionLocal
from app.auth.models import User
from app.llm_chat.config import get_llm_settings

_settings = get_llm_settings()
mcp = FastMCP("llm-chat-tools", host=_settings.mcp_server_host, port=_settings.mcp_server_port)


class BearerAuth:
    """Reject any HTTP request that doesn't carry the shared token."""

    def __init__(self, app, token: str):
        self.app = app
        self.expected = f"Bearer {token}".encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            sent = dict(scope["headers"]).get(b"authorization", b"")
            if not hmac.compare_digest(sent, self.expected):
                resp = JSONResponse({"detail": "Unauthorized"}, status_code=401)
                return await resp(scope, receive, send)
        await self.app(scope, receive, send)


@mcp.tool()
def get_employee_details(email: str) -> str:
    """Look up employees' role and account status. Accepts a full email or just a
    name such as 'alice'. Only the part before '@' is matched, so never guess a domain."""
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.email.ilike(f"{email.split('@')[0]}%")).limit(5).all()
        if not users:
            return f"No employee found matching '{email}'."
        return "\n".join(
            f"{u.email} — role: {u.role.name if u.role else 'no role assigned'}, "
            f"status: {'active' if u.is_active else 'inactive'}, member since {u.created_at.date()}."
            for u in users
        )
    finally:
        db.close()


if __name__ == "__main__":
    if not _settings.mcp_auth_token:
        raise SystemExit("MCP_AUTH_TOKEN is not set; refusing to start an open MCP server.")
    # ponytail: one shared token, no per-user identity; move to OAuth if MCP gets external clients
    uvicorn.run(BearerAuth(mcp.streamable_http_app(), _settings.mcp_auth_token),
                host=_settings.mcp_server_host, port=_settings.mcp_server_port)