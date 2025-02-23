import logging
import re

logger = logging.getLogger(__name__)

def escape_markdown(text: str) -> str:
    """
    Handle Markdown formatting, converting double asterisks to single and escaping special characters.
    Only escape characters that need to be escaped for MarkdownV2, preserving formatting characters.
    """
    try:
        preview_length = 333
        logger.info(f"Original text (first {preview_length} chars): {text[:preview_length]}...")

        # First remove any existing backslashes
        text = text.replace('\\', '')

        # Convert **text** to *text* using regex to ensure pairs
        text = re.sub(r'\*\*(.*?)\*\*', r'*\1*', text)

        # Escape only the special characters that need escaping
        escape_chars = r"!#>+-=|{}.()"
        for char in escape_chars:
            text = text.replace(char, f'\\{char}')

        logger.info(f"Escaped text (first {preview_length} chars): {text[:preview_length]}...")
        return text

    except Exception as e:
        logger.error(f"Error while escaping markdown: {str(e)}")
        return text

def markdown_to_html(text: str) -> str:
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)  # bold
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)      # italic
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text) # code
    text = re.sub(r'~~(.*?)~~', r'<s>\1</s>', text)     # strikethrough
    return text
