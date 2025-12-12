import os
import streamlit as st
from google import genai
from google.genai import types
import requests
from io import BytesIO
import json
from gtts import gTTS
from duckduckgo_search import DDGS
import warnings
import time

# --- 1. SILENCE WARNINGS ---
warnings.filterwarnings("ignore")

# --- CONFIGURATION ---
API_KEY = os.environ.get("GEMINI_API_KEY")
# Using the stable model for reliability
GEMINI_MODEL = "gemini-1.5-flash"

# --- 2. CUSTOM STYLING (BIG TEXT FOR MOBILE) ---
st.markdown("""
    <style>
    /* Bigger Tabs */
    button[data-baseweb="tab"] {
        font-size: 20px !important;
        font-weight: bold !important;
        padding: 12px !important;
    }
    /* Bigger Headers */
    h1 { font-size: 2.5rem !important; }
    h2 { font-size: 2.0rem !important; color: #008000; } 
    h3 { font-size: 1.5rem !important; }
    /* Bigger Body Text */
    p, li, .stMarkdown { font-size: 1.2rem !important; }
    /* Hide the 'Deploy' button hamburger menu on mobile if possible to clean UI */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- SYSTEM PROMPT ---
SYSTEM_INSTRUCTION = """
You are an expert TPRS Italian teacher. Create a 3-part lesson based on the image.

1. "vocabulary": 5 key nouns from the image.
2. "conversation": A short Q&A dialogue (Who/What/Where) using those nouns.
3. "story": A repetitive story using the "Super 7 Verbs" (Essere, Avere, Esserci, Piacere, Andare, Volere) and the vocabulary.

JSON STRUCTURE:
{
  "vocabulary": [
    {
      "object_name": "English name",
      "italian_word": "Italian word (with article)",
      "italian_sentence": "Simple sentence",
      "english_translation": "English translation"
    }
  ],
  "conversation": [
    {"speaker": "Name", "italian": "...", "english": "..."}
  ],
  "story": [
    {"italian": "...", "english": "..."}
  ]
}
"""

st.set_page_config(page_title="Vista Vocale", layout="wide")

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Settings")
    teacher_mode = st.checkbox("🎓 Teacher Mode", value=False, help="Hide English text.")

# --- FUNCTIONS ---

def get_audio_bytes(text, lang='it'):
    try:
        tts = gTTS(text=text, lang=lang)
        fp = BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp
    except: return None

# --- CORE ANALYSIS FUNCTION (Now accepts RAW BYTES for stability) ---
@st.cache_data(show_spinner=False)
def generate_lesson_from_bytes(image_bytes, mime_type):
    if not API_KEY: return None

    client = genai.Client(api_key=API_KEY)
    content = [types.Part.from_bytes(data=image_bytes, mime_type=mime_type), "Create a TPRS lesson."]
    
    # Retry logic for stability
    for attempt in range(3):
        try:
            resp = client.models.generate_content(
                model=GEMINI_MODEL, 
                contents=content,
                config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION)
            )
            return json.loads(resp.text.replace('```json', '').replace('```', '').strip())
        except Exception as e:
            if "503" in str(e) or "Overloaded" in str(e):
                time.sleep(2)
                continue
            return None
    return None

# --- MAIN LAYOUT ---
st.title("🇮🇹 Vista Vocale")

# TABS: Upload is now #1
t_upload, t_gallery = st.tabs(["📷 Snap Photo", "🖼️ Gallery"])

final_image_bytes = None
final_mime_type = "image/jpeg"
start_analysis = False

# --- TAB 1: SNAP / UPLOAD ---
with t_upload:
    uploaded_file = st.file_uploader("Take a photo or upload:", type=["jpg", "png", "jpeg", "webp"])
    if uploaded_file:
        # Convert to bytes immediately to keep it stable
        final_image_bytes = uploaded_file.getvalue()
        final_mime_type = uploaded_file.type
        start_analysis = True

# --- TAB 2: GALLERY (Backup) ---
with t_gallery:
    IMAGE_GALLERY = {
        "Select...": None,
        "☕ Espresso": "https://upload.wikimedia.org/wikipedia/commons/4/45/A_small_cup_of_coffee.JPG",
        "🛶 Venice": "https://upload.wikimedia.org/wikipedia/commons/d/d6/Gondola_Venice_2016.jpg",
        "🏛️ Colosseum": "https://upload.wikimedia.org/wikipedia/commons/d/de/Colosseo_2020.jpg"
    }
    selected_name = st.selectbox("Or choose a scene:", list(IMAGE_GALLERY.keys()))
    if selected_name and IMAGE_GALLERY[selected_name]:
        try:
            # Download the gallery image to bytes so the logic is the same
            resp = requests.get(IMAGE_GALLERY[selected_name], headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
            if resp.status_code == 200:
                final_image_bytes = resp.content
                final_mime_type = "image/jpeg"
                start_analysis = True
        except:
            st.warning("Could not load gallery image.")

st.markdown("---")

# --- LESSON DISPLAY ---
if start_analysis and final_image_bytes:
    with st.spinner("🇮🇹 Bella sta guardando la tua foto... (Analyzing)"):
        # Send the BYTES to the cached function
        lesson_data = generate_lesson_from_bytes(final_image_bytes, final_mime_type)

        if lesson_data:
            # Mobile-friendly layout: Image on top, tabs below
            st.image(final_image_bytes, use_container_width=True)
            
            t1, t2, t3 = st.tabs(["📖 VOCAB", "🗣️ CHAT", "📜 STORY"])
            
            # 1. VOCABULARY
            with t1:
                if 'vocabulary' in lesson_data:
                    for item in lesson_data['vocabulary']:
                        c1, c2 = st.columns([2, 1])
                        with c1:
                            st.markdown(f"**{item['italian_word']}**")
                            st.markdown(f"_{item['italian_sentence']}_")
                            if not teacher_mode: 
                                st.caption(f"{item['object_name']} • {item['english_translation']}")
                        with c2:
                            ab = get_audio_bytes(f"{item['italian_word']}... {item['italian_sentence']}")
                            if ab: st.audio(ab, format='audio/mp3')
                        st.divider()

            # 2. CONVERSATION
            with t2:
                if 'conversation' in lesson_data:
                    for turn in lesson_data['conversation']:
                        c1, c2 = st.columns([3, 1])
                        with c1:
                            st.markdown(f"**{turn['speaker']}:** {turn['italian']}")
                            if not teacher_mode: st.caption(f"({turn['english']})")
                        with c2:
                            ab = get_audio_bytes(turn['italian'])
                            if ab: st.audio(ab, format='audio/mp3')
                        st.divider()

            # 3. STORY
            with t3:
                if 'story' in lesson_data:
                    for chunk in lesson_data['story']:
                        c1, c2 = st.columns([3, 1])
                        with c1:
                            st.markdown(f"📖 **{chunk['italian']}**")
                            if not teacher_mode: st.caption(chunk['english'])
                        with c2:
                            ab = get_audio_bytes(chunk['italian'])
                            if ab: st.audio(ab, format='audio/mp3')
                        st.markdown("")
        else:
            st.error("Could not analyze image. Try a clearer photo!")
