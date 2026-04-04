import sys
import soundfile as sf
from kokoro import KPipeline

def test_tts():
    print("Initializing Kokoro Pipeline...")
    # Initialize pipeline with American English
    pipeline = KPipeline(lang_code='a')

    text = "Hello Chieh! I am Kokoro, Amber's new local voice. I am running entirely on your GPU, which means my speech is private, fast, and completely free."
    
    print(f"Generating audio for: '{text}'")
    # Generate audio using the 'af_heart' voice
    generator = pipeline(
        text, voice='af_heart', # af_heart is a standard American Female voice
        speed=1, split_pattern=r'\n+'
    )

    for i, (gs, ps, audio) in enumerate(generator):
        output_file = f"/home/chieh/vessence/test_code/kokoro_test_output_{i}.wav"
        sf.write(output_file, audio, 24000)
        print(f"Success! Audio saved to {output_file}")

if __name__ == "__main__":
    test_tts()
