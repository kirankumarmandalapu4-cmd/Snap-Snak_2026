import json
from google import genai
from google.genai import types
import streamlit as st 
from twilio.rest import Client as TwilioClient
from prompts import SYSTEM_PROMPT,WELCOME_MESSAGE_TEMPLATE,SUMMARY_REQUEST_PROMPT

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
TWILIO_ACCOUNT_SID = st.secrets["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = st.secrets["TWILIO_AUTH_TOKEN"]
TWILIO_WHATSAPP_FROM = st.secrets["TWILIO_WHATSAPP_FROM"]   
TWILIO_CONTENT_SID = st.secrets["TWILIO_CONTENT_SID"]

MODEL_NAME = "gemini-3.6-flash"

def clean_whatsapp_text(text):
    if not text:
        return "No nutrition information available."
    text = " ".join(text.split())
    return text[:1500] + "..." if len(text) > 1500 else text

def render_message(message):
    with st.chat_message(message["role"]):
        if message["kind"]=="text":
            st.write(message["content"])
        elif message["kind"]=="image":
            st.image(message["content"])

def add_message(role,kind,content):
    st.session_state.messages.append({"role":role,"kind":kind,"content":content})
    render_message(st.session_state.messages[-1])

def ask_gemini(parts):
    try:
        return st.session_state.chat.send_message(parts).text
    except Exception as e:
        return f"Sorry,something went wrong: {e}"

def send_whatsapp(whatsappno,name,summary):
    try:
        content_variables = json.dumps(
            {"1":name,"2":clean_whatsapp_text(summary)},ensure_ascii=False
            
        )
        message = twilio_client.messages.create(
            from_ = TWILIO_WHATSAPP_FROM,
            to = f"whatsapp:{whatsappno}",
            content_sid = TWILIO_CONTENT_SID,
            content_variables = content_variables,
        )
        return True,message.sid
    except Exception as e:
        return False,str(e)

@st.cache_resource
def get_gemini_client():
    return genai.Client(api_key=GEMINI_API_KEY)

@st.cache_resource
def get_twilio_client():
    return TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

twilio_client = get_twilio_client()

gemini_client = get_gemini_client()

if 'onboarded' not in st.session_state:
    st.title("VisionTranslate AI")
    st.caption("Upload a photo. Translate it instantly.")

    with st.form("onboarding_form"):
        name = st.text_input("Enter your name")
        whatsappno = st.text_input(
            "Enter your WhatsApp number(with country code)",
            placeholder="+91xxxxxxxxxx",
            help="this number will be used for sending notifications"
        )
        submitted = st.form_submit_button("Let's go")

        if submitted:
            if not name.strip() or not whatsappno.strip():
                st.warning("Please fill in both your name and whatsapp number.")
            else:
                st.session_state.name=name.strip()
                st.session_state.whatsappno=whatsappno.strip()
                st.session_state.chat = gemini_client.chats.create(
                    model=MODEL_NAME,
                    config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT)
                )
                st.session_state.messages = []
                st.session_state.onboarded = True
                st.rerun()
        st.stop()

header_col,button_col=st.columns([5,2],vertical_alignment="center")
with header_col:
    st.title("VisionTranslate AI 📷")


with button_col:
    send_disabled= len(st.session_state.messages)<=1
    if st.button("Send details to WhatsApp",disabled=send_disabled,use_container_width=True):
        with st.spinner("Summarizing you day..."):
            summary = ask_gemini([SUMMARY_REQUEST_PROMPT])
        success,info = send_whatsapp(st.session_state.whatsappno,st.session_state.name,summary)
        if success:
            st.success("Summary sent check to your WhatsApp!")    
        else:
            st.error(f"Failed to send summary: {info}") 

st.caption(f"Logged in as {st.session_state.name} - update go to {st.session_state.whatsappno}")



if not st.session_state.messages:
    add_message("assistant","text",WELCOME_MESSAGE_TEMPLATE.format(name=st.session_state.name))
else:
    for message in st.session_state.messages:
        render_message(message)

user_input = st.chat_input(
    "Ask a question,or attach a photo",
    accept_file=True,
    file_type=["jpg","jpeg","png"],
)

if user_input:
    photo = user_input.files[0] if user_input.files else None
    text = user_input.text
    parts = []

    if photo is not None:
        photo_bytes = photo.getvalue()
        add_message("user","image",photo_bytes)
        parts.append(types.Part.from_bytes(data=photo_bytes, mime_type=photo.type))

    if text:
        add_message("user","text",text)
        parts.append(text)
    elif photo is not None:
        parts.append("Extract all readable text from this image, identify the language, and translate it into English. If the text is unclear, mark it as [unclear] instead of guessing.")

    with st.spinner("Translating..."):
        answer = ask_gemini(parts)

    add_message("assistant","text",answer)