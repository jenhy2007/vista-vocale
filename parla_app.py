import streamlit as st
from streamlit_mic_recorder import mic_recorder
import google.generativeai as genai
from gtts import gTTS
import io

# --- CONFIGURATION ---
st.set_page_config(page_title="Project Parla", layout="centered")

try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=API_KEY)
except:
    st.error("❌ API Key missing. Please check Secrets.")
    st.stop()

# --- STYLING ---
st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 20px; height: 3em; }
    h1 { color: #2E86C1; text-align: center; }
    .chat-box { background-color: #f0f2f6; padding: 20px; border-radius: 10px; margin-top: 20px; text-align: center;}
</style>
""", unsafe_allow_html=True)

st.title("🗣️ Parla con Gemini")
st.markdown("### Your AI Speaking Partner")
st.info("Tap the microphone, say something in **Italian** (like 'Ciao, come stai?'), and wait for the reply!")

# --- 1. THE MICROPHONE ---
# We use a unique key so it resets properly
c1, c2, c3 = st.columns([1, 2, 1])
with c2:
    audio = mic_recorder(
        start_prompt="🎤 Start Speaking",
        stop_prompt="⏹️ Stop & Send",
        just_once=True, # Key for "Walkie Talkie" mode
        key='recorder'
    )

# --- 2. THE PROCESSING LOOP ---
if audio:
    # A. Get User Audio
    user_audio_bytes = audio['bytes']
    
    with st.spinner("🎧 Listening & Thinking..."):
        try:
            # B. Send to Gemini (The Brain)
            model = genai.GenerativeModel("gemini-2.5-flash")
            
            # We give it a "Persona"
            prompt = """
            You are a friendly, patient Italian language teacher. 
            Listen to the student's audio.
            Reply in simple, beginner-level Italian (A1/A2).
            Keep your answer short (1-2 sentences) so the conversation is fast.
            """
            
            response = model.generate_content([
                prompt,
                {"mime_type": "audio/wav", "data": user_audio_bytes}
            ])
            
            ai_text_reply = response.text
            
            # C. Convert AI Reply to Audio (The Voice)
            tts = gTTS(text=ai_text_reply, lang='it')
            audio_fp = io.BytesIO()
            tts.write_to_fp(audio_fp)
            audio_fp.seek(0)
            
            # --- 3. THE DISPLAY ---
            st.markdown("---")
            
            # Show what Gemini said (Text)
            st.markdown(f"<div class='chat-box'><h3>🇮🇹 {ai_text_reply}</h3></div>", unsafe_allow_html=True)
            
            # Play what Gemini said (Audio)
            # autoplay=True tries to play immediately, but mobile browsers sometimes block it.
            st.audio(audio_fp, format='audio/mp3', start_time=0)
            
        except Exception as e:
            st.error(f"Connection Error: {str(e)}")
