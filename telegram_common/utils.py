import logging
import re

logger = logging.getLogger(__name__)

def escape_markdown(text: str) -> str:
    """
    Escape reserved MarkdownV2 characters while preserving Markdown formatting.
    """
    # Only escape characters that aren't used for formatting
    escape_chars = r"!#>+-=|{}.()"

    try:
        preview_length = 100
        logger.info(f"Original text (first {preview_length} chars): {text[:preview_length]}...")

        # Escape special characters that aren't used for formatting
        escaped_text = re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

        logger.info(f"Escaped text (first {preview_length} chars): {escaped_text[:preview_length]}...")
        return escaped_text

    except Exception as e:
        logger.error(f"Error while escaping markdown: {str(e)}")
        return text
