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
import time # We need time to wait between retries

# --- 1. SILENCE WARNINGS ---
warnings.filterwarnings("ignore")

# --- CONFIGURATION ---
API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash"

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
    teacher_mode = st.checkbox("🎓 Teacher Mode", value=False, help="Hide English text for quizzing.")
    st.info("Tip: If Search fails, try the 'Paste URL' tab.")

# --- FUNCTIONS ---
def search_image(query):
    try:
        results = DDGS().images(keywords=query, max_results=1)
        if results: return results[0]['image']
        return None
    except: return None

def get_audio_bytes(text, lang='it'):
    try:
        tts = gTTS(text=text, lang=lang)
        fp = BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp
    except: return None

# --- CACHING WITH RETRY LOGIC ---
@st.cache_data(show_spinner=False)
def analyze_image_lesson(image_url):
    if not API_KEY: return None, None

    # 1. Download Image
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(image_url, headers=headers, timeout=10)
        response.raise_for_status() 
        content_type = response.headers.get('Content-Type', '').split(';')[0].strip()
        image_bytes = response.content
    except Exception as e:
        st.error(f"Image Download Error: {e}")
        return None, None

    # 2. Call Gemini with RETRY Loop
    client = genai.Client(api_key=API_KEY)
    content = [types.Part.from_bytes(data=image_bytes, mime_type=content_type), "Create a TPRS lesson."]
    
    # Try 3 times to get an answer
    for attempt in range(3):
        try:
            resp = client.models.generate_content(
                model=GEMINI_MODEL, 
                contents=content,
                config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION)
            )
            # If successful, parse and return immediately
            return json.loads(resp.text.replace('```json', '').replace('```', '').strip()), image_bytes
        
        except Exception as e:
            # If it's the "Overloaded" error (503), wait and try again
            if "503" in str(e) or "Overloaded" in str(e):
                time.sleep(2) # Wait 2 seconds
                continue # Try loop again
            else:
                # If it's a real error (like bad API key), stop.
                st.error(f"AI Error: {e}")
                return None, None
    
    # If we tried 3 times and still failed:
    st.error("Server is very busy (Tried 3 times). Please wait a moment and try again.")
    return None, None

# --- MAIN LAYOUT ---
st.title("🇮🇹 Vista Vocale")

tab_search, tab_paste = st.tabs(["🔍 Search", "🔗 Paste URL"])
final_image_url = None
start_analysis = False

with tab_search:
    c1, c2 = st.columns([3, 1])
    with c1: search_query = st.text_input("Topic:", placeholder="Italian Market", label_visibility="collapsed")
    with c2: 
        if st.button("Search"):
            if search_query:
                with st.spinner("Searching..."):
                    found_url = search_image(search_query)
                    if found_url: 
                        final_image_url = found_url; start_analysis = True
                    else: st.warning("No images found.")

with tab_paste:
    c1, c2 = st.columns([3, 1])
    with c1: pasted_url = st.text_input("URL:", "https://upload.wikimedia.org/wikipedia/commons/d/d6/Gondola_Venice_2016.jpg", label_visibility="collapsed")
    with c2: 
        if st.button("Go"): final_image_url = pasted_url; start_analysis = True

st.markdown("---")

if start_analysis and final_image_url:
    with st.spinner("Gemini is creating the lesson... (Auto-retrying if busy)"):
        lesson_data, img_bytes = analyze_image_lesson(final_image_url)

        if lesson_data:
            col_img, col_content = st.columns([1, 1.3])
            
            with col_img: st.image(img_bytes, use_container_width=True)

            with col_content:
                t1, t2, t3 = st.tabs(["1. Vocabulary", "2. Conversation", "3. Story"])
                
                with t1:
                    if 'vocabulary' in lesson_data:
                        for item in lesson_data['vocabulary']:
                            c1, c2, c3 = st.columns([1.5, 2.5, 0.5])
                            with c1:
                                st.markdown(f"**{item['italian_word']}**")
                                if not teacher_mode: st.caption(item['object_name'])
                            with c2:
                                st.markdown(f"_{item['italian_sentence']}_")
                                if not teacher_mode: st.write(item['english_translation']) 
                            with c3:
                                ab = get_audio_bytes(f"{item['italian_word']}... {item['italian_sentence']}")
                                if ab: st.audio(ab, format='audio/mp3')
                            st.divider()

                with t2:
                    if 'conversation' in lesson_data:
                        for turn in lesson_data['conversation']:
                            c1, c2 = st.columns([4, 1])
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
                            c1, c2 = st.columns([4, 1])
                            with c1:
                                st.markdown(f"📖 **{chunk['italian']}**")
                                if not teacher_mode: st.caption(chunk['english'])
                            with c2:
                                ab = get_audio_bytes(chunk['italian'])
                                if ab: st.audio(ab, format='audio/mp3')
                            st.markdown("")