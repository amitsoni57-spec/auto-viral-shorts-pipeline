import os
import json
import asyncio
import requests
import subprocess
import ollama
import edge_tts
from faster_whisper import WhisperModel

# ==========================================
# 1. USER INPUT & VIRAL SCRIPT GENERATION
# ==========================================
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "YOUR_PEXELS_API_KEY_HERE")

TOPIC = input("Enter a video topic (e.g. 'Volcano Explosions', 'Space Exploration'): ")
print(f"\n[1/6] Auto-generating viral retention script for: '{TOPIC}'...")

prompt = f"""
You are an expert viral YouTube Shorts creator specializing in high-retention storytelling.
Write an intensely engaging 30-second script about '{TOPIC}'.

RULES FOR THE SCRIPT:
- Scene 1 MUST start with an incredible, attention-grabbing HOOK that makes scrolling impossible (e.g., "Nobody was supposed to survive this...", "This single mistake changed human history forever...").
- Keep sentences punchy, dramatic, and fast-paced.
- End with a mind-bending fact or open question to drive comments.
- Split into EXACTLY 6 scenes. Each scene should take ~5 seconds to speak (around 12-15 words).
- Provide precise, cinematic Pexels search terms (2-3 words) for dramatic stock footage.

Respond ONLY with valid JSON in this exact structure:
{{
  "scenes": [
    {{"text": "...", "search_term": "..."}},
    {{"text": "...", "search_term": "..."}},
    {{"text": "...", "search_term": "..."}},
    {{"text": "...", "search_term": "..."}},
    {{"text": "...", "search_term": "..."}},
    {{"text": "...", "search_term": "..."}}
  ]
}}
"""

response = ollama.generate(model='llama3.2', prompt=prompt, format='json')
script_data = json.loads(response['response'])
SCENES = script_data['scenes']

print("\n--- Auto-Generated Viral Script ---")
for s in SCENES:
    print(f"Text: {s['text']}")
    print(f"Search: {s['search_term']}\n")

FULL_SCRIPT = " ".join([s["text"] for s in SCENES])

# ==========================================
# 2. GENERATE HIGH-QUALITY STUDIO VOICE (EDGE-TTS)
# ==========================================
print("[2/6] Generating studio-quality neural voiceover with Edge-TTS...")

VOICE = "en-US-ChristopherNeural"

async def generate_voice():
    communicate = edge_tts.Communicate(FULL_SCRIPT, VOICE, rate="-5%")
    await communicate.save("voice.mp3")

asyncio.run(generate_voice())

# ==========================================
# 3. FETCH CINEMATIC PEXELS FOOTAGE
# ==========================================
print("[3/6] Fetching matching stock videos from Pexels...")
headers = {"Authorization": PEXELS_API_KEY}

for idx, scene in enumerate(SCENES):
    query = scene["search_term"]
    url = f"https://api.pexels.com/videos/search?query={requests.utils.quote(query)}&orientation=portrait&per_page=1"
    
    res = requests.get(url, headers=headers).json()
    if res.get("videos"):
        video_files = res["videos"][0]["video_files"]
        selected_video = next((v for v in video_files if v.get("width") == 1080), video_files[0])
        v_data = requests.get(selected_video["link"]).content
        with open(f"clip_{idx}.mp4", "wb") as f:
            f.write(v_data)
        print(f"Downloaded clip {idx+1}/6 for: '{query}'")
    else:
        print(f"No video found for '{query}'. Using fallback clip.")

# ==========================================
# 4. GENERATE VIRAL MULTI-WORD ASS CAPTIONS
# ==========================================
print("[4/6] Generating viral multi-word captions with Whisper...")
model = WhisperModel("base")
segments, _ = model.transcribe("voice.mp3", word_timestamps=True, language="en")

# ASS Style Header: Uses 'Impact' font, bold yellow text, thick black border, bottom aligned
ass_header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Impact,90,&H0000FFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,2,2,10,10,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

all_words = []
for segment in segments:
    for word in segment.words:
        w_text = word.word.strip().upper()
        if w_text in ["FAX", "FAX."]:
            w_text = "FACTS."
        all_words.append({
            "text": w_text,
            "start": word.start,
            "end": word.end
        })

# Group words into 3-word chunks per caption line
WORDS_PER_CHUNK = 3
chunks = [all_words[i:i + WORDS_PER_CHUNK] for i in range(0, len(all_words), WORDS_PER_CHUNK)]

ass_events = []
for chunk in chunks:
    chunk_start = chunk[0]["start"]
    chunk_end = chunk[-1]["end"]

    start_m, start_s = divmod(chunk_start, 60)
    start_h, start_m = divmod(start_m, 60)
    start_str = f"{int(start_h)}:{int(start_m):02d}:{start_s:05.2f}"

    end_m, end_s = divmod(chunk_end, 60)
    end_h, end_m = divmod(end_m, 60)
    end_str = f"{int(end_h)}:{int(end_m):02d}:{end_s:05.2f}"

    phrase_text = " ".join([w["text"] for w in chunk])
    event_line = f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{phrase_text}"
    ass_events.append(event_line)

with open("subtitles.ass", "w", encoding="utf-8") as f:
    f.write(ass_header + "\n".join(ass_events))

# ==========================================
# 5. RENDER FINAL VIDEO WITH FFMPEG
# ==========================================
print("[5/6] Rendering final video with FFmpeg...")

scene_count = len(SCENES)
filter_complex = ""

for i in range(scene_count):
    filter_complex += f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1[v{i}]; "

filter_complex += "".join([f"[v{i}]" for i in range(scene_count)])
filter_complex += f"concat=n={scene_count}:v=1:a=0[v_concat]; "
filter_complex += "[v_concat]ass=subtitles.ass[v_final]"

input_args = " ".join([f"-t 5 -i clip_{i}.mp4" for i in range(scene_count)])
output_name = f"final_{TOPIC.replace(' ', '_').lower()}.mp4"

cmd = f'ffmpeg -y {input_args} -i voice.mp3 -filter_complex "{filter_complex}" -map "[v_final]" -map {scene_count}:a -c:v libx264 -preset fast -crf 18 -c:a aac -b:a 192k -shortest "{output_name}"'

os.system(cmd)

print(f"\n[6/6] SUCCESS! Automated video saved as '{output_name}'.")