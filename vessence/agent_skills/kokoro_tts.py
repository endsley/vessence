import sys
import argparse
import numpy as np
import soundfile as sf
from kokoro import KPipeline

def main():
    parser = argparse.ArgumentParser(description="Generate TTS using Kokoro-82M")
    parser.add_argument("--text", type=str, required=True, help="Text to speak")
    parser.add_argument("--output", type=str, required=True, help="Output .wav path")
    parser.add_argument("--voice", type=str, default="af_heart", help="Voice ID to use")
    
    args = parser.parse_args()

    # Suppress output to avoid polluting stdout if called via subprocess
    devnull = open('/dev/null', 'w')  # noqa: SIM115
    sys.stdout = devnull

    try:
        pipeline = KPipeline(lang_code='a')
        generator = pipeline(
            args.text, voice=args.voice, speed=1, split_pattern=r'\n+'
        )

        audio_chunks = []
        for i, (gs, ps, audio) in enumerate(generator):
            audio_chunks.append(audio)

        if audio_chunks:
            final_audio = np.concatenate(audio_chunks)
            sf.write(args.output, final_audio, 24000)
        else:
            sys.stdout = sys.__stdout__
            print("ERROR: TTS pipeline produced no audio chunks.", file=sys.stderr)
            sys.exit(1)

    finally:
        sys.stdout = sys.__stdout__
        devnull.close()

if __name__ == "__main__":
    main()
