import streamlit as st
from streamlit_mic_recorder import mic_recorder
import google.generativeai as genai
from gtts import gTTS
import io
import time

# --- CONFIGURATION ---
st.set_page_config(page_title="Parla con Giulia", layout="centered")

try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=API_KEY)
except:
    st.error("❌ API Key missing.")
    st.stop()

# --- STYLING ---
st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 20px; height: 3em; background-color: #f0f2f6; }
    .chat-box { padding: 15px; border-radius: 15px; margin-bottom: 10px; }
    .user-msg { background-color: #e3f2fd; text-align: right; color: #1565c0; }
    .ai-msg { background-color: #f1f8e9; text-align: left; color: #2e7d32; }
    .success-box { padding: 10px; background-color: #e8f5e9; border-radius: 10px; color: #1b5e20; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

st.title("🗣️ Parla con Giulia")

# --- 1. INSTANT TRANSLATION HELPER ---
# No button needed. Just type and hit Enter.
english_text = st.text_input("Type English:", placeholder="e.g. I am retired")

if english_text:
    model_helper = genai.GenerativeModel("gemini-2.5-flash")
    translation = model_helper.generate_content(f"Translate this to simple Italian: '{english_text}'")
    st.markdown(f"<div class='success-box'>🇮🇹 {translation.text}</div>", unsafe_allow_html=True)

# --- 2. INITIALIZE MEMORY ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {"role": "user", "parts": ["Ciao!"]},
        {"role": "model", "parts": ["Ciao! Sono Giulia. Come stai oggi?"]}
    ]

# --- 3. DISPLAY HISTORY ---
for message in st.session_state.chat_history[-4:]: 
    role_class = "user-msg" if message["role"] == "user" else "ai-msg"
    prefix = "👤 Tu:" if message["role"] == "user" else "🇮🇹 Giulia:"
    st.markdown(f"<div class='chat-box {role_class}'><b>{prefix}</b> {message['parts'][0]}</div>", unsafe_allow_html=True)

# --- 4. INPUT ---
c1, c2, c3 = st.columns([1, 2, 1])
with c2:
    audio = mic_recorder(start_prompt="🎤 Speak Italian", stop_prompt="⏹️ Send", just_once=True, key='recorder')

# --- 5. MAIN LOGIC ---
if audio:
    user_audio_bytes = audio['bytes']
    
    with st.spinner("🎧 Ascoltando..."):
        try:
            # A. TRANSCRIPTION
            model_listen = genai.GenerativeModel("gemini-2.5-flash")
            transcription = model_listen.generate_content([
                "Transcribe to Italian.", 
                {"mime_type": "audio/wav", "data": user_audio_bytes}
            ])
            
            user_text = transcription.text
            st.session_state.chat_history.append({"role": "user", "parts": [user_text]})
            
            # B. CHAT RESPONSE
            model_chat = genai.GenerativeModel("gemini-2.5-flash")
            chat = model_chat.start_chat(history=st.session_state.chat_history)
            
            response = chat.send_message(
                "Reply in simple Italian (A1/A2). Keep it short (1-2 sentences). Ask a follow-up question."
            )
            
            ai_text = response.text
            st.session_state.chat_history.append({"role": "model", "parts": [ai_text]})
            
            # C. AUDIO OUTPUT
            tts = gTTS(text=ai_text, lang='it')
            audio_fp = io.BytesIO()
            tts.write_to_fp(audio_fp)
            audio_fp.seek(0)
            
            st.audio(audio_fp, format='audio/mp3', autoplay=True)
            time.sleep(1)
            st.rerun()
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
