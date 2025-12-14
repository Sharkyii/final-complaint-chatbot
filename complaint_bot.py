import streamlit as st
import pandas as pd
import shared_utils as utils
from datetime import datetime
def run():
    st.title("🛡️ Report a Safety Defect")

    # --- ALWAYS INITIALIZE REQUIRED SESSION STATE ---
    if "locked_fields" not in st.session_state:
        st.session_state.locked_fields = set()

    if "record" not in st.session_state:
        st.session_state.record = {field: None for field in utils.COMPLAINT_FIELDS}

    if "attempt_counts" not in st.session_state:
        st.session_state.attempt_counts = {}

    if "no_extraction_count" not in st.session_state:
        st.session_state.no_extraction_count = 0

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "..."}
        ]

    if "page" not in st.session_state:
        st.session_state.page = "CHAT"
        st.session_state.messages = [
            {"role": "assistant", "content": """Hi! I'm here to help you file a safety report. 

You can tell me everything at once or step by step - whatever works for you! For example:

*"My 2019 Honda Civic's brakes failed while driving 60mph in Los Angeles, CA. No crash or injuries, but it was scary. VIN is 1HGBH41JXMN109186"*

Or just start with the basics and I'll guide you through! 😊"""}
        ]
        st.session_state.record = {field: None for field in utils.COMPLAINT_FIELDS}
        st.session_state.attempt_counts = {}
        st.session_state.no_extraction_count = 0  # Track consecutive failed extractions

    # --- SIDEBAR ---
    with st.sidebar:
        st.markdown("### 📊 Progress")
        auto_fields = ["Timestamp", "Input_Length", "Suspicion_Score", "User_Risk_Level"]
        total_fields = [f for f in utils.COMPLAINT_FIELDS if f not in auto_fields]
        filled = len([f for f in total_fields if st.session_state.record.get(f)])
        
        progress_pct = filled / len(total_fields)
        st.progress(progress_pct)
        st.caption(f"**{filled}/{len(total_fields)}** fields collected")
        
        if filled > 0:
            st.markdown("#### ✅ Captured So Far:")
            display_fields = ["Make", "Model", "Model_Year", "VIN", "Description"]
            for f in display_fields:
                val = st.session_state.record.get(f)
                if val:
                    st.text(f"{f}: {val[:30]}...")
        
        st.markdown("---")
        st.markdown("### 🛠️ Tools")
        if st.button("↩️ Undo Last Message", use_container_width=True):
            if len(st.session_state.messages) > 1:
                st.session_state.messages.pop()
                if st.session_state.messages and st.session_state.messages[-1]['role'] == 'user':
                    st.session_state.messages.pop()
                st.rerun()
        
        if st.button("🔄 Start Over", use_container_width=True):
            if st.button("⚠️ Confirm Reset?", type="secondary"):
                st.session_state.clear()
                st.rerun()

    # --- CHAT INTERFACE ---
    if st.session_state.page == "CHAT":
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if prompt := st.chat_input("Type your response here..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            # --- SMART EXTRACTION + VALIDATION ---
            auto_fields = ["Timestamp", "Input_Length", "Suspicion_Score", "User_Risk_Level"]
            remaining = [f for f in utils.COMPLAINT_FIELDS 
                        if f not in auto_fields and st.session_state.record.get(f) is None]
            
            extracted = utils.extract_all_fields_from_text(prompt, remaining, st.session_state.record)
            
            # --- VALIDATE EXTRACTED DATA ---
            validated_data = {}
            validation_errors = {}
            
            for field, value in extracted.items():
                is_valid, validated_value, error_msg = utils.validate_field(field, value)
                
                if is_valid:
                    validated_data[field] = validated_value
                    st.session_state.attempt_counts[field] = 0
                else:
                    validation_errors[field] = error_msg
                    st.session_state.attempt_counts[field] = \
                        st.session_state.attempt_counts.get(field, 0) + 1
            
            # --- SAVE VALID DATA ---
            if validated_data:
                for field, value in validated_data.items():
                    st.session_state.record[field] = value
                    st.toast(f"✅ Got {field}: {value}", icon="📝")
                st.session_state.no_extraction_count = 0  # Reset counter
                
            # --- UPDATE REMAINING FIELDS ---
            remaining = [f for f in utils.COMPLAINT_FIELDS 
                       if f not in auto_fields and st.session_state.record.get(f) is None]
            
            # --- GENERATE AI RESPONSE ---
            with st.spinner("Processing..."):
                if validation_errors:
                    ai_reply = utils.generate_validation_error_response(
                        st.session_state.messages,
                        validation_errors,
                        st.session_state.attempt_counts
                    )
                    st.session_state.no_extraction_count = 0
                    
                elif validated_data and remaining:
                    ai_reply = utils.generate_ai_response(
                        st.session_state.messages,
                        st.session_state.record,
                        remaining,
                        "COMPLAINT"
                    )
                    st.session_state.no_extraction_count = 0
                    
                elif not remaining:
                    ai_reply = "Perfect! I have all the information I need. Let me show you a summary to review! 🎉"
                    st.session_state.page = "REVIEW"
                    
                elif not extracted:
                    # Nothing was extracted - could be small talk or unclear input
                    st.session_state.no_extraction_count = st.session_state.get('no_extraction_count', 0) + 1
                    
                    if st.session_state.no_extraction_count >= 3:
                        # User seems stuck - offer more help
                        ai_reply = f"""I'm having trouble understanding. Let me help! 

I still need the following information:
{chr(10).join(f'• **{field}**: {utils.FIELD_DESCRIPTIONS.get(field, field)}' for field in remaining[:3])}

Could you provide any of these? For example, just say "Toyota Camry 2019" or "My VIN is 1HGBH41JXMN109186" """
                        st.session_state.no_extraction_count = 0
                    else:
                        ai_reply = utils.generate_small_talk_response(
                            st.session_state.messages,
                            remaining
                        )
                else:
                    # Some edge case
                    ai_reply = "Thanks! Let me know if you have any other details to share."
                    st.session_state.no_extraction_count = 0
            
            st.session_state.messages.append({"role": "assistant", "content": ai_reply})
            with st.chat_message("assistant"):
                st.write_stream(utils.stream_text(ai_reply))
            
            # Auto-transition to review if complete
            if not remaining and not validation_errors:
                st.rerun()

    # --- REVIEW PAGE ---
    elif st.session_state.page == "REVIEW":
        st.subheader("✨ Review Your Safety Report")
        st.markdown("Please review all the information below carefully. You can edit any field before submitting.")

        auto_fields = ["Timestamp", "Input_Length", "User_Risk_Level", "Suspicion_Score"]
        display_data = {k: v for k, v in st.session_state.record.items() 
                       if k not in auto_fields and v is not None}
        
        if not display_data:
            st.warning("⚠️ No data collected yet. Let's go back and gather some information!")
            if st.button("← Back to Chat"):
                st.session_state.page = "CHAT"
                st.rerun()
            return
        
        # --- CREATE EXPANDABLE SECTIONS FOR BETTER UX ---
        st.markdown("### 🚗 Vehicle Information")
        vehicle_fields = {k: v for k, v in display_data.items() 
                         if k in ["Make", "Model", "Model_Year", "VIN", "Mileage"]}
        if vehicle_fields:
            df_vehicle = pd.DataFrame(list(vehicle_fields.items()), columns=["Field", "Value"])
            edited_vehicle = st.data_editor(
                df_vehicle,
                num_rows="fixed",
                hide_index=True,
                use_container_width=True,
                key="vehicle_editor",
                column_config={
                    "Field": st.column_config.TextColumn(disabled=True, width="medium"),
                    "Value": st.column_config.TextColumn("Your Information", width="large")
                }
            )
        
        st.markdown("### 📍 Incident Location")
        location_fields = {k: v for k, v in display_data.items() 
                          if k in ["City", "State", "Date_Complaint"]}
        if location_fields:
            df_location = pd.DataFrame(list(location_fields.items()), columns=["Field", "Value"])
            edited_location = st.data_editor(
                df_location,
                num_rows="fixed",
                hide_index=True,
                use_container_width=True,
                key="location_editor",
                column_config={
                    "Field": st.column_config.TextColumn(disabled=True, width="medium"),
                    "Value": st.column_config.TextColumn("Your Information", width="large")
                }
            )
        
        st.markdown("### 🚨 Incident Details")
        incident_fields = {k: v for k, v in display_data.items() 
                          if k in ["Speed", "Crash", "Fire", "Injured", "Deaths", "Component"]}
        if incident_fields:
            df_incident = pd.DataFrame(list(incident_fields.items()), columns=["Field", "Value"])
            edited_incident = st.data_editor(
                df_incident,
                num_rows="fixed",
                hide_index=True,
                use_container_width=True,
                key="incident_editor",
                column_config={
                    "Field": st.column_config.TextColumn(disabled=True, width="medium"),
                    "Value": st.column_config.TextColumn("Your Information", width="large")
                }
            )
        
        st.markdown("### 📝 Full Description")
        description_fields = {k: v for k, v in display_data.items() 
                             if k in ["Description", "Technician_Notes", "Brake_Condition", "Engine_Temperature"]}
        if description_fields:
            df_description = pd.DataFrame(list(description_fields.items()), columns=["Field", "Value"])
            edited_description = st.data_editor(
                df_description,
                num_rows="fixed",
                hide_index=True,
                use_container_width=True,
                key="description_editor",
                column_config={
                    "Field": st.column_config.TextColumn(disabled=True, width="medium"),
                    "Value": st.column_config.TextColumn("Your Information", width="large")
                }
            )
        
        st.markdown("---")
        
        # --- ACTION BUTTONS ---
        col1, col2, col3 = st.columns([3, 2, 1])
        
        with col1:
            if st.button("📤 Submit Safety Report", type="primary", use_container_width=True):
                all_editors = [
                    ('vehicle_editor', edited_vehicle if 'edited_vehicle' in locals() else None),
                    ('location_editor', edited_location if 'edited_location' in locals() else None),
                    ('incident_editor', edited_incident if 'edited_incident' in locals() else None),
                    ('description_editor', edited_description if 'edited_description' in locals() else None)
                ]
                
                for editor_name, df in all_editors:
                    if df is not None:
                        for index, row in df.iterrows():
                            st.session_state.record[row["Field"]] = row["Value"]
                
                st.session_state.record["Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state.record["Input_Length"] = sum(
                    len(str(v)) for v in st.session_state.record.values() if v
                )
                st.session_state.record["User_Risk_Level"] = "LOW"
                st.session_state.record["Suspicion_Score"] = "0"

                with st.spinner("📡 Submitting your safety report..."):
                    success = utils.save_to_sheet(st.session_state.record, "COMPLAINT")
                
                if success:
                    st.session_state.page = "SUCCESS"
                    st.rerun()
                else:
                    st.error("❌ Submission failed. Please check your internet connection and try again.")
        
        with col2:
            if st.button("💬 Add More Details", use_container_width=True):
                st.session_state.page = "CHAT"
                st.rerun()
        
        with col3:
            if st.button("🗑️ Clear", use_container_width=True):
                if st.button("⚠️ Confirm?"):
                    st.session_state.clear()
                    st.rerun()

    # --- SUCCESS PAGE ---
    elif st.session_state.page == "SUCCESS":
        st.balloons()
        
        st.success("### 🎉 Report Submitted Successfully!")
        
        report_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        st.info(f"""
        **Report Reference ID:** `{report_id}`
        
        Please save this ID for your records. You can use it to track the status of your report.
        """)
        
        st.markdown("---")
        st.markdown("### What Happens Next?")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            **📋 Review Process**
            - Our safety team will review your report within 2-3 business days
            - You may be contacted if we need additional information
            - Critical safety issues are prioritized for immediate review
            """)
        
        with col2:
            st.markdown("""
            **📧 Follow-Up**
            - You'll receive a confirmation email shortly
            - Updates will be sent as your case progresses
            - For urgent matters, call our safety hotline: **1-800-XXX-XXXX**
            """)
        
        st.markdown("---")
        st.markdown("### Your Safety Matters")
        st.markdown("Thank you for taking the time to report this issue. Reports like yours help make vehicles safer for everyone.")
        
        st.markdown("---")
        
        col_a, col_b, col_c = st.columns([2, 2, 1])
        with col_a:
            if st.button("📝 File Another Report", type="primary", use_container_width=True):
                st.session_state.clear()
                st.rerun()
        
        with col_b:
            if st.button("🏠 Return to Home", use_container_width=True):
                st.session_state.clear()
                st.rerun()
        
        with col_c:
            if st.download_button(
                label="⬇️ PDF",
                data=generate_pdf_summary(st.session_state.record),
                file_name=f"safety_report_{report_id}.txt",
                mime="text/plain",
                use_container_width=True
            ):
                st.toast("Report downloaded!", icon="✅")


def generate_pdf_summary(record):
    """Generate a simple text summary of the report"""
    summary = f"""VEHICLE SAFETY REPORT SUMMARY
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
{'='*50}

VEHICLE INFORMATION
"""
    vehicle_fields = ["Make", "Model", "Model_Year", "VIN", "Mileage"]
    for field in vehicle_fields:
        if record.get(field):
            summary += f"{field}: {record[field]}\n"
    
    summary += f"\nINCIDENT DETAILS\n"
    incident_fields = ["Date_Complaint", "City", "State", "Speed", "Crash", "Fire", "Injured", "Deaths"]
    for field in incident_fields:
        if record.get(field):
            summary += f"{field}: {record[field]}\n"
    
    summary += f"\nDESCRIPTION\n"
    if record.get("Description"):
        summary += f"{record['Description']}\n"
    
    summary += f"\n{'='*50}\nEnd of Report"
    
    return summary