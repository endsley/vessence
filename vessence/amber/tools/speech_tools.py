import os
import logging
import tempfile
from pathlib import Path
from typing_extensions import override
from google.adk.tools.base_tool import BaseTool
from google.genai import types

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT))

from jane.config import VAULT_DIR

logger = logging.getLogger('google_adk.tools.speech_tool')

# Microsoft Edge neural voices — good defaults
VOICE_MAP = {
    "aria":    "en-US-AriaNeural",      # Female, warm
    "jenny":   "en-US-JennyNeural",     # Female, friendly
    "sara":    "en-US-SaraNeural",      # Female, casual
    "guy":     "en-US-GuyNeural",       # Male, casual
    "davis":   "en-US-DavisNeural",     # Male, warm
    "sonia":   "en-GB-SoniaNeural",     # British Female
    "ryan":    "en-GB-RyanNeural",      # British Male
    "natasha": "en-AU-NatashaNeural",   # Australian Female
}

DEFAULT_VOICE = "jenny"


class TextToSpeechTool(BaseTool):
    """
    A tool that generates speech from text using Microsoft Edge TTS.
    Fast, high-quality neural voices with no local model loading.
    """

    def __init__(self, **kwargs):
        super().__init__(
            name="generate_speech",
            description=(
                "Converts text into high-quality human speech (audio) and saves it "
                "to the vault. Returns the filename. ONLY call this when the user "
                "EXPLICITLY asks to hear your voice, requests an audio/voice message, "
                "or asks you to 'speak' something. Do NOT call this for regular text responses."
            ),
            **kwargs
        )
        self.vault_dir = os.path.join(VAULT_DIR, 'audio')
        os.makedirs(self.vault_dir, exist_ok=True)

    def _get_declaration(self) -> types.FunctionDeclaration:
        voice_desc = ", ".join(f"'{k}' ({VOICE_MAP[k].split('-')[1]} {VOICE_MAP[k].replace('Neural','').split('-')[-1]})"
                               for k in VOICE_MAP)
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "text": types.Schema(type="STRING", description="The exact words you want to say."),
                    "filename": types.Schema(type="STRING", description="Optional: Name of the file to save (must end in .mp3)."),
                    "voice": types.Schema(
                        type="STRING",
                        description=f"Optional: The voice to use. Available: {voice_desc}. Default: '{DEFAULT_VOICE}'."
                    )
                },
                required=["text"]
            )
        )

    async def run_async(
        self,
        *,
        args: dict,
        tool_context
    ) -> list:
        text = args.get("text")
        filename = args.get("filename", "my_voice_message.mp3")
        voice_key = args.get("voice", DEFAULT_VOICE).lower()

        if not text:
            return [{"text": "ERROR: 'text' is required to generate speech."}]

        # Resolve voice name
        voice = VOICE_MAP.get(voice_key, VOICE_MAP[DEFAULT_VOICE])

        if not filename.endswith('.mp3'):
            filename = filename.rsplit('.', 1)[0] + '.mp3'

        target_path = os.path.join(self.vault_dir, filename)

        # Handle duplicates
        counter = 1
        base, ext = os.path.splitext(filename)
        while os.path.exists(target_path):
            filename = f"{base}_{counter}{ext}"
            target_path = os.path.join(self.vault_dir, filename)
            counter += 1

        try:
            import edge_tts

            logger.info(f"Generating speech ({voice}) for text: {text[:50]}...")
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(target_path)

            return [{
                "text": f"Success! Here is my voice message using voice '{voice_key}':",
                "file_data": {
                    "file_uri": target_path,
                    "mime_type": "audio/mpeg"
                }
            }]
        except Exception as e:
            logger.error(f"TTS Error: {e}")
            return [{"text": f"Failed to generate speech: {e}"}]
