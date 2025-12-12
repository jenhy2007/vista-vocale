import streamlit as st
import requests
from io import BytesIO
import json
from gtts import gTTS
import base64
from PIL import Image

# --- CONFIGURATION ---
st.set_page_config(page_title="Vista Vocale", layout="wide")

try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("❌ API Key missing. Please check Secrets.")
    st.stop()

# --- STYLING ---
st.markdown("""
    <style>
    button[data-baseweb="tab"] { font-size: 20px !important; padding: 12px !important; }
    h1 { font-size: 2.2rem !important; }
    p, li { font-size: 1.1rem !important; }
    </style>
""", unsafe_allow_html=True)

# --- SYSTEM PROMPT ---
SYSTEM_PROMPT = """
You are an Italian teacher. Analyze the image and return a JSON object with this structure:
{
  "vocabulary": [{"italian_word": "", "italian_sentence": "", "english_translation": "", "object_name": ""}],
  "conversation": [{"speaker": "", "italian": "", "english": ""}],
  "story": [{"italian": "", "english": ""}]
}
Create 5 vocab words, a short dialogue, and a simple story using "Super 7 Verbs".
"""

# --- DIRECT API FUNCTION ---
def call_gemini_direct(image_bytes):
    # We use the REST API endpoint directly to avoid library version issues
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"
    
    # Convert image to Base64
    b64_image = base64.b64encode(image_bytes).decode('utf-8')
    
    payload = {
        "contents": [{
            "parts": [
                {"text": SYSTEM_PROMPT},
                {"inline_data": {
                    "mime_type": "image/jpeg",
                    "data": b64_image
                }}
            ]
        }],
        "generation_config": {
            "response_mime_type": "application/json"
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
        
        # Check for errors
        if response.status_code != 200:
            return None, f"Error {response.status_code}: {response.text}"
            
        # Parse result
        result = response.json()
        text_content = result['candidates'][0]['content']['parts'][0]['text']
        return json.loads(text_content), None
        
    except Exception as e:
        return None, str(e)

def get_audio_bytes(text, lang='it'):
    try:
        tts = gTTS(text=text, lang=lang)
        fp = BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp
    except: return None

# --- MAIN APP ---
st.title("🇮🇹 Vista Vocale")
st.caption("✨ Direct API Connection (v5.5)")

t_upload, t_gallery = st.tabs(["📷 Snap Photo", "🖼️ Gallery"])

final_image_bytes = None

with t_upload:
    uploaded_file = st.file_uploader("Take a photo:", type=["jpg", "png", "jpeg", "webp"])
    if uploaded_file:
        final_image_bytes = uploaded_file.getvalue()

with t_gallery:
    GALLERY = {
        "Select...": None,
        "☕ Espresso": "https://upload.wikimedia.org/wikipedia/commons/4/45/A_small_cup_of_coffee.JPG",
        "🛶 Venice": "https://upload.wikimedia.org/wikipedia/commons/d/d6/Gondola_Venice_2016.jpg"
    }
    choice = st.selectbox("Choose scene:", list(GALLERY.keys()))
    if choice and GALLERY[choice]:
        try:
            final_image_bytes = requests.get(GALLERY[choice]).content
        except: st.warning("Gallery Load Error")

st.markdown("---")

if final_image_bytes:
    # Display the image first
    st.image(final_image_bytes, use_container_width=True)
    
    with st.spinner("Analyzing..."):
        lesson_data, error = call_gemini_direct(final_image_bytes)
        
        if error:
            st.error(f"⚠️ {error}")
        elif lesson_data:
            t1, t2, t3 = st.tabs(["📖 VOCAB", "🗣️ CHAT", "📜 STORY"])
            
            with t1:
                if 'vocabulary' in lesson_data:
                    for item in lesson_data.get('vocabulary', []):
                        c1, c2 = st.columns([3, 1])
                        with c1:
                            st.markdown(f"**{item.get('italian_word')}**")
                            st.markdown(f"_{item.get('italian_sentence')}_")
                        with c2:
                            ab = get_audio_bytes(f"{item.get('italian_word')}... {item.get('italian_sentence')}")
                            if ab: st.audio(ab, format='audio/mp3')
                        st.divider()
                        
            with t2:
                if 'conversation' in lesson_data:
                    for turn in lesson_data.get('conversation', []):
                        c1, c2 = st.columns([3, 1])
                        with c1:
                            st.markdown(f"**{turn.get('speaker')}**: {turn.get('italian')}")
                        with c2:
                            ab = get_audio_bytes(turn.get('italian'))
                            if ab: st.audio(ab, format='audio/mp3')
                        st.divider()

            with t3:
                if 'story' in lesson_data:
                    for chunk in lesson_data.get('story', []):
                        c1, c2 = st.columns([3, 1])
                        with c1:
                            st.markdown(f"📖 {chunk.get('italian')}")
                        with c2:
                            ab = get_audio_bytes(chunk.get('italian'))
                            if ab: st.audio(ab, format='audio/mp3')
                        st.divider()
