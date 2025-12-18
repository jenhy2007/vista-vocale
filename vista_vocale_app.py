import streamlit as st
import requests
import json
import base64
import time
from io import BytesIO
from datetime import datetime
from gtts import gTTS
import google.generativeai as genai
from streamlit_mic_recorder import mic_recorder

# ==========================================
# 1. GLOBAL CONFIG & STYLING
# ==========================================
st.set_page_config(page_title="Vista Vocale Super App", layout="wide")

# API KEY SETUP
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=API_KEY)
except:
    st.error("❌ API Key missing. Please check Secrets.")
    st.stop()

# GLOBAL CSS
st.markdown("""
<style>
    /* Global Font Size */
    html, body, [class*="css"] { font-size: 18px !important; }
    
    /* Big Menu Buttons */
    div.stButton > button {
        width: 100%;
        height: 80px;
        font-size: 20px;
        font-weight: bold;
        border-radius: 15px;
        margin-bottom: 10px;
        background-color: #f0f2f6;
    }
    div.stButton > button:hover {
        background-color: #e3f2fd;
        border: 2px solid #1565c0;
    }

    /* Vista Vocale Styles */
    .pinyin { color: #555; font-size: 1.1rem; font-style: italic; margin-bottom: 5px; font-family: "Courier New", monospace; }
    .vocab-word { font-size: 1.5rem; font-weight: bold; color: #1E88E5; }
    
    /* Parla Chat Styles */
    .chat-box { padding: 15px; border-radius: 15px; margin-bottom: 10px; }
    .user-msg { background-color: #e3f2fd; text-align: right; color: #1565c0; }
    .ai-msg { background-color: #f1f8e9; text-align: left; color: #2e7d32; }
    .success-box { padding: 10px; background-color: #e8f5e9; border-radius: 10px; color: #1b5e20; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. SHARED HELPER FUNCTIONS
# ==========================================
def get_prioritized_models():
    # Helper to find the best Gemini model available
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
    try:
        response = requests.get(url)
        if response.status_code != 200: return []
        data = response.json()
        valid_models = []
        for m in data.get('models', []):
            name = m['name']
            if "generateContent" not in m.get('supportedGenerationMethods', []): continue
            if "tts" in name.lower() or "embedding" in name.lower(): continue
            valid_models.append(name)
        
        def sort_key(name):
            if "gemini-3" in name: return 0
            if "gemini-2.5-flash" in name and "lite" not in name: return 1
            if "gemini-2.5" in name and "lite" not in name: return 2
            return 50 
        valid_models.sort(key=sort_key)
        return valid_models
    except: return []

def get_audio_bytes(text, lang_code):
    try:
        fp = BytesIO()
        gTTS(text=text, lang=lang_code).write_to_fp(fp)
        fp.seek(0)
        return fp
    except: return None

def get_any(d, keys, default=""):
    """Helper to safely find values using multiple possible key names"""
    for k in keys:
        if k in d and d[k]: return d[k]
        if k.lower() in d and d[k.lower()]: return d[k.lower()]
    return default

def create_lesson_file(data, lang_name):
    """Generates the text file for the Save tab"""
    text = f"🌍 VISTA VOCALE - {lang_name.upper()} LESSON\n==========================================\n\n"
    
    # 1. Vocab
    text += "1. VOCABULARY\n-------------\n"
    for item in data.get('vocabulary', []):
        if isinstance(item, dict):
            word = get_any(item, ['target_word', 'word', 'term'])
            sent = get_any(item, ['target_sentence', 'sentence', 'example'])
            trans = get_any(item, ['english_translation', 'translation', 'meaning'])
            text += f"* {word}\n  SENTENCE: {sent}\n  MEANING: {trans}\n\n"
            
    # 2. Conversation
    text += "2. CONVERSATION\n---------------\n"
    for turn in data.get('conversation', []):
        if isinstance(turn, dict):
            speaker = get_any(turn, ['speaker', 'role'])
            content = get_any(turn, ['target_text', 'text', 'content', 'message', 'sentence'])
            text += f"{speaker}: {content}\n"
            
    # 3. Story
    text += "\n3. STORY\n--------\n"
    for chunk in data.get('story', []):
        if isinstance(chunk, dict):
             text += get_any(chunk, ['target_text', 'text', 'content', 'sentence']) + "\n"
        elif isinstance(chunk, str):
             text += chunk + "\n"
             
    return text

# ==========================================
# 3. APP A: VISTA VOCALE (Photo Lesson)
# ==========================================
def run_photo_app():
    # Navigation Header
    c_head1, c_head2 = st.columns([1, 5])
    with c_head1:
        if st.button("⬅️ Home"):
            st.session_state.current_page = "home"
            st.rerun()
    with c_head2:
        st.title("📷 Photo Lesson")

    LANG_CONFIG = {
        "🇮🇹 Italian": { "code": "it", "name": "Italian", "super7": "essere, avere, volere, andare, piacere, c'è, potere" },
        "🇫🇷 French": { "code": "fr", "name": "French", "super7": "être, avoir, vouloir, aller, aimer, il y a, pouvoir" },
        "🇨🇳 Chinese": { "code": "zh-CN", "name": "Mandarin Chinese", "super7": "是 (shì), 有 (yǒu), 要 (yào), 去 (qù), 喜欢 (xǐhuān), 在 (zài), 能 (néng)" }
    }
    
    my_models = get_prioritized_models()

    t_upload, t_gallery = st.tabs(["📷 Snap/Upload", "🖼️ Gallery"])
    final_image_bytes = None

    with t_upload:
        st.info("Tip: Take photo first, then upload!")
        uploaded_file = st.file_uploader("Upload Image:", type=["jpg", "png", "jpeg", "webp"])
        if uploaded_file: final_image_bytes = uploaded_file.getvalue()

    with t_gallery:
        GALLERY = {
            "Select...": None,
            "☕ Espresso": "https://upload.wikimedia.org/wikipedia/commons/4/45/A_small_cup_of_coffee.JPG",
            "🛶 Venice": "https://upload.wikimedia.org/wikipedia/commons/d/d6/Gondola_Venice_2016.jpg",
            "🥐 Croissant": "https://upload.wikimedia.org/wikipedia/commons/2/28/2018_01_Croissant_IMG_0685.JPG",
            "🥟 Dumplings": "https://upload.wikimedia.org/wikipedia/commons/9/93/Jiaozi_at_Wangfujing.JPG"
        }
        choice = st.selectbox("Choose scene:", list(GALLERY.keys()))
        if choice and GALLERY[choice]:
            try:
                headers = {'User-Agent': 'Mozilla/5.0'}
                resp = requests.get(GALLERY[choice], headers=headers, timeout=5)
                if resp.status_code == 200: final_image_bytes = resp.content
            except: pass

    st.markdown("---")

    if final_image_bytes:
        c1, c2, c3 = st.columns([1, 2, 1]) 
        with c2:
            st.image(final_image_bytes, use_container_width=True)
            selected_lang_key = st.selectbox("Target Language:", list(LANG_CONFIG.keys()), index=0)
            current_lang = LANG_CONFIG[selected_lang_key]
            
            if st.button(f"Generate {current_lang['name']} Lesson", type="primary"):
                if not my_models:
                     st.error("No models found.")
                else:
                    with st.spinner("Analyzing image..."):
                        # --- SAFE PROMPT CONSTRUCTION (Fixes SyntaxError) ---
                        model_name = my_models[0]
                        url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={API_KEY}"
                        b64_image = base64.b64encode(final_image_bytes).decode('utf-8')
                        
                        # Note: We use a standard string here (no 'f') to avoid bracket conflicts
                        base_prompt = """
                        You are an expert TPRS LANGUAGE_TARGET teacher.
                        Analyze the image and create a lesson.
                        1. Select 5 High-Frequency Vocabulary words visible in the image.
                        2. Create a simple Conversation that uses ONLY these words and "Super 7" verbs: SUPER_7_VERBS.
                        3. Create a Story (5-6 sentences) that RECYCLES the vocab words.
                        4. Keep level A1 (Beginner).
                        
                        CRITICAL FORMATTING:
                        - If CHINESE: You MUST provide Pinyin for the 'target_word' AND the 'target_sentence'.
                        - If ITALIAN/FRENCH: Leave pronunciation empty.
                        
                        Return STRICT JSON with these exact keys:
                        {
                          "vocabulary": [
                            {
                                "target_word": "...", 
                                "pronunciation": "...", 
                                "target_sentence": "...", 
                                "english_translation": "..."
                            }
                          ],
                          "conversation": [{"speaker": "...", "target_text": "...", "pronunciation": "..."}],
                          "story": [{"target_text": "...", "pronunciation": "..."}]
