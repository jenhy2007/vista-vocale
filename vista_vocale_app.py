import streamlit as st
import requests
import json
import base64
import time
from io import BytesIO
from gtts import gTTS

# --- CONFIGURATION ---
st.set_page_config(page_title="Vista Vocale", layout="wide")

try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("❌ API Key missing. Please check Secrets.")
    st.stop()

# --- STYLING (BIG TEXT EDITION) ---
st.markdown("""
    <style>
    /* Increase base font size for the whole app */
    html, body, [class*="css"] {
        font-size: 20px !important; 
    }
    
    /* Make the tabs bigger */
    button[data-baseweb="tab"] { 
        font-size: 22px !important; 
        padding: 10px 20px !important; 
        flex: 1 1 auto; 
    }
    
    /* Make headers pop */
    h1 { font-size: 3rem !important; color: #FF4B4B; }
    h2 { font-size: 2.2rem !important; }
    h3 { font-size: 1.8rem !important; }
    
    /* Center select boxes */
    div[data-baseweb="select"] { text-align: center; }
    
    /* Pinyin styling - distinct color */
    .pinyin { 
        color: #555; 
        font-size: 1.1rem; 
        font-style: italic; 
        margin-bottom: 5px; 
        font-family: "Courier New", monospace;
    }
    
    /* Target word emphasis */
    .vocab-word {
        font-size: 1.5rem;
        font-weight: bold;
        color: #1E88E5;
    }
    </style>
""", unsafe_allow_html=True)

# --- LANGUAGE SETTINGS ---
LANG_CONFIG = {
    "🇮🇹 Italian": { "code": "it", "name": "Italian", "super7": "essere, avere, volere, andare, piacere, c'è, potere" },
    "🇫🇷 French": { "code": "fr", "name": "French", "super7": "être, avoir, vouloir, aller, aimer, il y a, pouvoir" },
    "🇨🇳 Chinese": { "code": "zh-CN", "name": "Mandarin Chinese", "super7": "是 (shì), 有 (yǒu), 要 (yào), 去 (qù), 喜欢 (xǐhuān), 在 (zài), 能 (néng)" }
}

# --- 1. INTELLIGENT MODEL MANAGER ---
@st.cache_data
def get_prioritized_models():
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
    try:
        response = requests.get(url)
        if response.status_code != 200: return []
        data = response.json()
        
        valid_models = []
        for m in data.get('models', []):
            name = m['name']
            methods = m.get('supportedGenerationMethods', [])
            if "generateContent" not in methods: continue
            if "tts" in name.lower(): continue
            if "embedding" in name.lower(): continue
            valid_models.append(name)
        
        # Sort: Gemini 3 -> 2.5 Full -> 2.5 Lite
        def sort_key(name):
            if "gemini-3" in name: return 0
            if "gemini-2.5-flash" in name and "lite" not in name: return 1
            if "gemini-2.5" in name and "lite" not in name: return 2
            if "lite" in name: return 99
            return 50 
            
        valid_models.sort(key=sort_key)
        return valid_models
    except:
        return []

# --- 2. THE AUTO-PILOT ENGINE ---
def generate_lesson_with_fallback(image_bytes, lang_config, models_list):
    for attempt, model_name in enumerate(models_list[:4]): 
        status_placeholder = st.empty()
        status_placeholder.info(f"Attempt {attempt+1}: Connecting to `{model_name}`...")
        
        url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={API_KEY}"
        b64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        # UPDATED PROMPT: Explicitly asking for sentence pronunciation
        prompt_text = f"""
        You are an expert TPRS {lang_config['name']} teacher.
        Analyze the image and create a lesson strictly following these rules:
        1. Select 5 High-Frequency Vocabulary words visible in the image.
        2. Create a simple Conversation that uses ONLY these words and "Super 7" verbs: {lang_config['super7']}.
        3. Create a Story (5-6 sentences) that RECYCLES the vocab words.
        4. Keep level A1 (Beginner).
        
        CRITICAL FORMATTING:
        - If CHINESE: You MUST provide Pinyin for the 'target_word' AND the 'target_sentence'.
        - If ITALIAN/FRENCH: Leave pronunciation empty.
        
        Return STRICT JSON with these exact keys:
        {{
          "vocabulary": [
            {{
                "target_word": "...", 
                "pronunciation": "...", 
                "target_sentence": "...", 
                "sentence_pronunciation": "...", 
                "english_translation": "...", 
                "object_name": "..."
            }}
          ],
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
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and result['candidates']:
                    text_content = result['candidates'][0]['content']['parts'][0]['text']
                    status_placeholder.success(f"✅ Success! Generated by `{model_name}`")
                    time.sleep(1)
                    status_placeholder.empty()
                    try:
                        clean_text = text_content.replace('```json', '').replace('```', '')
                        parsed_json = json.loads(clean_text)
                        return parsed_json, None, model_name
                    except:
                        status_placeholder.warning(f"⚠️ `{model_name}` returned bad data format. Skipping...")
                        continue

            if response.status_code in [429, 400, 503]:
                status_placeholder.warning(f"⚠️ `{model_name}` failed. Switching engines...")
                time.sleep(1)
                continue
            
            return None, f"Error ({response.status_code}): {response.text}", model_name
            
        except Exception as e:
            return None, str(e), model_name
            
    return None, "All available models failed.", "All"

# --- 3. FLEXIBLE READER ---
def get_any(d, keys, default=""):
    for k in keys:
        if k in d and d[k]: return d[k]
        if k.lower() in d and d[k.lower()]: return d[k.lower()]
    return default

# --- 4. GALLERY DOWNLOADER ---
@st.cache_data(show_spinner=False)
def load_gallery_image(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        return response.content
    except Exception as e: return None

# --- 5. HELPER: TEXT FILE ---
def create_lesson_file(data, lang_name):
    # Create a nice readable text format
    text = f"🌍 VISTA VOCALE - {lang_name.upper()} LESSON\n==========================================\n\n"
    
    text += "1. VOCABULARY\n-------------\n"
    for item in data.get('vocabulary', []):
        if isinstance(item, dict):
            word = get_any(item, ['target_word', 'word'])
            pron = get_any(item, ['pronunciation', 'pinyin'])
            sent = get_any(item, ['target_sentence', 'sentence'])
            sent_pron = get_any(item, ['sentence_pronunciation', 'sentence_pinyin'])
            trans = get_any(item, ['english_translation', 'translation'])
            
            text += f"* {word}"
            if pron: text += f" [{pron}]"
            text += f"\n  SENTENCE: {sent}\n"
            if sent_pron: text += f"  PINYIN: {sent_pron}\n"
            text += f"  MEANING: {trans}\n\n"

    text += "2. CONVERSATION\n---------------\n"
    for turn in data.get('conversation', []):
        if isinstance(turn, dict):
            speaker = get_any(turn, ['speaker', 'role'])
            txt = get_any(turn, ['target_text', 'text'])
            text += f"{speaker}: {txt}\n"
            
    text += "\n3. STORY\n--------\n"
    for chunk in data.get('story', []):
        if isinstance(chunk, dict):
            text += get_any(chunk, ['target_text', 'text']) + "\n"
            
    return text

def get_audio_bytes(text, lang_code):
    try:
        fp = BytesIO()
        gTTS(text=text, lang=lang_code).write_to_fp(fp)
        fp.seek(0)
        return fp
    except: return None

# --- MAIN APP LAYOUT ---
st.title("🌍 Vista Vocale")
my_models = get_prioritized_models()

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
            if not my_models:
                 st.error("Could not find any AI models in your account.")
            else:
                lesson_data, error, used_model = generate_lesson_with_fallback(final_image_bytes, current_lang, my_models)
                
                if error:
                    st.error(error)
                elif lesson_data:
                    st.session_state['lesson_data'] = lesson_data
                    st.session_state['current_lang'] = current_lang
                    st.session_state['used_model'] = used_model

    if 'lesson_data' in st.session_state:
        data = st.session_state['lesson_data']
        lang = st.session_state['current_lang']
        st.caption(f"✨ Generated using: `{st.session_state.get('used_model', 'Unknown')}`")
        st.markdown("---")
        t1, t2, t3, t4, t5 = st.tabs(["📖 Vocab", "🗣️ Chat", "📜 Story", "🇺🇸 Key", "💾 Save"])
        
        # --- TAB 1: VOCAB ---
        with t1:
            for item in data.get('vocabulary', []):
                if isinstance(item, dict):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        word = get_any(item, ['target_word', 'word'])
                        pron = get_any(item, ['pronunciation', 'pinyin'])
                        sent = get_any(item, ['target_sentence', 'sentence'])
                        # NEW: Try to get sentence pinyin
                        sent_pron = get_any(item, ['sentence_pronunciation', 'sentence_pinyin'])
                        
                        st.markdown(f"<div class='vocab-word'>{word}</div>", unsafe_allow_html=True)
                        if pron: st.markdown(f"<div class='pinyin'>{pron}</div>", unsafe_allow_html=True)
                        
                        st.markdown(f"_{sent}_")
                        # NEW: Display sentence pinyin if available
                        if sent_pron: st.markdown(f"<div class='pinyin' style='font-size: 0.9rem;'>{sent_pron}</div>", unsafe_allow_html=True)
                        
                    with c2:
                        ab = get_audio_bytes(f"{word}... {sent}", lang['code'])
                        if ab: st.audio(ab, format='audio/mp3')
                    st.divider()

        # --- TAB 2: CHAT ---
        with t2:
            for turn in data.get('conversation', []):
                c1, c2 = st.columns([3, 1])
                with c1:
                    if isinstance(turn, dict):
                        speaker = get_any(turn, ['speaker', 'role'], 'Speaker')
                        text = get_any(turn, ['target_text', 'text'])
                        pron = get_any(turn, ['pronunciation', 'pinyin'])
                        
                        st.markdown(f"**{speaker}**: {text}")
                        if pron: st.markdown(f"<div class='pinyin'>{pron}</div>", unsafe_allow_html=True)
                        text_for_audio = text
                    else:
                        st.markdown(str(turn))
                        text_for_audio = str(turn)
                with c2:
                    ab = get_audio_bytes(text_for_audio, lang['code'])
                    if ab: st.audio(ab, format='audio/mp3')
                st.divider()

        # --- TAB 3: STORY ---
        with t3:
            for chunk in data.get('story', []):
                c1, c2 = st.columns([3, 1])
                with c1:
                    if isinstance(chunk, dict):
                        text = get_any(chunk, ['target_text', 'text'])
                        pron = get_any(chunk, ['pronunciation', 'pinyin'])
                        
                        st.markdown(f"📖 {text}")
                        if pron: st.markdown(f"<div class='pinyin'>{pron}</div>", unsafe_allow_html=True)
                        text_for_audio = text
                    else:
                        st.markdown(f"📖 {str(chunk)}")
                        text_for_audio = str(chunk)
                with c2:
                    ab = get_audio_bytes(text_for_audio, lang['code'])
                    if ab: st.audio(ab, format='audio/mp3')
                st.divider()

        # --- TAB 4: ANSWER KEY ---
        with t4:
            st.header("🇺🇸 Answer Key")
            for item in data.get('vocabulary', []):
                if isinstance(item, dict):
                    word = get_any(item, ['target_word', 'word'])
                    obj = get_any(item, ['object_name', 'meaning'])
                    trans = get_any(item, ['english_translation', 'translation'])
                    st.markdown(f"**{word}** = *{obj}*")
                    st.caption(f"Sent: {trans}")
                    st.divider()

        # --- TAB 5: DOWNLOAD ---
        with t5:
            st.header("💾 Download Notes")
            lesson_text = create_lesson_file(data, lang['name'])
            # Explicitly label as .txt to avoid confusion
            st.download_button(label=f"📥 Download Lesson (.txt)", data=lesson_text, file_name=f"{lang['name']}_Lesson.txt", mime="text/plain")
