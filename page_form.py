import streamlit as st
from datetime import datetime
import io
from translations import _t
from config import CURRENT_PARTICIPANTS, SUBMITTER_LIST, GOOGLE_DRIVE_FOLDER_ID
from google_connect import connect_to_google_sheets, connect_to_google_drive, upload_file_to_drive

def show_submission_form(lang):
    """Wyświetla formularz do wprowadzania danych bieżącej edycji."""
    st.header(_t('form_header', lang))
    
    users_list = sorted(CURRENT_PARTICIPANTS)
    submitters_list_sorted = sorted(SUBMITTER_LIST)
    
    if 'last_submission' in st.session_state and st.session_state.last_submission:
        details = st.session_state.last_submission
        st.success(_t('form_success_message', lang, details['participant'], details['day'], details['status_translated']))
        
        with st.expander(_t('form_confirmation_header', lang), expanded=True):
            st.write(f"**{_t('form_confirmation_participant', lang)}:** {details['participant']}")
            st.write(f"**{_t('form_confirmation_day', lang)}:** {details['day']}")
            st.write(f"**{_t('form_confirmation_status', lang)}:** {details['status_translated']}")
            st.write(f"**{_t('form_confirmation_notes', lang)}:** {details['full_notes'] if details['full_notes'] else _t('form_confirmation_notes_empty', lang)}")
        st.info(_t('form_overwrite_info', lang))
        
        st.session_state.last_submission = None 
    
    
    participant, day, status, notes, uploaded_file = None, None, None, None, None
    
    with st.form("submission_form"):
        st.info(_t('form_info', lang))
        
        col1, col2 = st.columns(2)
        with col1:
            submitter = st.selectbox(
                _t('form_submitter_label', lang),
                options=[None] + submitters_list_sorted, 
                index=st.session_state.get('submitter_index_plus_one', 0), 
                format_func=lambda x: _t('form_submitter_placeholder', lang) if x is None else x
            )
            
            participant = st.selectbox(
                _t('form_participant_label', lang),
                options=[None] + users_list, 
                index=0, 
                format_func=lambda x: _t('form_participant_placeholder', lang) if x is None else x
            )
        with col2:
            day = st.number_input(
                _t('form_day_label', lang), 
                min_value=1, 
                max_value=31,
                value=st.session_state.get('last_day_entered', 1),
                step=1
            )
            status = st.radio(
                _t('form_status_label', lang),
                options=[
                    _t('form_status_pass', lang), 
                    _t('form_status_fail', lang), 
                    _t('form_status_no_report', lang)
                ],
                horizontal=True
            )
            st.caption(_t('form_status_info', lang))
        
        submitted = st.form_submit_button(_t('form_submit_button', lang))
        st.caption(_t('form_ranking_info', lang))


        with st.expander(_t('form_converters_expander', lang)):
            st.warning(_t('form_converters_warning', lang))
            st.json({
                "HIKE_RATE (Wędrówka)": 1500,
                "PRIMARY_RATE (Bieg)": 1300,
                "GENERIC_DISTANCE_RATE (Spacer)": 800,
                "CYCLE_RATE (Rower)": 550,
                "EBIKE_RATE (E-Rower)": 400,
                "STEPS_PER_MINUTE_RATE (Inne)": 60
            })

        notes = st.text_area(
            _t('form_notes_label', lang),
            placeholder=_t('form_notes_placeholder', lang)
        )
        
        uploaded_file = st.file_uploader(
            _t('form_upload_label', lang), 
            type=["png", "jpg", "jpeg"]
        )
        
        if GOOGLE_DRIVE_FOLDER_ID != "PASTE_YOUR_FOLDER_ID_HERE" and GOOGLE_DRIVE_FOLDER_ID:
            folder_url = f"https://drive.google.com/drive/folders/{GOOGLE_DRIVE_FOLDER_ID}"
            st.link_button(_t('form_upload_link_text', lang), folder_url, use_container_width=True)

        st.markdown("---")
        st.markdown(_t('form_thanks_note', lang))


    if submitted:
        if not submitter or not participant:
            st.error(_t('form_error_no_participant', lang))
        else:
            st.session_state.submitter_index_plus_one = ([None] + submitters_list_sorted).index(submitter)
            st.session_state.last_day_entered = day + 1 if day < 31 else 31 

            status_key = "Zaliczone"
            if status == _t('form_status_fail', lang):
                status_key = "Niezaliczone"
            elif status == _t('form_status_no_report', lang):
                status_key = "Brak raportu"
            
            # --- Logika Przesyłania Pliku ---
            file_link_text = ""
            if uploaded_file is not None:
                if GOOGLE_DRIVE_FOLDER_ID == "PASTE_YOUR_FOLDER_ID_HERE" or not GOOGLE_DRIVE_FOLDER_ID:
                    st.error(_t('form_error_drive_not_configured', lang))
                    file_link_text = f"Błąd konfiguracji (Plik: {uploaded_file.name})"
                else:
                    drive_service = connect_to_google_drive()
                    if drive_service:
                        file_link = upload_file_to_drive(drive_service, uploaded_file, GOOGLE_DRIVE_FOLDER_ID, lang)
                        if file_link:
                            file_link_text = file_link
                        else:
                            file_link_text = f"(Błąd przesyłania pliku: {uploaded_file.name})"
                    else:
                        file_link_text = "(Błąd połączenia z Google Drive)"
            
            full_notes = f"{notes} | {file_link_text}".strip(" | ")
            timestamp = datetime.now().isoformat()
            # --- Koniec Logiki Przesyłania Pliku ---

            try:
                sheet = connect_to_google_sheets()
                if sheet:
                    worksheet_data = sheet.worksheet("BiezacaEdycja")
                    worksheet_data.append_row([participant, day, status_key, full_notes, timestamp])
                    
                    worksheet_log = sheet.worksheet("LogWpisow")
                    worksheet_log.append_row([submitter, participant, day, status_key, timestamp])
                    
                    st.session_state.last_submission = {
                        'participant': participant,
                        'day': day,
                        'status_translated': status,
                        'full_notes': full_notes
                    }
                    
                    st.cache_data.clear() 
                else:
                    st.error(_t('form_error_message', lang, "Nie można połączyć się z arkuszem."))
            except Exception as e:
                st.error(_t('form_error_message', lang, e))
            
        st.rerun()