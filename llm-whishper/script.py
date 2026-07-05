import os
import time
from faster_whisper import WhisperModel

# ==========================================
# Configuration
# ==========================================

VIDEO_PATH = r"D:\Videos\lecture.mp4"   # <-- Change this
MODEL_SIZE = "distil-large-v3"          # or "small", "medium", "large-v3"

DEVICE = "cpu"
COMPUTE_TYPE = "int8"

# ==========================================

print("Loading model...")

start = time.time()

model = WhisperModel(
    MODEL_SIZE,
    device=DEVICE,
    compute_type=COMPUTE_TYPE
)

print("Model loaded.")
print("Detecting language and generating subtitles...\n")

segments, info = model.transcribe(
    VIDEO_PATH,
    task="translate",      # Hindi -> English
    beam_size=5,
    vad_filter=True
)

print(f"Detected language: {info.language}")

output_file = os.path.splitext(VIDEO_PATH)[0] + ".srt"


def ts(seconds):
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)

    return f"{hrs:02}:{mins:02}:{secs:02},{ms:03}"


count = 0

with open(output_file, "w", encoding="utf-8") as f:

    for count, segment in enumerate(segments, start=1):

        print(
            f"[{count}] "
            f"{segment.start:8.1f}s -> {segment.end:8.1f}s"
        )

        f.write(f"{count}\n")
        f.write(f"{ts(segment.start)} --> {ts(segment.end)}\n")
        f.write(segment.text.strip() + "\n\n")

        # Save immediately
        f.flush()

elapsed = time.time() - start

print("\n===================================")
print("Completed!")
print(f"Subtitles : {output_file}")
print(f"Segments  : {count}")
print(f"Time taken: {elapsed/60:.1f} minutes")
print("===================================")
