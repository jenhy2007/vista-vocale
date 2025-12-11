import os
import streamlit as st
from google import genai
from google.genai import types
import requests
from io import BytesIO
import json
from gtts import gTTS # New import for audio

# --- CONFIGURATION ---
API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash"

SYSTEM_INSTRUCTION = """
You are an Italian language image analysis tutor. Your task is to identify key objects in the image relevant to a beginner Italian lesson.
You must output a single, complete JSON object. Do not include any text, conversation, or explanation outside of the JSON block.

The JSON object MUST contain one key, "vocabulary", which holds an array of three items.
Each item in the "vocabulary" array must be a JSON object containing these four keys:
1. "object_name": The English name of the object (e.g., "cheese").
2. "italian_word": The corresponding Italian word (e.g., "il formaggio").
3. "english_translation": The English translation of the sentence.
4. "italian_sentence": A simple, A1-level Italian sentence using the word (e.g., "Il formaggio è delizioso.").
"""

# --- PAGE CONFIG ---
st.set_page_config(page_title="Vista Vocale", layout="wide")

# --- FUNCTIONS ---

def get_audio_bytes(text, lang='it'):
    """Generates audio mp3 bytes for the given text."""
    try:
        tts = gTTS(text=text, lang=lang)
        fp = BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp
    except Exception as e:
        st.error(f"Audio error: {e}")
        return None

def analyze_image_lesson(image_url):
    """Downloads the image and sends it to Gemini. Returns BOTH the JSON and the image data."""
    if not API_KEY:
        st.error("!!! ERROR: GEMINI_API_KEY is not set. Please run the SET command in Command Prompt.")
        return None, None

    try:
        # 1. Download the image file (Robust way with Headers)
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(image_url, headers=headers)
        response.raise_for_status() 
        image_bytes = response.content 

        # 2. Prepare data for Gemini
        content = [
            types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'),
            "List key objects in this image for an Italian lesson."
        ]
        
        # 3. Call Gemini API
        client = genai.Client(api_key=API_KEY)
        gemini_response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=content,
            config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION)
        )
        
        # 4. Parse JSON
        json_text = gemini_response.text.strip('```json\n').strip('\n```')
        return json.loads(json_text), image_bytes
        
    except Exception as e:
        st.error(f"Error processing image: {e}")
        return None, None

# --- MAIN APP LAYOUT ---

st.title("🇮🇹 Vista Vocale: Audio Edition")
st.write("Enter an image URL below to generate an instant Italian lesson with pronunciation.")

# Default URL
default_url = "https://i.imgur.com/8QzL0jT.jpeg"
image_url = st.text_input("Image URL:", default_url)

if st.button("Analyze Image"):
    if image_url:
        with st.spinner("Gemini is analyzing and Bella is preparing her voice..."):
            # Run the analysis
            lesson_data, displayed_image = analyze_image_lesson(image_url)

            if lesson_data and displayed_image:
                st.success("Lesson Generated!")
                
                col1, col2 = st.columns([1, 1.2]) # Make right column slightly wider
                
                with col1:
                    st.image(displayed_image, caption="Lesson Image", use_container_width=True)

                with col2:
                    st.subheader("Vocabulary & Audio")
                    st.markdown("---") # Visual separator
                    
                    if 'vocabulary' in lesson_data:
                        # Iterate through each item to display it beautifully
                        for item in lesson_data['vocabulary']:
                            
                            # 1. Display the Word
                            st.markdown(f"### 🇮🇹 **{item['italian_word']}** _({item['object_name']})_")
                            
                            # 2. Display the Sentence
                            st.write(f"_{item['italian_sentence']}_")
                            st.caption(f"({item['english_translation']})")
                            
                            # 3. Generate and Display Audio Player
                            # We combine the word and the sentence for the audio
                            audio_text = f"{item['italian_word']}... {item['italian_sentence']}"
                            audio_bytes = get_audio_bytes(audio_text)
                            if audio_bytes:
                                st.audio(audio_bytes, format='audio/mp3')
                            
                            st.markdown("---") # Divider between items
                    else:
                        st.warning("No vocabulary found in response.")