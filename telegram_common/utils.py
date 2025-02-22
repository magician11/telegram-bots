import logging

logger = logging.getLogger(__name__)

def escape_markdown(text: str) -> str:
    """
    Escape reserved MarkdownV2 characters while preserving supported Markdown formatting.
    """
    escape_chars = r'_*[]()~`>#+-=|{}.!'

    try:
        # Log the original text (but limit length for log readability)
        preview_length = 100
        logger.debug(f"Original text (first {preview_length} chars): {text[:preview_length]}...")

        # Escape special characters
        escaped_text = ''.join('\\' + c if c in escape_chars else c for c in text)

        # Log the escaped text and any changes made
        logger.debug(f"Escaped text (first {preview_length} chars): {escaped_text[:preview_length]}...")
        if text != escaped_text:
            # Log which characters were escaped and their positions
            changes = [(i, c) for i, c in enumerate(text) if c in escape_chars]
            logger.debug(f"Escaped characters (position, char): {changes}")

        return escaped_text

    except Exception as e:
        logger.error(f"Error while escaping markdown: {str(e)}")
        # Return the original text if something goes wrong
        return text
