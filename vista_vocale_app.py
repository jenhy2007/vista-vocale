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
    /* Bigger Tabs */
    button[data-baseweb="tab"] { font-size: 18px !important; padding: 10px !important; }
    h1 { font-size: 2.2rem !important; }
    p, li { font-size: 1.1rem !important; }
    </style>
""", unsafe_allow_html=True)

# --- 1. AUTO-DISCOVERY (Stable Priority) ---
@st.cache_data
def get_best_model_name():
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
    try:
        response = requests.get(url)
        if response.status_code != 200:
            return None, f"List Error: {response.status_code}"
        
        data = response.json()
        models = data.get('models', [])
        
        # Priority: Stable 1.5 first to avoid limits
        priority_list = [
            "gemini-1.5-flash",
            "gemini-1.5-flash-latest",
            "gemini-1.5-flash-001",
            "gemini-1.5-pro"
        ]
        
        for priority in priority_list:
            for m in models:
                if priority in m['name']:
                    return m['name'], None

        for m in models:
            if "generateContent" in m.get('supportedGenerationMethods', []):
                return m['name'], None
                
        return "models/gemini-1.5-flash", None
        
    except Exception as e:
        return None, str(e)

valid_model_name, model_error = get_best_model_name()

# --- 2. DIRECT API CALL ---
def call_gemini_direct(image_bytes, model_name):
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={API_KEY}"
    b64_image = base64.b64encode(image_bytes).decode('utf-8')
    
    prompt_text = """
    You are an expert TPRS Italian teacher. Analyze the image and return a JSON object.
    Strictly follow this structure:
    {
      "vocabulary": [{"italian_word": "word", "italian_sentence": "sentence", "english_translation": "trans", "object_name": "name"}],
      "conversation": [{"speaker": "Name", "italian": "Italian text", "english": "English text"}],
      "story": [{"italian": "Story sentence", "english": "English translation"}]
    }
    """
    
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt_text},
                {"inline_data": {"mime_type": "image/jpeg", "data": b64_image}}
            ]
        }],
        "generation_config": {"response_mime_type": "application/json"}
    }
    
    try:
        response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
        if response.status_code != 200:
            return None, f"API Error ({response.status_code}): {response.text}"
            
        result = response.json()
        if 'candidates' in result and result['candidates']:
             text_content = result['candidates'][0]['content']['parts'][0]['text']
             text_content = text_content.replace('```json', '').replace('```', '')
             return json.loads(text_content), None
        else:
             return None, "AI returned no content."
        
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
    st.caption(f"✨ Connected to: `{valid_model_name}`")

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
    # --- LAYOUT CHANGE 1: SMALLER IMAGE ---
    # We use columns to center the image and limit width
    c1, c2, c3 = st.columns([1, 2, 1]) 
    with c2:
        st.image(final_image_bytes, use_container_width=True)
    
    if st.button("🇮🇹 Create Lesson", type="primary"):
        with st.spinner("Analyzing..."):
            lesson_data, error = call_gemini_direct(final_image_bytes, valid_model_name)
            
            if error:
                st.error(error)
            elif lesson_data:
                # --- LAYOUT CHANGE 2: 4TH TAB FOR TRANSLATIONS ---
                t1, t2, t3, t4 = st.tabs(["📖 VOCAB", "🗣️ CHAT", "📜 STORY", "🇺🇸 TRANSLATION"])
                
                # --- TAB 1: VOCAB (Italian Only) ---
                with t1:
                    vocab_list = lesson_data.get('vocabulary', [])
                    if isinstance(vocab_list, list):
                        for item in vocab_list:
                            if isinstance(item, dict):
                                c1, c2 = st.columns([3, 1])
                                with c1:
                                    st.markdown(f"**{item.get('italian_word', '')}**")
                                    st.markdown(f"_{item.get('italian_sentence', '')}_")
                                with c2:
                                    ab = get_audio_bytes(f"{item.get('italian_word', '')}... {item.get('italian_sentence', '')}")
                                    if ab: st.audio(ab, format='audio/mp3')
                                st.divider()
                            
                # --- TAB 2: CHAT (Italian Only) ---
                with t2:
                    chat_list = lesson_data.get('conversation', [])
                    if isinstance(chat_list, list):
                        for turn in chat_list:
                            c1, c2 = st.columns([3, 1])
                            with c1:
                                if isinstance(turn, dict):
                                    speaker = turn.get('speaker', 'Speaker')
                                    italian = turn.get('italian', '')
                                    st.markdown(f"**{speaker}**: {italian}")
                                else:
                                    st.markdown(str(turn))
                                    italian = str(turn)
                            with c2:
                                ab = get_audio_bytes(italian)
                                if ab: st.audio(ab, format='audio/mp3')
                            st.divider()

                # --- TAB 3: STORY (Italian Only) ---
                with t3:
                    story_list = lesson_data.get('story', [])
                    if isinstance(story_list, list):
                        for chunk in story_list:
                            c1, c2 = st.columns([3, 1])
                            with c1:
                                if isinstance(chunk, dict):
                                    text = chunk.get('italian', '')
                                    st.markdown(f"📖 {text}")
                                else:
                                    text = str(chunk)
                                    st.markdown(f"📖 {text}")
                            with c2:
                                ab = get_audio_bytes(text)
                                if ab: st.audio(ab, format='audio/mp3')
                            st.divider()

                # --- TAB 4: TRANSLATIONS (The Answer Key) ---
                with t4:
                    st.header("🇺🇸 English Translations")
                    
                    st.subheader("1. Vocabulary")
                    if isinstance(vocab_list, list):
                        for item in vocab_list:
                             if isinstance(item, dict):
                                 st.markdown(f"**{item.get('italian_word')}** = *{item.get('object_name')}*")
                                 st.caption(f"Sent: {item.get('english_translation')}")
                                 st.divider()

                    st.subheader("2. Conversation")
                    if isinstance(chat_list, list):
                        for turn in chat_list:
                             if isinstance(turn, dict):
                                 st.markdown(f"**{turn.get('speaker')}**: {turn.get('english')}")

                    st.markdown("---")
                    st.subheader("3. Story")
                    if isinstance(story_list, list):
                        for chunk in story_list:
                             if isinstance(chunk, dict):
                                 st.markdown(f"_{chunk.get('english')}_")
                                 st.markdown("")
