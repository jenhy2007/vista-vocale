import streamlit as st
import requests
import json
import base64
from io import BytesIO
from gtts import gTTS

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
    button[data-baseweb="tab"] { font-size: 16px !important; padding: 8px 12px !important; flex: 1 1 auto; }
    h1 { font-size: 2.2rem !important; }
    div[data-baseweb="select"] { text-align: center; }
    .pinyin { color: #888; font-size: 0.9rem; font-style: italic; margin-bottom: 5px; }
    </style>
""", unsafe_allow_html=True)

# --- LANGUAGE SETTINGS ---
LANG_CONFIG = {
    "🇮🇹 Italian": { "code": "it", "name": "Italian", "super7": "essere, avere, volere, andare, piacere, c'è, potere" },
    "🇫🇷 French": { "code": "fr", "name": "French", "super7": "être, avoir, vouloir, aller, aimer, il y a, pouvoir" },
    "🇨🇳 Chinese": { "code": "zh-CN", "name": "Mandarin Chinese", "super7": "是 (shì), 有 (yǒu), 要 (yào), 去 (qù), 喜欢 (xǐhuān), 在 (zài), 能 (néng)" }
}

# --- 1. THE TRUTH SERUM (List EXACTLY what you have) ---
@st.cache_data
def get_my_models():
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
    try:
        response = requests.get(url)
        if response.status_code != 200:
            return []
        data = response.json()
        # Filter for models that can generate content
        valid_models = [
            m['name'] for m in data.get('models', []) 
            if "generateContent" in m.get('supportedGenerationMethods', [])
        ]
        return valid_models
    except:
        return []

# --- 2. SIDEBAR SELECTOR ---
with st.sidebar:
    st.header("🔧 Engine Room")
    my_models = get_my_models()
    
    if not my_models:
        st.error("⚠️ No models found! Your API Key might be invalid or has no access.")
        active_model = "models/gemini-1.5-flash" # Fallback hope
    else:
        st.success(f"Found {len(my_models)} available engines.")
        # Default to the first one, but let user pick
        active_model = st.selectbox("Select Model:", my_models, index=0)
        st.caption(f"Using: `{active_model}`")

# --- 3. GALLERY DOWNLOADER ---
@st.cache_data(show_spinner=False)
def load_gallery_image(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        return response.content
    except Exception as e: return None

# --- 4. HELPER: TEXT FILE ---
def create_lesson_file(data, lang_name):
    text = f"🌍 VISTA VOCALE - {lang_name.upper()} LESSON\n==========================================\n\n"
    text += "1. VOCABULARY\n-------------\n"
    for item in data.get('vocabulary', []):
        if isinstance(item, dict):
            word = item.get('target_word', '')
            pron = item.get('pronunciation', '')
            text += f"* {word} ({item.get('object_name', '')})\n"
            if pron: text += f"  [{pron}]\n"
            text += f"  - {item.get('target_sentence', '')}\n  - {item.get('english_translation', '')}\n\n"

    text += "2. CONVERSATION\n---------------\n"
    for turn in data.get('conversation', []):
        if isinstance(turn, dict):
            text += f"{turn.get('speaker')}: {turn.get('target_text')}\n"
            if turn.get('pronunciation'): text += f"      [{turn.get('pronunciation')}]\n"
            text += f"      ({turn.get('english')})\n"
    
    text += "\n3. STORY\n--------\n"
    for chunk in data.get('story', []):
        if isinstance(chunk, dict):
            text += f"{chunk.get('target_text')}\n"
            if chunk.get('pronunciation'): text += f"[{chunk.get('pronunciation')}]\n"
            if chunk.get('english'): text += f"({chunk.get('english')})\n\n"
    return text

# --- 5. DIRECT API CALL ---
def call_gemini_direct(image_bytes, model_name, lang_config):
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={API_KEY}"
    b64_image = base64.b64encode(image_bytes).decode('utf-8')
    
    prompt_text = f"""
    You are an expert TPRS {lang_config['name']} teacher.
    Analyze the image and create a lesson strictly following these rules:
    1. Select 5 High-Frequency Vocabulary words visible in the image.
    2. Create a simple Conversation that uses ONLY these words and "Super 7" verbs: {lang_config['super7']}.
    3. Create a Story (5-6 sentences) that RECYCLES the vocab words.
    4. Keep level A1 (Beginner).

    CRITICAL:
    If CHINESE: fill "pronunciation" with Pinyin.
    If ITALIAN/FRENCH: leave "pronunciation" empty ("").
    
    Return JSON:
    {{
      "vocabulary": [{{"target_word": "...", "pronunciation": "...", "target_sentence": "...", "english_translation": "...", "object_name": "..."}}],
      "conversation": [{{"speaker": "...", "target_text": "...", "pronunciation": "...", "english": "..."}}],
      "story": [{{"target_text": "...", "pronunciation": "...", "english": "..."}}]
    }}
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt_text}, {"inline_data": {"mime_type": "image/jpeg", "data": b64_image}}]}],
        "generation_config": {"response_mime_type": "application/json"}
    }
    
    try:
        response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
        if response.status_code != 200: return None, f"API Error ({response.status_code}): {response.text}"
        result = response.json()
        if 'candidates' in result and result['candidates']:
             text_content = result['candidates'][0]['content']['parts'][0]['text']
             return json.loads(text_content.replace('```json', '').replace('```', '')), None
        else: return None, "AI returned no content."
    except Exception as e: return None, str(e)

def get_audio_bytes(text, lang_code):
    try:
        fp = BytesIO()
        gTTS(text=text, lang=lang_code).write_to_fp(fp)
        fp.seek(0)
        return fp
    except: return None

# --- MAIN APP LAYOUT ---
st.title("🌍 Vista Vocale")

t_upload, t_gallery = st.tabs(["📷 Snap Photo", "🖼️ Gallery"])
final_image_bytes = None

with t_upload:
    uploaded_file = st.file_uploader("Take a photo:", type=["jpg", "png", "jpeg", "webp"])
    if uploaded_file: final_image_bytes = uploaded_file.getvalue()

with t_gallery:
    GALLERY = {
        "Select...": None,
        "☕ Espresso": "https://upload.wikimedia.org/wikipedia/commons/4/45/A_small_cup_of_coffee.JPG",
        "🛶 Venice": "https://upload.wikimedia.org/wikipedia/commons/d/d6/Gondola_Venice_2016.jpg",
        "🥐 Croissant (French)": "https://upload.wikimedia.org/wikipedia/commons/2/28/2018_01_Croissant_IMG_0685.JPG",
        "🥟 Dumplings (Chinese)": "https://upload.wikimedia.org/wikipedia/commons/9/93/Jiaozi_at_Wangfujing.JPG"
    }
    choice = st.selectbox("Choose scene:", list(GALLERY.keys()))
    if choice and GALLERY[choice]:
        loaded_bytes = load_gallery_image(GALLERY[choice])
        if loaded_bytes: final_image_bytes = loaded_bytes

st.markdown("---")

if final_image_bytes:
    c1, c2, c3 = st.columns([1, 2, 1]) 
    with c2:
        st.image(final_image_bytes, use_container_width=True)
        selected_lang_key = st.selectbox("Select Target Language:", list(LANG_CONFIG.keys()), index=0)
        current_lang = LANG_CONFIG[selected_lang_key]
        
        if st.button(f"Create {current_lang['name']} Lesson", type="primary", use_container_width=True):
            with st.spinner("Analyzing..."):
                lesson_data, error = call_gemini_direct(final_image_bytes, active_model, current_lang)
                if error:
                    st.error(error) 
                    with st.expander("Raw Error"): st.code(error)
                elif lesson_data:
                    st.session_state['lesson_data'] = lesson_data
                    st.session_state['current_lang'] = current_lang

    if 'lesson_data' in st.session_state:
        data = st.session_state['lesson_data']
        lang = st.session_state['current_lang']
        st.markdown("---")
        t1, t2, t3, t4, t5 = st.tabs(["📖 Vocab", "🗣️ Chat", "📜 Story", "🇺🇸 Key", "💾 Save"])
        
        with t1:
            for item in data.get('vocabulary', []):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"**{item.get('target_word', '')}**")
                    if item.get('pronunciation'): st.markdown(f"<div class='pinyin'>{item.get('pronunciation')}</div>", unsafe_allow_html=True)
                    st.markdown(f"_{item.get('target_sentence', '')}_")
                with c2:
                    ab = get_audio_bytes(f"{item.get('target_word', '')}... {item.get('target_sentence', '')}", lang['code'])
                    if ab: st.audio(ab, format='audio/mp3')
                st.divider()

        with t2:
            for turn in data.get('conversation', []):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"**{turn.get('speaker')}**: {turn.get('target_text')}")
                    if turn.get('pronunciation'): st.markdown(f"<div class='pinyin'>{turn.get('pronunciation')}</div>", unsafe_allow_html=True)
                with c2:
                    ab = get_audio_bytes(turn.get('target_text'), lang['code'])
                    if ab: st.audio(ab, format='audio/mp3')
                st.divider()

        with t3:
            for chunk in data.get('story', []):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"📖 {chunk.get('target_text')}")
                    if chunk.get('pronunciation'): st.markdown(f"<div class='pinyin'>{chunk.get('pronunciation')}</div>", unsafe_allow_html=True)
                with c2:
                    ab = get_audio_bytes(chunk.get('target_text'), lang['code'])
                    if ab: st.audio(ab, format='audio/mp3')
                st.divider()

        with t4:
            st.header("🇺🇸 Answer Key")
            for item in data.get('vocabulary', []):
                st.markdown(f"**{item.get('target_word')}** = *{item.get('object_name')}*")
                st.caption(f"Sent: {item.get('english_translation')}")
                st.divider()
            st.subheader("Conversation")
            for turn in data.get('conversation', []):
                st.markdown(f"**{turn.get('speaker')}**: {turn.get('english')}")
            st.subheader("Story")
            for chunk in data.get('story', []):
                st.markdown(f"_{chunk.get('english')}_")

        with t5:
            st.header("💾 Download")
            lesson_text = create_lesson_file(data, lang['name'])
            st.download_button(label=f"📥 Download (.txt)", data=lesson_text, file_name=f"{lang['name']}_Lesson.txt", mime="text/plain")
