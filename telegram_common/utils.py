import logging

logger = logging.getLogger(__name__)

def escape_markdown(text: str) -> str:
    """
    Escape reserved MarkdownV2 characters while preserving supported Markdown formatting
    and already escaped characters.
    """
    escape_chars = r'_*[]()~`>#+-=|{}.!'

    try:
        # Log the original text (but limit length for log readability)
        preview_length = 333
        logger.info(f"Original text (first {preview_length} chars): {text[:preview_length]}...")

        # Process the text character by character, keeping track of escapes
        result = []
        i = 0
        while i < len(text):
            # If we find a backslash, keep it and the next character as-is
            if text[i] == '\\' and i + 1 < len(text) and text[i + 1] in escape_chars:
                result.append(text[i:i+2])
                i += 2
            # If we find an unescaped special character, escape it
            elif text[i] in escape_chars:
                result.append('\\' + text[i])
                i += 1
            # For normal characters, just append them
            else:
                result.append(text[i])
                i += 1

        escaped_text = ''.join(result)

        # Log the escaped text and any changes made
        logger.info(f"Escaped text (first {preview_length} chars): {escaped_text[:preview_length]}...")
        if text != escaped_text:
            # Log which characters were escaped and their positions
            changes = [(i, c) for i, c in enumerate(text) if c in escape_chars and (i == 0 or text[i-1] != '\\')]
            logger.info(f"Escaped characters (position, char): {changes}")

        return escaped_text

    except Exception as e:
        logger.error(f"Error while escaping markdown: {str(e)}")
        # Return the original text if something goes wrong
        return text
