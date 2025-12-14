import streamlit as st

# Must be the first Streamlit command
st.set_page_config(page_title="Safety & Feedback Portal", page_icon="🚗", layout="wide")

# Import after page config
import complaint_bot
import feedback_bot

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("🧭 Navigation")
app_mode = st.sidebar.radio(
    "Select a service:",
    ["Home", "Report Safety Issue", "Provide Feedback"],
    index=0
)

# Clear state when switching modes
if "current_mode" not in st.session_state:
    st.session_state.current_mode = app_mode
elif st.session_state.current_mode != app_mode:
    # User switched modes - clear relevant state
    keys_to_clear = [
        "messages", "record", "remaining", "attempt_counts", "completed",
        "no_extraction_count", "last_extracted_count",
        "fb_messages", "fb_record", "fb_remaining", "fb_attempt_counts", "fb_completed"
    ]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    st.session_state.current_mode = app_mode

# --- HOME PAGE ---
if app_mode == "Home":
    st.title("🚗 Vehicle Safety & Feedback Portal")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### 🛡️ Report Safety Issue
        
        File a formal safety complaint about:
        - Vehicle defects
        - Safety concerns
        - Recalls or incidents
        - Component failures
        
        **Our AI assistant will guide you through:**
        - Vehicle identification
        - Incident details
        - Location and timing
        - Safety impact assessment
        """)
        
        st.info("💡 **Tip:** You can provide all details at once or step-by-step!")
    
    with col2:
        st.markdown("""
        ### 🗣️ Provide Feedback
        
        Share your thoughts about:
        - Our services
        - Product quality
        - Website experience
        - Suggestions for improvement
        
        **We value your input on:**
        - Customer service
        - Process improvements
        - Feature requests
        - General comments
        """)
        
        st.info("💡 **Tip:** Your feedback helps us improve!")
    
    st.markdown("---")
    
    # Quick stats
    st.markdown("### 📊 Why Report?")
    col_a, col_b, col_c = st.columns(3)
    
    with col_a:
        st.metric("Response Time", "2-3 Days", "Fast")
    
    with col_b:
        st.metric("Privacy", "100%", "Secure")
    
    with col_c:
        st.metric("AI Assisted", "Smart", "Easy")
    
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666;'>
    <p>🔒 Your information is secure and confidential</p>
    <p>📧 You'll receive confirmation via email</p>
    <p>⚡ Our AI makes reporting fast and easy</p>
    </div>
    """, unsafe_allow_html=True)

# --- COMPLAINT BOT ---
elif app_mode == "Report Safety Issue":
    complaint_bot.run()

# --- FEEDBACK BOT ---
elif app_mode == "Provide Feedback":
    feedback_bot.run()