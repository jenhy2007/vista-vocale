import streamlit as st
from streamlit_mic_recorder import mic_recorder
import google.generativeai as genai
import io

# --- CONFIGURATION ---
st.set_page_config(page_title="Project Parla - Mic Test")

try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=API_KEY)
except:
    st.error("❌ API Key missing.")
    st.stop()

st.title("🎤 Project Parla: The Ear Test")
st.write("Click the microphone, speak a sentence in Italian, and see if Gemini hears you!")

# --- 1. THE MICROPHONE BUTTON ---
# This creates a button. When you click it, it records. Click again to stop.
audio = mic_recorder(
    start_prompt="⏺️ Record (Speak Now!)",
    stop_prompt="⏹️ Stop (Sending...)",
    key='recorder'
)

# --- 2. THE PROCESSING ---
if audio:
    # Get the audio data bytes
    audio_bytes = audio['bytes']
    
    st.audio(audio_bytes, format='audio/wav')
    st.info("📨 Sending audio to Gemini's ears...")

    # --- 3. SEND TO GEMINI (NATIVE AUDIO SUPPORT) ---
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        # We prompt Gemini to act as a transcriber
        response = model.generate_content([
            "Listen to this audio. Transcribe EXACTLY what was said. If it is Italian, write the Italian words.",
            {"mime_type": "audio/wav", "data": audio_bytes}
        ])
        
        # --- 4. SHOW RESULT ---
        st.success("👂 Gemini Heard:")
        st.markdown(f"## {response.text}")
        
    except Exception as e:
        st.error(f"Error: {str(e)}")
