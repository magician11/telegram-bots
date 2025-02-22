import re

def escape_markdown(text: str) -> str:
    """
    Escape reserved MarkdownV2 characters while preserving supported Markdown formatting.
    """
    escape_chars = r"!#>+-=|{}.()"
    text = re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)
    return text
