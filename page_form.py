import streamlit as st
from datetime import datetime
import pandas as pd
from streamlit_extras.mention import mention
from translations import _t
from config import ALL_POSSIBLE_PARTICIPANTS, SUBMITTER_LIST, GOOGLE_DRIVE_FOLDER_ID, EDITIONS
from google_connect import connect_to_google_sheets, connect_to_google_drive, upload_file_to_drive, append_to_sheet_dual
from page_current_ranking import calculate_ranking, find_last_complete_stage
from data_loader import load_google_sheet_data, process_raw_data, load_historical_data_from_json

def show_submission_form(lang, edition_key="november"):
    # Pobieramy config edycji
    cfg = EDITIONS.get(edition_key, EDITIONS['november'])
    sheet_name = cfg['sheet_name']
    edition_label = cfg['label_' + lang]
    participants_list = cfg['participants']
    
    st.header(_t('form_header', lang, edition_label))
    st.info(_t('form_info', lang, edition_label))
    
    # Nawiązujemy połączenie RAZ na początku funkcji
    sheet = connect_to_google_sheets()
    if not sheet:
        st.error("Błąd krytyczny: Brak połączenia z Google Sheets.")
        return

    users_list = sorted(participants_list)
    submitters_list = sorted(SUBMITTER_LIST)

    # === STANY FORMULARZA (Komunikat o sukcesie) ===
    if 'last_submission' in st.session_state and st.session_state.last_submission:
        details = st.session_state.last_submission
        st.success(_t('form_success_message', lang, details['participant'], details['day'], details['status_translated']))
        st.session_state.last_submission = None 

    # Funkcja formatująca dla selectbox (zastępuje None tekstem)
    def format_option(option):
        if option is None:
            return _t('form_submitter_placeholder', lang) if "Wybierz" in _t('form_submitter_placeholder', lang) else "Wybierz..."
        return option

    # BEZ st.form - formularz jest interaktywny
    col1, col2 = st.columns(2)
    with col1:
        submitter = st.selectbox(
            _t('form_submitter_label', lang),
            options=[None] + submitters_list, 
            index=st.session_state.get('submitter_index_plus_one', 0),
            format_func=lambda x: _t('form_submitter_placeholder', lang) if x is None else x,
            key=f"sub_{edition_key}"
        )
        
        participant = st.selectbox(
            _t('form_participant_label', lang),
            options=[None] + users_list, 
            index=0,
            format_func=lambda x: _t('form_participant_placeholder', lang) if x is None else x,
            key=f"part_{edition_key}"
        )
        
    with col2:
        day_input = st.number_input(
            _t('form_day_label', lang), 
            min_value=1, 
            max_value=60, 
            value=st.session_state.get('last_day_entered', 1),
            step=1,
            key=f"day_{edition_key}"
        )
        
    st.markdown(f"**{_t('form_status_label', lang)}**")
    status_val = st.radio(
        "Wybierz:", 
        [_t('form_status_pass', lang), _t('form_status_fail', lang), _t('form_status_no_report', lang)],
        key=f"status_{edition_key}",
        label_visibility="collapsed"
    )

    # === PRZYCISK ZAPISU ===
    st.write("")
    try:
        submitted = st.button(_t('form_submit_button', lang), type="primary", use_container_width=True, key=f"btn_{edition_key}")
    except TypeError:
         submitted = st.button(_t('form_submit_button', lang), type="primary", key=f"btn_{edition_key}")
    
    st.markdown("---")
    
    # === DODATKI ===
    with st.expander(_t('form_converters_expander', lang), expanded=False):
        st.info(_t('form_converters_warning', lang))
        st.markdown("""
        * **Rower (Outdoor):** Dystans (km) × **550** = Liczba Kroków
        * **E-Rower:** Dystans (km) × **400** = Liczba Kroków
        * **Wędrówka / Spacer (Strava):** Dystans (km) × **1300**
        * **Bieg:** Dystans (km) × **1100-1300**
        * **Inne:** 1 min intensywnego ruchu ≈ **60-100** kroków.
        """)

    notes = st.text_area(_t('form_notes_label', lang), placeholder=_t('form_notes_placeholder', lang), key=f"note_{edition_key}")
    uploaded_file = st.file_uploader(_t('form_upload_label', lang), type=["png", "jpg", "jpeg"], key=f"upl_{edition_key}")

    # Link do folderu publicznego (zawsze widoczny)
    public_folder_url = f"https://drive.google.com/drive/folders/{GOOGLE_DRIVE_FOLDER_ID}" if GOOGLE_DRIVE_FOLDER_ID != "PASTE_YOUR_FOLDER_ID_HERE" else "https://drive.google.com/drive/folders/1b-mUxDmKEUoOyLtTePeb7RaJWGfO_Xre"
    st.link_button(_t('form_upload_link_text', lang), public_folder_url, use_container_width=True)

    # === LOGIKA ZAPISU ===
    if submitted:
        if not submitter or not participant:
            st.error(_t('form_error_no_participant', lang))
        else:
            st.session_state.submitter_index_plus_one = ([None] + submitters_list).index(submitter)
            
            file_link_text = ""
            if uploaded_file:
                # --- DIAGNOSTYKA START ---
                st.info(f"Próba uploadu. ID folderu: {GOOGLE_DRIVE_FOLDER_ID}")
                
                if GOOGLE_DRIVE_FOLDER_ID and GOOGLE_DRIVE_FOLDER_ID != "PASTE_YOUR_FOLDER_ID_HERE":
                    try:
                        drive = connect_to_google_drive()
                        if drive:
                            st.write("Połączono z API Drive...") # Debug
                            link = upload_file_to_drive(drive, uploaded_file, GOOGLE_DRIVE_FOLDER_ID, lang)
                            
                            if link:
                                file_link_text = link
                                st.success(f"Plik wysłany: {link}") # Debug
                            else:
                                file_link_text = "(Błąd uploadu - funkcja zwróciła None)"
                                st.error("Upload nieudany: Funkcja uploadu zwróciła pusty wynik.")
                        else:
                            st.error("Błąd: Nie udało się połączyć z obiektem Drive (connect_to_google_drive zwróciło None).")
                    except Exception as e_upload:
                        st.error(f"KRYTYCZNY BŁĄD PODCZAS UPLOADU: {e_upload}")
                        file_link_text = f"(Wyjątek: {e_upload})"
                    st.warning("ID folderu w configu wygląda na domyślne/puste.")
                    file_link_text = "(Drive nieskonfigurowany)"
                # --- DIAGNOSTYKA KONIEC ---            
            full_notes = f"{notes} | {file_link_text}".strip(" | ")
            timestamp = datetime.now().isoformat()
            
            def map_status(ui_status):
                if ui_status == _t('form_status_pass', lang): return "Zaliczone"
                if ui_status == _t('form_status_fail', lang): return "Niezaliczone"
                return "Brak raportu"

            status_key = map_status(status_val)
            
            try:
                ws = sheet.worksheet(sheet_name)
                ws.append_row([participant, day_input, status_key, full_notes, timestamp])
                
                ws_log = sheet.worksheet("LogWpisow")
                ws_log.append_row([submitter, participant, day_input, status_key, timestamp, edition_key])
                
                st.session_state.last_submission = {
                    'participant': participant,
                    'day': day_input,
                    'status_translated': status_val,
                    'full_notes': full_notes
                }
                st.session_state.last_day_entered = day_input + 1
                st.cache_data.clear()
                st.rerun()
                
            except Exception as e:
                st.error(f"Błąd zapisu: {e}")

    # === NAJWIĘKSI POMOCNICY ===
    st.markdown("---")
    st.subheader(_t('current_stats_top_submitters', lang))
    
    helper_pct_str = "0"
    if sheet:
        try:
            df_raw_logs = load_google_sheet_data(sheet, "LogWpisow")
            if not df_raw_logs.empty:
                df_helpers = df_raw_logs[df_raw_logs['Submitter'] != 'poprzeczka (Admin)']
                total_entries = len(df_raw_logs)
                helper_entries = len(df_helpers)
                admin_entries = total_entries - helper_entries
                
                if total_entries > 0:
                    helper_pct_str = f"{helper_entries / total_entries * 100:.0f}"
                
                all_submitters = df_helpers['Submitter'].value_counts()
                if not all_submitters.empty:
                    cols = st.columns(min(3, len(all_submitters)))
                    for idx, (name, count) in enumerate(all_submitters.items()):
                        with cols[idx % len(cols)]:
                            mention(label=f"**{name}** ({count})", icon="📝", url=f"https://hive.blog/@{name}")
                
                st.caption(_t('current_stats_top_submitters_percentage', lang, float(helper_pct_str), helper_entries, admin_entries))
        except Exception:
            st.info(_t('current_log_empty', lang))

    # === GENERATOR DRAFTU ===
    st.markdown("---")
    st.header(_t('draft_header', lang, edition_label))
    
    all_participants_draft = sorted(list(set(EDITIONS['november']['participants'] + EDITIONS['december']['participants'])))
    selected_participant_for_draft = st.selectbox(
        _t('draft_select_label', lang), 
        options=[None] + all_participants_draft, 
        format_func=lambda x: _t('form_participant_placeholder', lang) if x is None else x,
        key=f"draft_sel_{edition_key}"
    )

    if selected_participant_for_draft:
        with st.spinner(_t('draft_loading', lang)):
            try:
                if sheet:
                    df_raw_data = load_google_sheet_data(sheet, sheet_name)
                    expected_data_cols = ['Participant', 'Day', 'Status', 'Timestamp', 'Notes']
                    current_data, max_day_reported, _ = process_raw_data(df_raw_data, lang, expected_data_cols, sheet_name)
                    
                    ranking_df, elimination_map_live = calculate_ranking(current_data, max_day_reported, lang, participants_list, ranking_type='live')
                    complete_stages = find_last_complete_stage(current_data, elimination_map_live, max_day_reported, participants_list)
                    official_stage = complete_stages[-1] if complete_stages else 1
                    ranking_df, elimination_map_official = calculate_ranking(current_data, official_stage, lang, participants_list, ranking_type='official')
                    df_historical = load_historical_data_from_json()
                    
                    female_users = ['ataraksja', 'asia-pl', 'patif2025']
                    is_female = selected_participant_for_draft in female_users
                    w_participant = _t('word_participant_f', lang) if is_female else _t('word_participant_m', lang)
                    w_chance = _t('word_chance_f', lang) if is_female else _t('word_chance_m', lang)
                    w_eliminated = _t('word_eliminated_f', lang) if is_female else _t('word_eliminated_m', lang)
                    w_achieved = _t('word_achieved_f', lang) if is_female else _t('word_achieved_m', lang)
                    w_missing = _t('word_missing_f', lang) if is_female else _t('word_missing_m', lang)
                    w_broke = _t('word_broke_f', lang) if is_female else _t('word_broke_m', lang)

                    part_col = _t('ranking_col_participant', lang)
                    rank_col = _t('ranking_col_rank', lang)
                    
                    user_row = ranking_df[ranking_df[part_col] == selected_participant_for_draft]
                    
                    if not user_row.empty:
                        current_rank = user_row.iloc[0][rank_col]
                        idx = user_row.index[0]
                        prev_user = f"@{ranking_df.iloc[idx-1][part_col]}" if idx > 0 else ("nikt" if lang == 'pl' else "no one")
                        next_user = f"@{ranking_df.iloc[idx+1][part_col]}" if idx < len(ranking_df) - 1 else ("nikt" if lang == 'pl' else "no one")
                        
                        p_days = current_data.get(selected_participant_for_draft, {})
                        if p_days:
                            last_reported_day = max(p_days.keys())
                            s_raw = p_days[last_reported_day]['status']
                            last_status_text = _t('draft_status_pass', lang) if s_raw == "Zaliczone" else _t('draft_status_fail', lang)
                        else:
                            last_reported_day = 0
                            last_status_text = "Brak danych"
                        
                        elim_day = elimination_map_official.get(selected_participant_for_draft)
                        avg_res, pb_res, diff_to_pb, pb_message = "brak danych", "brak danych", "X", ""
                        
                        if not df_historical.empty:
                            hist_p = df_historical[df_historical['uczestnik'] == selected_participant_for_draft]
                            if not hist_p.empty:
                                avg = hist_p['rezultat_numeric'].mean()
                                pb = hist_p['rezultat_numeric'].max()
                                if pd.notna(avg): avg_res = f"{avg:.0f}"
                                if pd.notna(pb): 
                                    pb_res = f"{pb:.0f}"
                                    current_score = user_row.iloc[0][_t('ranking_col_highest_pass', lang)]
                                    if current_score < pb: diff_to_pb = f"{pb - current_score:.0f}"
                                    else: pb_message = _t('draft_pb_congrats', lang, w_broke, w_participant, current_score)

                        if elim_day:
                            elim_str = w_eliminated.format(elim_day)
                            analysis_part = _t('draft_analysis_eliminated', lang, f"@{selected_participant_for_draft}", elim_str, w_achieved, avg_res, pb_message)
                        else:
                            if pb_message: analysis_part = _t('draft_analysis_eliminated', lang, f"@{selected_participant_for_draft}", w_chance, w_achieved, avg_res, pb_message)
                            else: analysis_part = _t('draft_analysis_active', lang, f"@{selected_participant_for_draft}", w_chance, w_achieved, avg_res, pb_res, w_missing, diff_to_pb)

                        draft_text = f"""{_t('draft_intro', lang, f'@{selected_participant_for_draft}')}\n\n{_t('draft_main_text', lang, official_stage, f'@{selected_participant_for_draft}', current_rank, prev_user, next_user, w_participant, last_reported_day, last_status_text)}\n\n{analysis_part}\n\n{_t('draft_footer', lang, helper_pct_str)}"""
                        st.text_area(_t('draft_copy_label', lang), value=draft_text, height=300)
                    else: st.warning(_t('draft_no_data', lang))
            except Exception as e: st.error(_t('draft_error', lang, str(e)))
