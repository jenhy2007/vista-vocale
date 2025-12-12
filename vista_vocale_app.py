import os
import streamlit as st
import google.generativeai as genai
import requests
from io import BytesIO
import json
from gtts import gTTS
from duckduckgo_search import DDGS
import warnings
import time
from PIL import Image

# --- 1. SILENCE WARNINGS ---
warnings.filterwarnings("ignore")

# --- CONFIGURATION ---
# We use the standard, stable model name
GEMINI_MODEL_NAME = "gemini-1.5-flash"

try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("❌ CRITICAL ERROR: API Key missing from Secrets!")
    st.stop()

# Configure the "Old Reliable" Library
genai.configure(api_key=API_KEY)

# --- STYLING ---
st.markdown("""
    <style>
    button[data-baseweb="tab"] { font-size: 20px !important; padding: 12px !important; }
    h1 { font-size: 2.2rem !important; }
    p, li { font-size: 1.1rem !important; }
    </style>
""", unsafe_allow_html=True)

# --- SYSTEM PROMPT ---
SYSTEM_INSTRUCTION = """
You are an expert TPRS Italian teacher. Create a 3-part lesson.
JSON Format:
{
  "vocabulary": [{"object_name": "", "italian_word": "", "italian_sentence": "", "english_translation": ""}],
  "conversation": [{"speaker": "", "italian": "", "english": ""}],
  "story": [{"italian": "", "english": ""}]
}
"""

st.set_page_config(page_title="Vista Vocale", layout="wide")

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Settings")
    teacher_mode = st.checkbox("🎓 Teacher Mode", value=False)

# --- FUNCTIONS ---
def get_audio_bytes(text, lang='it'):
    try:
        tts = gTTS(text=text, lang=lang)
        fp = BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp
    except: return None

# --- ANALYSIS FUNCTION (Using google-generativeai) ---
@st.cache_data(show_spinner=False)
def generate_lesson_from_bytes(image_bytes, mime_type):
    # Load the model using the stable library
    model = genai.GenerativeModel(GEMINI_MODEL_NAME, system_instruction=SYSTEM_INSTRUCTION)
    
    # Convert bytes to a PIL Image (The old library loves PIL Images)
    try:
        image = Image.open(BytesIO(image_bytes))
    except:
        return None, "Could not process image data."

    # Retry logic
    last_error = None
    for attempt in range(3):
        try:
            # The generation call
            response = model.generate_content(
                [image, "Create a TPRS lesson."],
                generation_config={"response_mime_type": "application/json"}
            )
            
            # Parse JSON
            return json.loads(response.text), None
            
        except Exception as e:
            last_error = e
            if "429" in str(e) or "quota" in str(e).lower():
                time.sleep(2)
                continue
            
    return None, str(last_error)

# --- MAIN LAYOUT ---
st.title("🇮🇹 Vista Vocale")

t_upload, t_gallery = st.tabs(["📷 Snap Photo", "🖼️ Gallery"])

final_image_bytes = None
final_mime_type = "image/jpeg"
start_analysis = False

# TAB 1: UPLOAD
with t_upload:
    uploaded_file = st.file_uploader("Take a photo:", type=["jpg", "png", "jpeg", "webp", "heic"])
    if uploaded_file:
        final_image_bytes = uploaded_file.getvalue()
        final_mime_type = uploaded_file.type
        start_analysis = True

# TAB 2: GALLERY
with t_gallery:
    IMAGE_GALLERY = {
        "Select...": None,
        "☕ Espresso": "https://upload.wikimedia.org/wikipedia/commons/4/45/A_small_cup_of_coffee.JPG",
        "🛶 Venice": "https://upload.wikimedia.org/wikipedia/commons/d/d6/Gondola_Venice_2016.jpg"
    }
    selected_name = st.selectbox("Choose scene:", list(IMAGE_GALLERY.keys()))
    if selected_name and IMAGE_GALLERY[selected_name]:
        try:
            resp = requests.get(IMAGE_GALLERY[selected_name], headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
            final_image_bytes = resp.content
            start_analysis = True
        except: st.warning("Gallery error.")

st.markdown("---")

# --- RESULT ---
if start_analysis and final_image_bytes:
    with st.spinner("Analyzing with Stable 1.5 Flash..."):
        lesson_data, error_msg = generate_lesson_from_bytes(final_image_bytes, final_mime_type)

        if error_msg:
            st.error(f"⚠️ ERROR: {error_msg}")
        
        elif lesson_data:
            st.image(final_image_bytes, use_container_width=True)
            
            t1, t2, t3 = st.tabs(["📖 VOCAB", "🗣️ CHAT", "📜 STORY"])
            
            with t1:
                if 'vocabulary' in lesson_data:
                    for item in lesson_data['vocabulary']:
                        c1, c2 = st.columns([2, 1])
                        with c1:
                            st.markdown(f"**{item['italian_word']}**")
                            st.markdown(f"_{item['italian_sentence']}_")
                            if not teacher_mode: st.caption(item['english_translation'])
                        with c2:
                            ab = get_audio_bytes(f"{item['italian_word']}... {item['italian_sentence']}")
                            if ab: st.audio(ab, format='audio/mp3')
                        st.divider()

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
