import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
from streamlit_extras.mention import mention
from translations import _t
# === ZMIANA: Importujemy funkcje do zapisu configu ===
from config import ALL_POSSIBLE_PARTICIPANTS, SUBMITTER_LIST, EDITIONS_CONFIG, MONTH_NAMES, save_config_to_json
from google_connect import connect_to_google_sheets, upload_file_to_hosting, append_to_sheet_dual
from page_current_ranking import calculate_ranking, find_last_complete_stage
from data_loader import load_google_sheet_data, process_raw_data, load_historical_data_from_json

def show_submission_form(lang, edition_key="december", is_active=True):
    
    # 1. Pobieramy config
    cfg = EDITIONS_CONFIG.get(edition_key)
    if not cfg:
        st.error("Błąd konfiguracji edycji.")
        return

    # 2. Obliczamy status daty
    today = datetime.now().date()
    start_date = cfg['start_date']
    is_upcoming = start_date > today

    # 3. Pobieramy nazwy
    edition_label = MONTH_NAMES[edition_key][lang]
    sheet_name = cfg['sheet_name']
    participants_list = cfg['participants']

    # Zmienna sterująca wyświetlaniem formularza
    show_form_content = False

    # === LOGIKA STATUSÓW (Góra strony) ===
    
    # PRZYPADEK A: Edycja przyszła
    if is_upcoming:
        st.header(_t('form_header', lang, edition_label))
        start_fmt = start_date.strftime('%d.%m.%Y')
        st.info(f"⏳ {_t('edition_starts_soon', lang, edition_label)}")
        st.markdown(f"📅 Start edycji: **{start_fmt}**")
        st.markdown(_t('join_intro', lang))
        show_form_content = False # Nie pokazujemy formularza, ale kod idzie dalej do Admin Panelu

    # PRZYPADEK B: Edycja zamknięta
    elif not is_active:
        st.header(_t('form_header', lang, edition_label))
        st.error(_t('form_error_edition_closed', lang, edition_label))
        show_form_content = False

    # PRZYPADEK C: Edycja aktywna
    else:
        st.header(_t('form_header', lang, edition_label))
        show_form_content = True

    # ==========================================
    # === WŁAŚCIWY FORMULARZ (Jeśli aktywny) ===
    # ==========================================
    
    sheet = None # Inicjalizacja zmiennej

    if show_form_content:
        # Nawiązujemy połączenie
        sheet = connect_to_google_sheets()
        if not sheet:
            st.error("Błąd krytyczny: Brak połączenia z Google Sheets.")
            return

        users_list = sorted(participants_list)
        submitters_list = sorted(SUBMITTER_LIST)

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
            
            # --- KALKULATOR DATY ---
            calc_start_date = cfg['start_date']
            if not isinstance(calc_start_date, type(datetime.now())):
                calc_start_date = datetime.combine(calc_start_date, datetime.min.time())        
            if calc_start_date:
                calculated_date = calc_start_date + timedelta(days=day_input - 1)
                
                pl_months = {
                    1: "stycznia", 2: "lutego", 3: "marca", 4: "kwietnia", 5: "maja", 6: "czerwca",
                    7: "lipca", 8: "sierpnia", 9: "września", 10: "października", 11: "listopada", 12: "grudnia"
                }
                
                if lang == 'pl':
                    date_str = f"{calculated_date.day} {pl_months[calculated_date.month]}"
                    label_text = f"📅 To jest raport za dzień: **{date_str}**"
                else:
                    date_str = calculated_date.strftime("%d %B")
                    label_text = f"📅 Report for date: **{date_str}**"
                
                st.caption(label_text)

                # --- KOMUNIKAT SUKCESU ---
                if 'last_submission' in st.session_state and st.session_state.last_submission:
                    details = st.session_state.last_submission
                    msg = _t('form_success_message', lang, details['participant'], details['day'], details['status_translated'])
                    if details.get('file_link'):
                        msg += f" | 🖼️ [Zobacz zdjęcie]({details['file_link']})"
                    st.success(msg)
                    st.session_state.last_submission = None

        st.markdown(f"**{_t('form_status_label', lang)}**")
        status_val = st.radio(
            "Wybierz:", 
            [_t('form_status_pass', lang), _t('form_status_fail', lang), _t('form_status_no_report', lang)],
            key=f"status_{edition_key}",
            label_visibility="collapsed"
        )

        st.write("")
        try:
            submitted = st.button(_t('form_submit_button', lang), type="primary", use_container_width=True, key=f"btn_{edition_key}")
        except TypeError:
             submitted = st.button(_t('form_submit_button', lang), type="primary", key=f"btn_{edition_key}")
        
        st.markdown("---")
        
        # KONWERTER
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

        # === LOGIKA ZAPISU DO ARKUSZA ===
        if submitted:
            if not submitter or not participant:
                st.error(_t('form_error_no_participant', lang))
            else:
                st.session_state.submitter_index_plus_one = ([None] + submitters_list).index(submitter)
                
                file_link_text = ""
                if uploaded_file:
                    with st.spinner("Wysyłanie pliku..."):
                        link = upload_file_to_hosting(uploaded_file)
                        if link:
                            file_link_text = link
                        else:
                            file_link_text = "(Błąd uploadu)"
                            st.error("Nie udało się wysłać pliku.")
            
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
                    ws_log.append_row([submitter, participant, day_input, status_key, timestamp, edition_key, full_notes])
                    
                    st.session_state.last_submission = {
                        'participant': participant,
                        'day': day_input,
                        'status_translated': status_val,
                        'full_notes': full_notes,
                        'file_link': file_link_text if "http" in file_link_text else None
                    }
                    st.session_state.last_day_entered = day_input + 1
                    st.cache_data.clear()
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Błąd zapisu: {e}")

        # === OSTATNIE ZGŁOSZENIA ===
        st.markdown("---")
        st.subheader("📋 Ostatnie zgłoszenia (Weryfikacja)" if lang == 'pl' else "📋 Recent Submissions (Verification)")
        st.caption("Tutaj możesz sprawdzić, czy Twój wpis dotarł do systemu." if lang == 'pl' else "Check here if your submission was received.")
            
        if sheet:
            try:
                df_log = load_google_sheet_data(sheet, "LogWpisow")
                
                if not df_log.empty:
                    proper_headers = ['Submitter', 'Participant', 'Day', 'Status', 'Timestamp', 'Edition', 'Notes']
                    current_col_count = len(df_log.columns)
                    df_log.columns = proper_headers[:current_col_count]
                    
                    if 'Notes' not in df_log.columns:
                        df_log['Notes'] = "" 

                    if 'Timestamp' in df_log.columns:
                        df_log['Timestamp'] = pd.to_datetime(df_log['Timestamp'], errors='coerce')
                        df_log = df_log.sort_values('Timestamp', ascending=False).head(10)
                        df_log['Timestamp'] = df_log['Timestamp'].dt.strftime('%H:%M %d-%m')

                        display_cols = ['Submitter', 'Participant', 'Day', 'Status', 'Notes', 'Timestamp']
                        final_cols = [c for c in display_cols if c in df_log.columns]
                        
                        st.dataframe(
                            df_log[final_cols], 
                            hide_index=True, 
                            width="stretch",
                            column_config={
                                "Notes": st.column_config.TextColumn("Notatki / Link", width="medium"),
                                "Timestamp": st.column_config.TextColumn("Czas", width="small")
                            }
                        )
                    else:
                        st.warning("Błąd danych: Nie udało się zidentyfikować kolumny z datą.")
                else:
                    st.info("Brak wpisów." if lang == 'pl' else "No entries yet.")
            except Exception as e:
                st.warning(f"Podgląd niedostępny: {e}")

        # === NAJWIĘKSI POMOCNICY ===
        st.markdown("---")
        st.subheader(_t('current_stats_top_submitters', lang))
        st.info(_t('helpers_info_text', lang))

        if sheet:
            try:
                df_logs = load_google_sheet_data(sheet, "LogWpisow")
                
                if not df_logs.empty:
                    df_logs_subset = df_logs.tail(200).copy() 
                else:
                    df_logs_subset = pd.DataFrame()

                # --- AGREGACJA TOP 5 LIDERÓW ---
                all_top_leaders = set()
                leader_bonus_editions = ['november', 'december'] 
                part_col = _t('ranking_col_participant', lang)
                
                for ed_key in leader_bonus_editions:
                    ed_cfg = EDITIONS_CONFIG.get(ed_key)
                    if ed_cfg:
                        ed_sheet_name = ed_cfg['sheet_name']
                        ed_participants_list = ed_cfg['participants']
                        
                        df_ed_results = load_google_sheet_data(sheet, ed_sheet_name)
                        
                        if not df_ed_results.empty:
                            expected_data_cols = ['Participant', 'Day', 'Status', 'Timestamp', 'Notes']
                            current_data_proc, max_day_proc, elimination_map_live = process_raw_data(df_ed_results, lang, expected_data_cols, ed_sheet_name)
                            
                            ranking_live, elimination_map_live = calculate_ranking(current_data_proc, max_day_proc, lang, ed_participants_list, ranking_type='live')
                            complete_stages = find_last_complete_stage(current_data_proc, elimination_map_live, max_day_proc, ed_participants_list)
                            
                            official_stage = complete_stages[-1] if complete_stages else 1
                            ranking_df, _ = calculate_ranking(current_data_proc, official_stage, lang, ed_participants_list, ranking_type='official')
                            
                            if not ranking_df.empty:
                                top_5_ed_leaders = ranking_df.head(5)[part_col].tolist()
                                all_top_leaders.update(top_5_ed_leaders)
                
                if not df_logs_subset.empty:
                    proper_headers = ['Submitter', 'Participant', 'Day', 'Status', 'Timestamp', 'Edition', 'Notes']
                    df_logs_subset.columns = proper_headers[:len(df_logs_subset.columns)]
                    
                    total_entries = len(df_logs_subset)
                    helpers_subset = df_logs_subset[df_logs_subset['Submitter'] != 'poprzeczka (Admin)']
                    community_entries = len(helpers_subset)
                    
                    P = 0
                    if total_entries > 0:
                        P = int((community_entries / total_entries) * 100)
                    
                    helper_pool = P * 0.80
                    leader_pool = P * 0.20
                    
                    helper_counts = helpers_subset['Submitter'].value_counts()
                    num_leaders = len(all_top_leaders) 
                    
                    bonus_per_leader = 0
                    if num_leaders > 0:
                        bonus_per_leader = leader_pool / num_leaders 
                    
                    rewards_data = []
                    all_beneficiaries = set(helper_counts.index.tolist()) | all_top_leaders 
                    
                    for user in all_beneficiaries:
                        user_entries = helper_counts.get(user, 0)
                        h_share = 0
                        if community_entries > 0:
                            h_share = (user_entries / community_entries) * helper_pool
                        
                        l_share = bonus_per_leader if user in all_top_leaders else 0
                        
                        total_raw = h_share + l_share
                        total_rounded = round(total_raw)
                        
                        details_str = _t('helpers_details_format', lang, h_share, l_share, total_rounded)
                        
                        if total_rounded > 0:
                            rewards_data.append({
                                "Uczestnik": f"@{user}",
                                "Nagroda": f"{total_rounded}%",
                                "Szczegóły wyliczenia": details_str,
                                "_sort_val": total_rounded
                            })
                    
                    rewards_data.sort(key=lambda x: x['_sort_val'], reverse=True)
                    top_rewards = rewards_data[:7]
                    
                    st.session_state['helper_pool_P'] = P 

                    if top_rewards:
                        df_display = pd.DataFrame(top_rewards).drop(columns=['_sort_val'])
                        st.dataframe(
                            df_display,
                            width="stretch",
                            hide_index=True,
                            column_config={
                                "Uczestnik": st.column_config.TextColumn(_t('helpers_col_participant', lang), width="small"),
                                "Nagroda": st.column_config.TextColumn(_t('helpers_col_reward', lang), width="small"),
                                "Szczegóły wyliczenia": st.column_config.TextColumn(_t('helpers_col_details', lang), width="large"),
                            }
                        )
                        caption_text = _t('helpers_footer_pool_full', lang, P, community_entries, total_entries - community_entries, total_entries)
                        st.caption(caption_text)
                    else:
                        st.info("Brak danych do wyliczenia nagród.")
                else: 
                    st.info("Brak wpisów w logu.")

            except Exception as e:
                st.warning(f"Nie udało się pobrać danych do tabeli pomocników: {e}")

        # === GENERATOR DRAFTU ===
        st.markdown("---")
        st.header(_t('draft_header', lang, edition_label))
        
        p_nov = EDITIONS_CONFIG.get('november', {}).get('participants', [])
        p_dec = EDITIONS_CONFIG.get('december', {}).get('participants', [])
        all_participants_draft = sorted(list(set(p_nov + p_dec)))
        
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
                        
                        # Logika językowa
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

                            helper_pool_pct = st.session_state.get('helper_pool_P', 0)
                            
                            if elim_day:
                                elim_str = w_eliminated.format(elim_day)
                                analysis_part = _t('draft_analysis_eliminated', lang, f"@{selected_participant_for_draft}", elim_str, w_achieved, avg_res, pb_message)
                            else:
                                if pb_message: 
                                    analysis_part = _t('draft_analysis_active', lang, f"@{selected_participant_for_draft}", w_chance, w_achieved, avg_res, pb_res, w_missing, diff_to_pb)
                                    analysis_part += f"\n\n{pb_message}" 
                                else: 
                                    analysis_part = _t('draft_analysis_active', lang, f"@{selected_participant_for_draft}", w_chance, w_achieved, avg_res, pb_res, w_missing, diff_to_pb)
                                
                            draft_text = f"""{_t('draft_intro', lang, f'@{selected_participant_for_draft}')}\n\n{_t('draft_main_text', lang, official_stage, f'@{selected_participant_for_draft}', current_rank, prev_user, next_user, w_participant, last_reported_day, last_status_text)}\n\n{analysis_part}\n\n{_t('draft_footer', lang, str(helper_pool_pct))}"""
                            st.text_area(_t('draft_copy_label', lang), value=draft_text, height=300)
                        else:
                            st.warning(_t('draft_no_data', lang))
                except Exception as e:
                    st.error(_t('draft_error', lang, str(e)))

    # =========================================================
    # === PANEL ORGANIZATORA (Widoczny ZAWSZE na dole) ===
    # =========================================================
    st.markdown("---")
    with st.expander("🛠️ Panel Organizatora / Organizer Panel", expanded=False):
        password = st.text_input("Podaj hasło administratora:", type="password", key="admin_pass")
        
        if password == "1234":
            st.success("Dostęp przyznany.")
            
            # Wybór edycji do zarządzania
            # Musimy znaleźć index obecnej edycji na liście kluczy
            all_keys = list(EDITIONS_CONFIG.keys())
            try:
                curr_index = all_keys.index(edition_key)
            except ValueError:
                curr_index = 0

            target_edition = st.selectbox("Wybierz edycję do edycji:", options=all_keys, index=curr_index)
            target_cfg = EDITIONS_CONFIG[target_edition]
            
            st.markdown(f"### Zarządzanie: {MONTH_NAMES[target_edition][lang]}")
            
            # 1. ZARZĄDZANIE UCZESTNIKAMI
            st.subheader("1. Lista Uczestników")
            current_participants = target_cfg['participants']
            st.write(f"Obecnie: {len(current_participants)} uczestników.")
            
            col_add, col_rem = st.columns(2)
            with col_add:
                new_user = st.text_input("Dodaj uczestnika (login Hive):")
                if st.button("Dodaj", key="adm_add"):
                    if new_user and new_user not in current_participants:
                        target_cfg['participants'].append(new_user)
                        if save_config_to_json(EDITIONS_CONFIG):
                            st.success(f"Dodano {new_user}")
                            st.rerun()
                    else:
                        st.warning("Puste pole lub użytkownik już istnieje.")
            
            with col_rem:
                user_to_remove = st.selectbox("Usuń uczestnika:", options=["Wybierz..."] + sorted(current_participants))
                if st.button("Usuń", key="adm_rem"):
                    if user_to_remove != "Wybierz...":
                        target_cfg['participants'].remove(user_to_remove)
                        if save_config_to_json(EDITIONS_CONFIG):
                            st.success(f"Usunięto {user_to_remove}")
                            st.rerun()

            st.divider()

            # 2. STATUS EDYCJI
            st.subheader("2. Status Edycji")
            
            # Zamknięcie edycji
            is_closed = target_cfg.get('is_manually_closed', False)
            st.write(f"Stan obecny: **{'ZAMKNIĘTA' if is_closed else 'OTWARTA'}**")
            
            col_stat1, col_stat2 = st.columns(2)
            with col_stat1:
                if is_closed:
                    if st.button("🔓 OTWÓRZ edycję", type="secondary"):
                        target_cfg['is_manually_closed'] = False
                        save_config_to_json(EDITIONS_CONFIG)
                        st.rerun()
                else:
                    if st.button("🔒 ZAKOŃCZ edycję", type="primary"):
                        target_cfg['is_manually_closed'] = True
                        save_config_to_json(EDITIONS_CONFIG)
                        st.rerun()
            
            st.divider()

            # 3. WIDOCZNOŚĆ W MENU
            st.subheader("3. Widoczność w Menu")
            is_hidden = target_cfg.get('is_hidden', False)
            st.write(f"Widoczność w menu: **{'UKRYTA' if is_hidden else 'WIDOCZNA'}**")
            
            col_vis1, col_vis2 = st.columns(2)
            with col_vis1:
                if is_hidden:
                    if st.button("👁️ POKAŻ w menu"):
                        target_cfg['is_hidden'] = False
                        save_config_to_json(EDITIONS_CONFIG)
                        st.rerun()
                else:
                    if st.button("🙈 UKRYJ z menu"):
                        target_cfg['is_hidden'] = True
                        save_config_to_json(EDITIONS_CONFIG)
                        st.rerun()
            
            with st.expander("Podgląd Configu JSON"):
                st.json(EDITIONS_CONFIG)
                
        elif password:
            st.error("Błędne hasło.")
