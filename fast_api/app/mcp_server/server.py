from mcp.server.fastmcp import FastMCP

from app.db import SessionLocal
from app.auth.models import User
from app.llm_chat.config import get_llm_settings

_settings = get_llm_settings()
mcp = FastMCP("llm-chat-tools", host=_settings.mcp_server_host, port=_settings.mcp_server_port)


@mcp.tool()
def get_employee_details(email: str) -> str:
    """Look up an employee's role and account status by email address."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            return f"No employee found with email {email}."
        role = user.role.name if user.role else "no role assigned"
        status = "active" if user.is_active else "inactive"
        return f"{user.email} — role: {role}, status: {status}, member since {user.created_at.date()}."
    finally:
        db.close()


if __name__ == "__main__":
    mcp.run(transport="streamable-http")