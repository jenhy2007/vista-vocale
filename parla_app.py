import streamlit as st
from streamlit_mic_recorder import mic_recorder
import google.generativeai as genai
from gtts import gTTS
import io

# --- CONFIGURATION ---
st.set_page_config(page_title="Project Parla (Memory)", layout="centered")

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

st.title("🗣️ Parla con Giulia (Smart)")

# --- 1. INITIALIZE MEMORY ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {"role": "user", "parts": ["Ciao!"]},
        {"role": "model", "parts": ["Ciao! Sono Giulia, la tua insegnante. Come stai?"]}
    ]

# --- 2. DISPLAY CHAT HISTORY ---
# We show the last few turns so you remember what is happening
for message in st.session_state.chat_history[-4:]: # Show last 4 messages only
    role_class = "user-msg" if message["role"] == "user" else "ai-msg"
    prefix = "👤 Tu:" if message["role"] == "user" else "🇮🇹 Giulia:"
    st.markdown(f"<div class='chat-box {role_class}'><b>{prefix}</b> {message['parts'][0]}</div>", unsafe_allow_html=True)

# --- 3. MICROPHONE INPUT ---
c1, c2, c3 = st.columns([1, 2, 1])
with c2:
    audio = mic_recorder(
        start_prompt="🎤 Hold to Speak",
        stop_prompt="⏹️ Release to Send",
        just_once=True,
        key='recorder'
    )

# --- 4. PROCESSING LOOP ---
if audio:
    user_audio_bytes = audio['bytes']
    
    with st.spinner("🎧 Ascoltando..."):
        try:
            # A. GET TRANSCRIPT (What did you say?)
            model_listen = genai.GenerativeModel("gemini-2.5-flash")
            transcription = model_listen.generate_content([
                "Transcribe this audio to Italian text perfectly.",
                {"mime_type": "audio/wav", "data": user_audio_bytes}
            ])
            user_text = transcription.text
            
            # B. APPEND TO HISTORY
            st.session_state.chat_history.append({"role": "user", "parts": [user_text]})
            
            # C. GENERATE RESPONSE (With Context!)
            # We send the WHOLE history to the chat model
            model_chat = genai.GenerativeModel("gemini-2.5-flash")
            chat = model_chat.start_chat(history=st.session_state.chat_history)
            
            response = chat.send_message(
                "Reply in Italian (A1 level). Keep it short (1 sentence). Ask a follow-up question to keep the conversation going."
            )
            ai_text = response.text
            
            # D. APPEND AI RESPONSE TO HISTORY
            st.session_state.chat_history.append({"role": "model", "parts": [ai_text]})
            
            # E. SPEAK IT
            tts = gTTS(text=ai_text, lang='it')
            audio_fp = io.BytesIO()
            tts.write_to_fp(audio_fp)
            audio_fp.seek(0)
            
            # RERUN to update the chat display and play audio
            st.audio(audio_fp, format='audio/mp3', autoplay=True)
            st.rerun()
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
