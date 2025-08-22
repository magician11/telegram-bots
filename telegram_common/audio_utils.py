import tempfile
import logging
import os
from typing import BinaryIO, Optional
from io import BytesIO
import subprocess

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

    @staticmethod
    def convert_to_supported_format(input_path: str, output_suffix: str = ".mp3") -> str:
        """Convert audio to a supported format (e.g., MP3) using FFmpeg."""
        output_path = input_path + output_suffix
        try:
            result = subprocess.run(
                ["ffmpeg", "-i", input_path, "-codec:a", "libmp3lame", "-q:a", "2", output_path],  # q:a 2 for good quality/size
                check=True,
                capture_output=True,
            )
            if result.returncode == 0:
                logger.info(f"Converted {input_path} to {output_path}")
                return output_path
            else:
                raise ValueError("FFmpeg conversion failed")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr.decode()}")
            raise ValueError("Audio conversion failed")
        except FileNotFoundError:
            logger.error("FFmpeg not found - ensure it's installed in the environment")
            raise RuntimeError("FFmpeg is required for audio conversion")

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
