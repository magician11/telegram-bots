import logging
import re

logger = logging.getLogger(__name__)

def escape_markdown(text: str) -> str:
    """
    Handle Markdown formatting, assuming text comes with pre-escaped markers.
    """
    # First unescape any pre-escaped Markdown formatting characters
    markdown_chars = r'*_~[]`'
    text = re.sub(r'\\([' + re.escape(markdown_chars) + r'])', r'\1', text)

    # Then escape only non-formatting special characters
    escape_chars = r"!#>+-=|{}.()"

    try:
        preview_length = 100
        logger.info(f"Original text (first {preview_length} chars): {text[:preview_length]}...")

        escaped_text = re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

        logger.info(f"Escaped text (first {preview_length} chars): {escaped_text[:preview_length]}...")
        return escaped_text

    except Exception as e:
        logger.error(f"Error while escaping markdown: {str(e)}")
        return text
