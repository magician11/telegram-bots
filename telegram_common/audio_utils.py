import tempfile
import logging
import os
from typing import BinaryIO, Optional
from io import BytesIO

logger = logging.getLogger(__name__)

class AudioFileManager:
    """Manages temporary audio files safely."""

    @staticmethod
    def create_temp_file(suffix: str = ".ogg") -> tempfile.NamedTemporaryFile:
        """Create a temporary file for audio processing."""
        return tempfile.NamedTemporaryFile(suffix=suffix, delete=False)

    @staticmethod
    def cleanup_temp_file(file_path: str):
        """Safely delete temporary file."""
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
                logger.debug(f"Cleaned up temp file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {file_path}: {str(e)}")

    @staticmethod
    def bytes_to_file(audio_bytes: bytes, suffix: str = ".ogg") -> tempfile.NamedTemporaryFile:
        """Convert bytes to temporary file."""
        temp_file = AudioFileManager.create_temp_file(suffix)
        temp_file.write(audio_bytes)
        temp_file.flush()
        temp_file.seek(0)
        return temp_file

def validate_audio_size(file_size: int, max_size_mb: int = 20) -> bool:
    """Validate audio file size."""
    max_size_bytes = max_size_mb * 1024 * 1024
    return file_size <= max_size_bytes

def format_file_size(size_bytes: int) -> str:
    """Format file size for user display."""
    for unit in ['B', 'KB', 'MB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} GB"
