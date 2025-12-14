import streamlit as st
import pandas as pd
import shared_utils as utils
from datetime import datetime

def run():
    st.title("🗣️ Share Your Feedback")

    # --- INITIALIZATION ---
    if "fb_page" not in st.session_state:
        st.session_state.fb_page = "CHAT"
        st.session_state.fb_messages = [
            {"role": "assistant", "content": "Hey there! We'd love to hear your feedback. What's on your mind today? Feel free to share everything - your experience, suggestions, or any concerns you have! 💭"}
        ]
        st.session_state.record = {field: None for field in utils.FEEDBACK_FIELDS}

    # --- SIDEBAR ---
    with st.sidebar:
        st.markdown("### Your Feedback")
        filled = len([f for f in utils.FEEDBACK_FIELDS 
                     if f != "Feedback_Timestamp" and st.session_state.record.get(f)])
        total = len([f for f in utils.FEEDBACK_FIELDS if f != "Feedback_Timestamp"])
        
        if filled > 0:
            st.progress(filled / total)
            st.caption(f"{filled}/{total} sections completed")
        
        st.markdown("---")
        if st.button("↩️ Undo Last Message"):
            if len(st.session_state.fb_messages) > 1:
                st.session_state.fb_messages.pop()
                if st.session_state.fb_messages and st.session_state.fb_messages[-1]['role'] == 'user':
                    st.session_state.fb_messages.pop()
                st.rerun()

    # --- CHAT INTERFACE ---
    if st.session_state.fb_page == "CHAT":
        for msg in st.session_state.fb_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if prompt := st.chat_input("Type your feedback here..."):
            st.session_state.fb_messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            # --- SMART EXTRACTION ---
            remaining = [f for f in utils.FEEDBACK_FIELDS 
                        if f != "Feedback_Timestamp" and st.session_state.record.get(f) is None]
            
            # For feedback, we use simpler extraction since there are only 2 main fields
            extracted = {}
            
            # Identify topic keywords
            if "Feedback_Topic" in remaining:
                topics = {
                    "service": ["service", "support", "help", "assistance"],
                    "product": ["product", "quality", "feature", "functionality"],
                    "website": ["website", "app", "interface", "navigation", "ui"],
                    "billing": ["billing", "payment", "charge", "invoice", "price"],
                    "suggestion": ["suggest", "recommend", "improve", "enhancement", "idea"],
                    "complaint": ["complaint", "issue", "problem", "concern", "dissatisfied"]
                }
                
                text_lower = prompt.lower()
                for topic, keywords in topics.items():
                    if any(kw in text_lower for kw in keywords):
                        extracted["Feedback_Topic"] = topic.title()
                        break
                
                # If no keyword match but text is substantial, use first few words
                if "Feedback_Topic" not in extracted and len(prompt.split()) > 3:
                    first_words = " ".join(prompt.split()[:4])
                    extracted["Feedback_Topic"] = first_words
            
            # If message is detailed, capture as the main feedback
            if "Feedback_Cause_Help" in remaining and len(prompt) > 20:
                extracted["Feedback_Cause_Help"] = prompt
            
            if extracted:
                for field, value in extracted.items():
                    st.session_state.record[field] = value
                    st.toast(f"✅ Noted: {field}", icon="📝")
                
                remaining = [f for f in utils.FEEDBACK_FIELDS 
                           if f != "Feedback_Timestamp" and st.session_state.record.get(f) is None]
                
                if remaining:
                    with st.spinner("Thinking..."):
                        ai_reply = utils.generate_ai_response(
                            st.session_state.fb_messages,
                            st.session_state.record,
                            remaining,
                            "FEEDBACK"
                        )
                    
                    st.session_state.fb_messages.append({"role": "assistant", "content": ai_reply})
                    with st.chat_message("assistant"):
                        st.write_stream(utils.stream_text(ai_reply))
                else:
                    st.session_state.fb_page = "REVIEW"
                    st.rerun()
            else:
                # Small talk or unclear input
                with st.spinner("..."):
                    ai_reply = utils.generate_small_talk_response(
                        st.session_state.fb_messages,
                        ["your feedback"]
                    )
                
                st.session_state.fb_messages.append({"role": "assistant", "content": ai_reply})
                with st.chat_message("assistant"):
                    st.write_stream(utils.stream_text(ai_reply))

    # --- REVIEW PAGE ---
    elif st.session_state.fb_page == "REVIEW":
        st.subheader("✨ Review Your Feedback")
        st.markdown("Take a moment to review what you've shared. You can edit anything below!")

        display_data = {k: v for k, v in st.session_state.record.items() 
                       if v is not None and k != "Feedback_Timestamp"}
        
        if not display_data:
            st.warning("Let's add some feedback first!")
            if st.button("Back to Chat"):
                st.session_state.fb_page = "CHAT"
                st.rerun()
            return
        
        df = pd.DataFrame(list(display_data.items()), columns=["Field", "Value"])
        
        edited_df = st.data_editor(
            df,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            column_config={
                "Field": st.column_config.TextColumn(disabled=True, width="medium"),
                "Value": st.column_config.TextColumn("Your Feedback", width="large")
            }
        )
        
        st.markdown("---")
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            if st.button("📤 Submit Feedback", type="primary", use_container_width=True):
                for index, row in edited_df.iterrows():
                    st.session_state.record[row["Field"]] = row["Value"]
                
                st.session_state.record["Feedback_Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                with st.spinner("Sending your feedback..."):
                    success = utils.save_to_sheet(st.session_state.record, "FEEDBACK")
                
                if success:
                    st.session_state.fb_page = "SUCCESS"
                    st.rerun()
                else:
                    st.error("Submission failed. Please try again.")
        
        with col2:
            if st.button("💬 Add More Details", use_container_width=True):
                st.session_state.fb_page = "CHAT"
                st.rerun()
        
        with col3:
            if st.button("🔄 Reset"):
                st.session_state.clear()
                st.rerun()

    # --- SUCCESS PAGE ---
    elif st.session_state.fb_page == "SUCCESS":
        st.balloons()
        st.success("### 🎉 Thank You for Your Feedback!")
        st.markdown("We truly appreciate you taking the time to share your thoughts with us.")
        st.info("**Your voice matters!** Our team reviews all feedback to continuously improve our services.")
        
        if st.button("💭 Share More Feedback", type="primary"):
            st.session_state.clear()
            st.rerun()