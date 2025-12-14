import streamlit as st
import time
import requests
import re
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- CONFIGURATION ---
SHEET_NAME = "Safety_Reports"

MODEL_CHAT = "Qwen/Qwen2.5-3B-Instruct"       
MODEL_CLASSIFY = "facebook/bart-large-cnn"    

COMPLAINT_FIELDS = [
    "Timestamp", "Make", "Model", "Model_Year", "VIN", "City", "State",
    "Speed", "Crash", "Fire", "Injured", "Deaths", "Description",
    "Component", "Mileage", "Technician_Notes",
    "Brake_Condition", "Engine_Temperature", "Date_Complaint",
    "Input_Length", "Suspicion_Score", "User_Risk_Level"
]

FEEDBACK_FIELDS = ["Feedback_Timestamp", "Feedback_Topic", "Feedback_Cause_Help"]

AUTOMATED_FIELDS = [
    "Timestamp", "Input_Length", "Suspicion_Score", "User_Risk_Level", 
    "Technician_Notes", "Brake_Condition", "Engine_Temperature"
]

FIELD_DESCRIPTIONS = {
    "Make": "the vehicle brand (like Toyota, Ford)",
    "Model": "the specific model name (like Camry, F-150)",
    "Model_Year": "the year the car was made",
    "VIN": "the 17-character Vehicle Identification Number",
    "City": "the city where the incident happened",
    "State": "the state code (like CA, TX)",
    "Speed": "how fast the vehicle was going (in mph)",
    "Crash": "if a crash happened (Yes/No)",
    "Fire": "if there was any fire or smoke (Yes/No)",
    "Injured": "if anyone was hurt (number of people)",
    "Deaths": "if anyone passed away (number of people)",
    "Description": "a detailed description of what went wrong",
    "Component": "which part failed (like Brakes, Steering)",
    "Mileage": "the total mileage on the odometer",
    "Date_Complaint": "when this happened (YYYY-MM-DD)",
    "Feedback_Topic": "the main topic of your feedback",
    "Feedback_Cause_Help": "details on what caused the issue or how we can help"
}

# --- SESSION STATE INITIALIZATION (REQUIRED) ---
def initialize_session_state():
    """Initialize all session state variables"""
    if "record" not in st.session_state:
        st.session_state.record = {}
    
    if "locked_fields" not in st.session_state:
        st.session_state.locked_fields = set()
    
    if "attempt_counts" not in st.session_state:
        st.session_state.attempt_counts = {}
    
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "mode" not in st.session_state:
        st.session_state.mode = None
    
    if "submission_complete" not in st.session_state:
        st.session_state.submission_complete = False

# --- API & UTILITIES ---
def get_api_key():
    try:
        return st.secrets["huggingface"]["api_key"]
    except:
        return None
def query_llm(messages, max_tokens=150, temperature=0.7):
    """
    Generic wrapper for Hugging Face Router (OpenAI-compatible).
    Uses Qwen/Qwen2.5-3B-Instruct model.
    """
    api_key = get_api_key()
    if not api_key:
        return "Error: API Key missing."

    API_URL = "https://router.huggingface.co/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "meta-llama/Llama-3.1-8B-Instruct",
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature
    }

    try:
        response = requests.post(
            API_URL,
            headers=headers,
            json=payload,
            timeout=8
        )

        if response.status_code != 200:
            return f"API Error {response.status_code}: {response.text}"

        result = response.json()

        # OpenAI-style response parsing (HF Router)
        if (
            isinstance(result, dict)
            and "choices" in result
            and len(result["choices"]) > 0
            and "message" in result["choices"][0]
        ):
            return result["choices"][0]["message"]["content"].strip()

        if "error" in result:
            return f"API Error: {result['error']}"

        return f"Unexpected response format: {result}"

    except Exception as e:
        return f"Request Error: {str(e)}"

def stream_text(text):
    for word in text.split(" "):
        yield word + " "
        time.sleep(0.02)

def save_to_sheet(record, mode):
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        
        try:
            sheet = client.open(SHEET_NAME).sheet1
        except gspread.SpreadsheetNotFound:
            st.error(f"Spreadsheet '{SHEET_NAME}' not found.")
            return False

        row_data = []
        record["Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if mode == "COMPLAINT":
            row_data = [str(record.get(f, "")) for f in COMPLAINT_FIELDS]
        elif mode == "FEEDBACK":
            row_data = ["" for _ in COMPLAINT_FIELDS]
            row_data.extend([str(record.get(f, "")) for f in FEEDBACK_FIELDS])
            
        sheet.append_row(row_data)
        return True
    except Exception as e:
        print(f"Database Error: {e}")
        return False

# --- LLM EXTRACTION ---
def extract_all_fields_from_text(user_text, remaining_fields, current_record):
    """
    Uses LLM to extract JSON data from user text.
    Handles out-of-order and complex inputs.
    """
    import json
    
    # Filter fields to only look for relevant ones to save tokens/confusion
    relevant_fields = {k: v for k, v in FIELD_DESCRIPTIONS.items() 
                      if k in remaining_fields or k in ["Make", "Model", "VIN", "Description"]}
    
    system_prompt = f"""You are a smart data extraction assistant.
    Review the user's input and extract any of the following fields into a JSON object.
    
    Fields to look for:
    {json.dumps(relevant_fields, indent=2)}
    
    Rules:
    1. Return ONLY valid JSON. No other text.
    2. If a field is not mentioned, do not include it in the JSON.
    3. Be smart: "My 2019 Camry" -> {{'Make': 'Toyota', 'Model': 'Camry', 'Model_Year': '2019'}} if Make is implied.
    4. For 'Crash', 'Fire': extract "YES" or "NO" if explicitly stated.
    5. 'Injured', 'Deaths': extract numbers.
    6. Extract as much as possible, even if out of order.
    """
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text}
    ]
    
    response_text = query_llm(messages, max_tokens=300, temperature=0.1)
    
    try:
        # cleanup json if LLM adds markdown
        json_str = response_text.replace("```json", "").replace("```", "").strip()
        data = json.loads(json_str)
        return data
    except:
        return {}

# --- LLM VALIDATION ---
def validate_field(field, value):
    """
    Uses LLM to validate the field value.
    Returns (is_valid, clean_value, error_message)
    """
    val = str(value).strip()

    if field in st.session_state.locked_fields:
        return False, value, f"❌ {field} is already confirmed. (Type 'yes' to unlock)"

    import json
    
    system_prompt = f"""You are a data validator. Validate the value '{value}' for the field '{field}'.
    Field Description: {FIELD_DESCRIPTIONS.get(field, 'No description')}
    
    Rules:
    - VIN: Must be 17 chars, no I, O, Q.
    - State: 2 letter US State code.
    - Model_Year: 4 digit year (1950-2025).
    - Speed: Number 0-200.
    
    Return JSON:
    {{
        "is_valid": true/false,
        "clean_value": "formatted value",
        "error_msg": "friendly error message if invalid, else null"
    }}
    """
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Validate {field}: {value}"}
    ]
    
    response_text = query_llm(messages, max_tokens=150, temperature=0.1)
    
    try:
        json_str = response_text.replace("```json", "").replace("```", "").strip()
        result = json.loads(json_str)
        
        if result["is_valid"]:
            # Hard code locking logic for critical fields
            if field in ["VIN", "Date_Complaint"]:
                st.session_state.locked_fields.add(field)
            return True, result["clean_value"], None
        else:
            return False, value, result["error_msg"]
    except:
        # Fallback to true if LLM fails, to not block user
        return True, value, None

# --- LLM RESPONSE GENERATION ---
def generate_ai_response(messages, record, remaining_fields, mode="COMPLAINT"):
    """
    Uses LLM to generate the next helpful conversational response.
    """
    # Simply critical and next fields
    critical = [f for f in ["VIN", "Make", "Model", "Description"] if f in remaining_fields]
    next_up = remaining_fields[:3] if remaining_fields else []
    
    # Force VIN after failed attempts
    # Note: Accessing st.session_state directly here as it's a shared util for streamlit apps
    if "VIN" in remaining_fields and st.session_state["attempt_counts"].get("VIN", 0) > 0:
        return "⚠️ I still need the **VIN** (17-character code). This is required to proceed."
    
    system_prompt = f"""You are a helpful empathetic safety reporting assistant.
    Current Mode: {mode}
    
    Context:
    - Collected so far: {record}
    - Critical missing: {critical}
    - Next fields to ask: {next_up}
    - User struggling with VIN: {vin_stuck}
    
    Goal:
    1. Acknowledge what was just provided.
    2. Ask for the next missing information.
    3. If the user seems confused or is stuck (especially on VIN), EXPLAIN the field clearly (e.g. where to find it).
    4. Allow the user to SKIP non-critical fields if they insist. For VIN, be persuasive but eventually allow skipping if they really can't find it.
    5. Be concise and friendly.
    """
    
    # tailored messages for context
    chat_context = [{"role": "system", "content": system_prompt}]
    # Add last few messages for context
    chat_context.extend(messages[-3:])
    
    response = query_llm(chat_context, max_tokens=150, temperature=0.7)
    return response

def generate_validation_error_response(messages, validation_errors, attempt_counts):
    """
    Uses LLM to explain errors nicely.
    """
    system_prompt = f"""You are a helpful assistant. The user provided invalid data.
    Direct them to fix it.
    
    Errors:
    {validation_errors}
    
    Write a short, encouraging message asking them to correct these fields.
    """
    return query_llm([{"role": "system", "content": system_prompt}], max_tokens=100)

def generate_small_talk_response(messages, remaining_fields):
    """
    Uses LLM to handle chitchat but steer back to business immediately.
    """
    next_field = remaining_fields[:1] if isinstance(remaining_fields, list) and remaining_fields else 'the incident details'
    
    system_prompt = f"""You are a professional data collection assistant.
    The user is chatting instead of providing data.
    
    Instructions:
    1. Acknowledge the input with a polite, professional sentence.
    2. Immediately pivot to asking for the missing field: {next_field}.
    3. Output MUST be natural text. Do NOT output lists, JSON, or robotic commands.
    4. Tone: Professional and Direct.
    """
    # Pass last user message
    last_msg = messages[-1]['content']
    return query_llm([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": last_msg}
    ], max_tokens=80)

# --- LLM RESPONSE GENERATION ---
def generate_ai_response(messages, record, remaining_fields, mode="COMPLAINT"):
    """
    Uses LLM to generate the next helpful conversational response.
    """
    # Simply critical and next fields
    critical = [f for f in ["VIN", "Make", "Model", "Description"] if f in remaining_fields]
    next_up = remaining_fields[:3] if remaining_fields else []
    
    # Force VIN after failed attempts
    # Note: Accessing st.session_state directly here as it's a shared util for streamlit apps
    if "VIN" in remaining_fields and st.session_state["attempt_counts"].get("VIN", 0) > 0:
        return "⚠️ I still need the **VIN** (17-character code). This is required to proceed."
    
    # Check if user is stuck on VIN (attempt count > 0)
    vin_stuck = "VIN" in remaining_fields and st.session_state["attempt_counts"].get("VIN", 0) > 0
    
    system_prompt = f"""You are a professional safety reporting assistant.
    Current Mode: {mode}
    
    Context:
    - Collected so far: {record}
    - Critical missing: {critical}
    - Next fields to ask: {next_up}
    - User struggling with VIN: {vin_stuck}
    
    Goal:
    1. Acknowledge what was just provided with a complete, professional sentence.
    2. Ask for the next missing information clearly in natural language.
    3. If the user seems confusion, EXPLAIN the field technically.
    4. Do NOT allow skipping. All fields are mandatory for safety compliance.
    5. Output MUST be natural text. Do NOT output lists or JSON.
    6. Tone: Professional, Concise, Serious.
    """
    
    # tailored messages for context
    chat_context = [{"role": "system", "content": system_prompt}]
    # Add last few messages for context
    chat_context.extend(messages[-3:])
    
    response = query_llm(chat_context, max_tokens=150, temperature=0.5)
    return response
