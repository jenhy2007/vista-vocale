import streamlit as st
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import requests
from io import BytesIO
import json
from gtts import gTTS
import time
from PIL import Image
import warnings

# --- 1. CONFIGURATION & SETUP ---
warnings.filterwarnings("ignore")
st.set_page_config(page_title="Vista Vocale", layout="wide")

# Get API Key
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("❌ CRITICAL ERROR: API Key missing from Secrets!")
    st.stop()

# Configure Library
genai.configure(api_key=API_KEY)

# --- 2. SELF-HEALING MODEL SELECTOR ---
@st.cache_data
def find_working_model():
    """Asks Google which models are available and picks the best one."""
    try:
        # List all models
        all_models = list(genai.list_models())
        
        # Priority list (We prefer Flash, then Pro, then anything else)
        preferences = [
            "gemini-1.5-flash",
            "gemini-1.5-flash-001",
            "gemini-1.5-flash-latest",
            "gemini-1.5-pro",
            "gemini-pro-vision"
        ]
        
        # Check if any preferred model exists in the available list
        for pref in preferences:
            for m in all_models:
                if pref in m.name:
                    return m.name # Found a match!
        
        # If no match, just return the first one that supports vision
        for m in all_models:
            if 'vision' in m.supported_generation_methods:
                return m.name
                
        return "models/gemini-1.5-flash" # Fallback guess
    except Exception as e:
        return "models/gemini-1.5-flash"

# Find the model ONCE and save it
valid_model_name = find_working_model()

# --- 3. APP LOGIC ---

# Styling
st.markdown("""
    <style>
    button[data-baseweb="tab"] { font-size: 20px !important; padding: 12px !important; }
    h1 { font-size: 2.2rem !important; }
    p, li { font-size: 1.1rem !important; }
    </style>
""", unsafe_allow_html=True)

SYSTEM_INSTRUCTION = """
You are an expert TPRS Italian teacher. Create a 3-part lesson.
JSON Format:
{
  "vocabulary": [{"object_name": "", "italian_word": "", "italian_sentence": "", "english_translation": ""}],
  "conversation": [{"speaker": "", "italian": "", "english": ""}],
  "story": [{"italian": "", "english": ""}]
}
"""

# --- FUNCTIONS ---
def get_audio_bytes(text, lang='it'):
    try:
        tts = gTTS(text=text, lang=lang)
        fp = BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp
    except: return None

@st.cache_data(show_spinner=False)
def generate_lesson_from_bytes(image_bytes):
    # Use the model we found earlier
    model = genai.GenerativeModel(valid_model_name, system_instruction=SYSTEM_INSTRUCTION)
    
    try:
        image = Image.open(BytesIO(image_bytes))
    except:
        return None, "Invalid image format."

    for attempt in range(3):
        try:
            response = model.generate_content(
                [image, "Create a TPRS lesson."],
                generation_config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text), None
        except Exception as e:
            if "429" in str(e):
                time.sleep(2)
                continue
            return None, str(e)
            
    return None, "Server busy (Timeout)."

# --- MAIN LAYOUT ---
st.title("🇮🇹 Vista Vocale")
st.caption(f"✨ Connected to: {valid_model_name}") # DEBUG INFO

t_upload, t_gallery = st.tabs(["📷 Snap Photo", "🖼️ Gallery"])

final_image_bytes = None
start_analysis = False

with t_upload:
    uploaded_file = st.file_uploader("Take a photo:", type=["jpg", "png", "jpeg", "webp"])
    if uploaded_file:
        final_image_bytes = uploaded_file.getvalue()
        start_analysis = True

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

if start_analysis and final_image_bytes:
    with st.spinner("Analyzing..."):
        lesson_data, error_msg = generate_lesson_from_bytes(final_image_bytes)

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
                        with c2:
                            ab = get_audio_bytes(chunk['italian'])
                            if ab: st.audio(ab, format='audio/mp3')
                        st.markdown("")
