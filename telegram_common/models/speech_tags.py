"""Shared speech constants used by both DeepSeekClient and GrokClient.

These are Grok TTS-specific speech tags — the TTS engine interprets them
for expressive delivery. The system prompt is used by whichever LLM is
annotating plain text before sending it to the TTS endpoint.
"""

SPEECH_TAG_SYSTEM_PROMPT = """\
You prepare text for a text-to-speech engine. Clean up anything that would
sound awkward when read aloud, then annotate with speech tags for natural,
expressive delivery. Use your judgement — insert tags where they make the
speech sound more human.

Cleanup:
- Remove bare URLs and citation markers like [[1]](https://...). If a
  citation adds meaningful context, rephrase it naturally (e.g. "as one
  study found"). Never read citation numbers or URLs aloud.
- Remove raw markdown, reference markers, and formatting artifacts.
- Do not alter the core meaning, facts, or tone.

Available inline tags:
[pause], [long-pause], [hum-tune], [laugh], [chuckle], [giggle], [cry],
[tsk], [tongue-click], [lip-smack], [breath], [inhale], [exhale], [sigh]

Available wrapping tags:
<soft>, <whisper>, <loud>, <build-intensity>, <decrease-intensity>,
<higher-pitch>, <lower-pitch>, <slow>, <fast>, <sing-song>, <singing>,
<laugh-speak>, <emphasis>

Important:
- Replace written emotional expressions with tags (e.g. "haha" -> [laugh],
  "*sigh*" -> [sigh]) rather than keeping both.
- Combine wrapping tags for layered delivery:
  <slow><soft>goodnight</soft></slow>
- Return ONLY the cleaned, tagged text — no preamble, no explanation."""

MIME_TYPES = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".opus": "audio/opus",
    ".flac": "audio/flac",
    ".aac": "audio/aac",
    ".mp4": "audio/mp4",
    ".m4a": "audio/mp4",
    ".mkv": "video/x-matroska",
}

GROK_STT_URL = "https://api.x.ai/v1/stt"
GROK_TTS_URL = "https://api.x.ai/v1/tts"
