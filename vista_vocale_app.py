import streamlit as st
import requests
import json
import base64
from io import BytesIO
from gtts import gTTS
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

# --- 1. AUTO-DISCOVERY FUNCTION ---
@st.cache_data
def get_best_model_name():
    """Asks Google: 'Which models do you have?' and picks the best Vision model."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
    try:
        response = requests.get(url)
        if response.status_code != 200:
            return None, f"List Error: {response.status_code}"
        
        data = response.json()
        models = data.get('models', [])
        
        # We look for specific trusted models in this order
        priority_list = [
            "gemini-1.5-flash",
            "gemini-1.5-flash-latest",
            "gemini-1.5-flash-001",
            "gemini-1.5-pro",
            "gemini-pro-vision"
        ]
        
        # 1. Try to find a match from our priority list
        for priority in priority_list:
            for m in models:
                if priority in m['name']:
                    # Return the full name (e.g., "models/gemini-1.5-flash-001")
                    return m['name'], None

        # 2. Fallback: Find ANY model that supports 'generateContent'
        for m in models:
            if "generateContent" in m.get('supportedGenerationMethods', []):
                return m['name'], None
                
        return "models/gemini-1.5-flash", None # Blind guess if all else fails
        
    except Exception as e:
        return None, str(e)

# --- FIND THE MODEL AT STARTUP ---
valid_model_name, model_error = get_best_model_name()

# --- 2. DIRECT API CALL ---
def call_gemini_direct(image_bytes, model_name):
    # Use the discovered model name directly
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={API_KEY}"
    
    b64_image = base64.b64encode(image_bytes).decode('utf-8')
    
    payload = {
        "contents": [{
            "parts": [
                {"text": "You are an Italian teacher. Create a JSON lesson with: vocabulary (5 words), conversation, story."},
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
        if response.status_code != 200:
            return None, f"API Error ({response.status_code}): {response.text}"
            
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

# --- MAIN APP LAYOUT ---
st.title("🇮🇹 Vista Vocale")

if model_error:
    st.error(f"⚠️ Could not find models: {model_error}")
else:
    st.caption(f"✨ Connected to: `{valid_model_name}`") # Shows exactly what model we found!

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
    st.image(final_image_bytes, use_container_width=True)
    
    if st.button("🇮🇹 Create Lesson"):
        with st.spinner("Analyzing..."):
            lesson_data, error = call_gemini_direct(final_image_bytes, valid_model_name)
            
            if error:
                st.error(error)
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
