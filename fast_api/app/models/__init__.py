"""Import every model module so all tables and string-based relationships are registered."""
from app.models import auth, customers, documents, llm_chat, tickets  # noqa: F401
