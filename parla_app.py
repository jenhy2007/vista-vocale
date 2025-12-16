import streamlit as st
from streamlit_mic_recorder import mic_recorder
import google.generativeai as genai
from gtts import gTTS
import io
import time

# --- CONFIGURATION ---
st.set_page_config(page_title="Project Parla (Mobile Fix)", layout="centered")

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
</style>
""", unsafe_allow_html=True)

st.title("🗣️ Parla con Giulia")

# --- 1. INITIALIZE MEMORY ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {"role": "user", "parts": ["Ciao!"]},
        {"role": "model", "parts": ["Ciao! Sono Giulia. Come stai?"]}
    ]

# --- 2. DISPLAY HISTORY ---
for message in st.session_state.chat_history[-4:]: 
    role_class = "user-msg" if message["role"] == "user" else "ai-msg"
    prefix = "👤 Tu:" if message["role"] == "user" else "🇮🇹 Giulia:"
    st.markdown(f"<div class='chat-box {role_class}'><b>{prefix}</b> {message['parts'][0]}</div>", unsafe_allow_html=True)

# --- 3. INPUT ---
c1, c2, c3 = st.columns([1, 2, 1])
with c2:
    audio = mic_recorder(start_prompt="🎤 Speak", stop_prompt="⏹️ Send", just_once=True, key='recorder')

# --- 4. SAFE PROCESSING FUNCTION ---
def safe_generate(model_action, *args, **kwargs):
    """Tries to run AI. If it hits a limit, it waits and retries."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return model_action(*args, **kwargs)
        except Exception as e:
            if "429" in str(e) or "Quota" in str(e):
                wait_time = 15 * (attempt + 1)
                with st.spinner(f"🚦 Traffic jam (Quota). Waiting {wait_time}s..."):
                    time.sleep(wait_time)
                continue 
            else:
                raise e 
    return None

# --- 5. MAIN LOOP ---
if audio:
    user_audio_bytes = audio['bytes']
    
    with st.spinner("🎧 Ascoltando..."):
        try:
            # A. TRANSCRIPTION
            model_listen = genai.GenerativeModel("gemini-2.5-flash")
            transcription = safe_generate(
                model_listen.generate_content,
                ["Transcribe to Italian.", {"mime_type": "audio/wav", "data": user_audio_bytes}]
            )
            
            if transcription:
                user_text = transcription.text
                st.session_state.chat_history.append({"role": "user", "parts": [user_text]})
                
                # B. CHAT RESPONSE
                model_chat = genai.GenerativeModel("gemini-2.5-flash")
                chat = model_chat.start_chat(history=st.session_state.chat_history)
                
                response = safe_generate(
                    chat.send_message,
                    "Reply in simple Italian (A1). Short answer."
                )
                
                if response:
                    ai_text = response.text
                    st.session_state.chat_history.append({"role": "model", "parts": [ai_text]})
                    
                    # C. AUDIO OUTPUT (Mobile Fix: No Autoplay)
                    tts = gTTS(text=ai_text, lang='it')
                    audio_fp = io.BytesIO()
                    tts.write_to_fp(audio_fp)
                    audio_fp.seek(0)
                    
                    # Rerun to show the text first
                    st.session_state['latest_audio'] = audio_fp
                    st.rerun()
                
        except Exception as e:
            st.error(f"System Error: {str(e)}")

# --- 6. PLAY AUDIO AT BOTTOM ---
if 'latest_audio' in st.session_state:
    st.markdown("### 🔊 Listen to Giulia:")
    st.audio(st.session_state['latest_audio'], format='audio/mp3')
