import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
from streamlit_extras.mention import mention
from translations import _t
from config import ALL_POSSIBLE_PARTICIPANTS, SUBMITTER_LIST, EDITIONS
from google_connect import connect_to_google_sheets, upload_file_to_hosting, append_to_sheet_dual
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

    # === 1. KOMUNIKAT SUKCESU (Trwały) ===
    if 'last_submission' in st.session_state and st.session_state.last_submission:
        details = st.session_state.last_submission
        msg = _t('form_success_message', lang, details['participant'], details['day'], details['status_translated'])
        if details.get('file_link'):
            msg += f" | 🖼️ [Zobacz zdjęcie]({details['file_link']})"
        st.success(msg)
        st.session_state.last_submission = None 

    # Funkcja formatująca dla selectbox
    def format_option(option):
        if option is None:
            return _t('form_submitter_placeholder', lang) if "Wybierz" in _t('form_submitter_placeholder', lang) else "Wybierz..."
        return option

    # FORMULARZ
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

        # --- NOWY KOD: KALKULATOR DATY ---
        # Definiujemy daty startowe dla poszczególnych edycji
        # (Możesz to przenieść do config.py w przyszłości, ale tu zadziała od razu)
        edition_start_dates = {
            'november': datetime(2024, 11, 1),
            'december': datetime(2024, 12, 1),
            # 'january': datetime(2025, 1, 1), # Na przyszłość
        }

        start_date = edition_start_dates.get(edition_key)
        
        if start_date:
            # Obliczamy datę: Data Startu + (Numer Etapu - 1 dni)
            # Np. Listopad (Start 1.11) + (Etap 31 - 1 = 30 dni) = 1 Grudnia
            calculated_date = start_date + timedelta(days=day_input - 1)
            
            # Formatowanie nazwy miesiąca po polsku (bo system może mieć angielskie locale)
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
            
            # Wyświetlamy podpowiedź (caption jest mniejszy i szary, idealny do tego celu)
            st.caption(label_text) # st.markdown(label_text) jeśli chcesz większy tekst
        # --- KONIEC NOWEGO KODU ---
        
    st.markdown(f"**{_t('form_status_label', lang)}**")
    status_val = st.radio(
        "Wybierz:", 
        [_t('form_status_pass', lang), _t('form_status_fail', lang), _t('form_status_no_report', lang)],
        key=f"status_{edition_key}",
        label_visibility="collapsed"
    )

    # PRZYCISK ZAPISU
    st.write("")
    try:
        submitted = st.button(_t('form_submit_button', lang), type="primary", use_container_width=True, key=f"btn_{edition_key}")
    except TypeError:
         submitted = st.button(_t('form_submit_button', lang), type="primary", key=f"btn_{edition_key}")
    
    st.markdown("---")
    
    # DODATKI (Konwerter)
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

    # === LOGIKA ZAPISU ===
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
                # Tutaj dodajemy 7. kolumnę (full_notes)
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

    # === 2. OSTATNIE ZGŁOSZENIA (Poprawione i naprawione) ===
    st.markdown("---")
    st.subheader("📋 Ostatnie zgłoszenia (Weryfikacja)" if lang == 'pl' else "📋 Recent Submissions (Verification)")
    st.caption("Tutaj możesz sprawdzić, czy Twój wpis dotarł do systemu." if lang == 'pl' else "Check here if your submission was received.")
        
    if sheet:
        try:
            df_log = load_google_sheet_data(sheet, "LogWpisow")
            
            if not df_log.empty:
                # --- AUTO-NAPRAWA NAGŁÓWKÓW ---
                # Nazywamy tyle kolumn, ile fizycznie przyszło z arkusza
                proper_headers = ['Submitter', 'Participant', 'Day', 'Status', 'Timestamp', 'Edition', 'Notes']
                current_col_count = len(df_log.columns)
                df_log.columns = proper_headers[:current_col_count]
                
                # --- WYMUSZENIE KOLUMNY NOTES ---
                # Jeśli arkusz ma stare dane (np. tylko 6 kolumn), Notes nie istnieje.
                # Dodajemy pustą kolumnę Notes, żeby tabela się nie wywaliła.
                if 'Notes' not in df_log.columns:
                    df_log['Notes'] = "" 

                if 'Timestamp' in df_log.columns:
                    df_log['Timestamp'] = pd.to_datetime(df_log['Timestamp'], errors='coerce')
                    df_log = df_log.sort_values('Timestamp', ascending=False).head(10)
                    df_log['Timestamp'] = df_log['Timestamp'].dt.strftime('%H:%M %d-%m')

                    # Wybieramy kolumny (teraz 'Notes' na pewno istnieje dzięki if powyżej)
                    display_cols = ['Submitter', 'Participant', 'Day', 'Status', 'Notes', 'Timestamp']
                    # Filtrujemy, żeby brać tylko te, które są w df (zabezpieczenie)
                    final_cols = [c for c in display_cols if c in df_log.columns]
                    
                    st.dataframe(
                        df_log[final_cols], 
                        hide_index=True, 
                        width="stretch",  # <--- POPRAWKA OSTRZEŻENIA (zamiast use_container_width)
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

    # === NAJWIĘKSI POMOCNICY (ZAAWANSOWANA TABELA) ===
    st.markdown("---")
    st.subheader(_t('current_stats_top_submitters', lang))

    # Tekst wprowadzający
    st.info(_t('helpers_info_text', lang))

    if sheet:
        try:
            # 1. Ładowanie danych logów (Dla Pomocników)
            df_logs = load_google_sheet_data(sheet, "LogWpisow")
            
            # --- ZMIANA 1: Ograniczenie do ostatnich 200 wpisów (Rolling Window) ---
            if not df_logs.empty:
                # Bierzemy tylko ostatnie 200 wpisów do obliczeń puli P
                df_logs_subset = df_logs.tail(200).copy() 
            else:
                df_logs_subset = pd.DataFrame() # Pusty DataFrame, jeśli brak logów
            
            # --- ZMIANA 2: AGREGACJA TOP 5 Z OFICJALNYCH WYNIKÓW WSZYSTKICH EDYCJI ---
            all_top_leaders = set()
            
            # Iterujemy przez WSZYSTKIE edycje, dla których chcemy liczyć bonus lidera
            leader_bonus_editions = ['november', 'december'] 
            
            # Nazwy kolumn do późniejszego użycia wewnątrz pętli
            part_col = _t('ranking_col_participant', lang)
            
            for ed_key in leader_bonus_editions:
                ed_cfg = EDITIONS.get(ed_key)
                if ed_cfg:
                    ed_sheet_name = ed_cfg['sheet_name']
                    ed_participants_list = ed_cfg['participants']
                    
                    # Ładowanie danych wyników dla danej edycji
                    df_ed_results = load_google_sheet_data(sheet, ed_sheet_name)
                    
                    if not df_ed_results.empty:
                        # Przetwarzamy dane
                        expected_data_cols = ['Participant', 'Day', 'Status', 'Timestamp', 'Notes']
                        current_data_proc, max_day_proc, elimination_map_live = process_raw_data(df_ed_results, lang, expected_data_cols, ed_sheet_name)
                        
                        # 1. Obliczamy OSTATNI OFICJALNY etap (na podstawie rankingu 'live')
                        ranking_live, elimination_map_live = calculate_ranking(current_data_proc, max_day_proc, lang, ed_participants_list, ranking_type='live')
                        complete_stages = find_last_complete_stage(current_data_proc, elimination_map_live, max_day_proc, ed_participants_list)
                        
                        # Używamy ostatniego oficjalnie ukończonego etapu (lub 1 jako fallback)
                        official_stage = complete_stages[-1] if complete_stages else 1
                        
                        # 2. Obliczamy ranking na podstawie OFICJALNYCH wyników (tylko ukończone etapy)
                        ranking_df, _ = calculate_ranking(current_data_proc, official_stage, lang, ed_participants_list, ranking_type='official')
                        
                        if not ranking_df.empty:
                            # Dodajemy Top 5 liderów z TEJ EDYCJI do globalnego zbioru
                            top_5_ed_leaders = ranking_df.head(5)[part_col].tolist()
                            all_top_leaders.update(top_5_ed_leaders)
            # --- KONIEC NOWEJ LOGIKI DLA LIDERÓW ---

            if not df_logs_subset.empty:
                # --- PRZYGOTOWANIE DANYCH (POMOCNIKÓW) ---
                
                # A. Obliczenia Pomocników (na podstawie podzbioru ostatnich 200 wpisów)
                proper_headers = ['Submitter', 'Participant', 'Day', 'Status', 'Timestamp', 'Edition', 'Notes']
                df_logs_subset.columns = proper_headers[:len(df_logs_subset.columns)]
                
                total_entries = len(df_logs_subset)
                helpers_subset = df_logs_subset[df_logs_subset['Submitter'] != 'poprzeczka (Admin)']
                community_entries = len(helpers_subset)
                
                # Procent puli (P)
                P = 0
                if total_entries > 0:
                    P = int((community_entries / total_entries) * 100)
                
                # Pula dla pomocników (80% puli społeczności)
                helper_pool = P * 0.80
                
                # Pula dla liderów (20% puli społeczności)
                leader_pool = P * 0.20
                
                # Zliczanie wpisów per użytkownik
                helper_counts = helpers_subset['Submitter'].value_counts()
                
                # B. Obliczenia Liderów 
                num_leaders = len(all_top_leaders) 
                
                bonus_per_leader = 0
                if num_leaders > 0:
                    bonus_per_leader = leader_pool / num_leaders 
                
                # C. Agregacja Wyników
                rewards_data = []
                
                # Zbieramy wszystkich unikalnych beneficjentów (zarówno pomocnicy jak i globalni liderzy)
                all_beneficiaries = set(helper_counts.index.tolist()) | all_top_leaders 
                
                for user in all_beneficiaries:
                    # Wyliczenie części za pomoc
                    user_entries = helper_counts.get(user, 0)
                    h_share = 0
                    if community_entries > 0:
                        h_share = (user_entries / community_entries) * helper_pool
                    
                    # Wyliczenie części za lidera
                    l_share = bonus_per_leader if user in all_top_leaders else 0
                    
                    # Suma i zaokrąglenie
                    total_raw = h_share + l_share
                    total_rounded = round(total_raw)
                    
                    # Formatowanie opisu
                    details_str = _t('helpers_details_format', lang, h_share, l_share, total_rounded)
                    
                    if total_rounded > 0:
                        rewards_data.append({
                            "Uczestnik": f"@{user}",
                            "Nagroda": f"{total_rounded}%",
                            "Szczegóły wyliczenia": details_str,
                            "_sort_val": total_rounded
                        })
                
                # D. Sortowanie i Wyświetlenie Tabeli
                rewards_data.sort(key=lambda x: x['_sort_val'], reverse=True)
                top_rewards = rewards_data[:7]
                
                # Używamy P do stopki draftu w Generatorze Draftu
                st.session_state['helper_pool_P'] = P 

                if top_rewards:
                    df_display = pd.DataFrame(top_rewards).drop(columns=['_sort_val'])
                    
                    st.dataframe(
                        df_display,
                        width="stretch",
                        hide_index=True,
                        column_config={
                            # Używamy kluczy z translations.py
                            "Uczestnik": st.column_config.TextColumn(_t('helpers_col_participant', lang), width="small"),
                            "Nagroda": st.column_config.TextColumn(_t('helpers_col_reward', lang), width="small"),
                            "Szczegóły wyliczenia": st.column_config.TextColumn(_t('helpers_col_details', lang), width="large"),
                        }
                    )
                    
                    # Stopka z info o puli
                    caption_text = _t('helpers_footer_pool_full', lang, P, community_entries, total_entries - community_entries, total_entries)
                    st.caption(caption_text)
                else:
                    st.info("Brak danych do wyliczenia nagród.")

            else: # Gdy df_logs jest puste
                st.info("Brak wpisów w logu.")


        except Exception as e:
            st.warning(f"Nie udało się pobrać danych do tabeli pomocników: {e}")

    # === GENERATOR DRAFTU (Skrócony w widoku, ale działa tak samo) ===
    st.markdown("---")
    st.header(_t('draft_header', lang, edition_label))
    
    p_nov = EDITIONS.get('november', {}).get('participants', [])
    p_dec = EDITIONS.get('december', {}).get('participants', [])
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
                    
                    # Logika draftu (bez zmian merytorycznych)
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

                        # Pobieramy obliczoną pulę P lub 0 jako fallback
                        helper_pool_pct = st.session_state.get('helper_pool_P', 0)
                        
                        if elim_day:
                            elim_str = w_eliminated.format(elim_day)
                            analysis_part = _t('draft_analysis_eliminated', lang, f"@{selected_participant_for_draft}", elim_str, w_achieved, avg_res, pb_message)
                        else:
                            if pb_message: 
                                # Gratulacje PB (osiągnął więcej niż w historii)
                                analysis_part = _t('draft_analysis_active', lang, f"@{selected_participant_for_draft}", w_chance, w_achieved, avg_res, pb_res, w_missing, diff_to_pb)
                                analysis_part += f"\n\n{pb_message}" # Dodajemy komunikat PB
                            else: 
                                # Standardowa analiza
                                analysis_part = _t('draft_analysis_active', lang, f"@{selected_participant_for_draft}", w_chance, w_achieved, avg_res, pb_res, w_missing, diff_to_pb)
                            
                            # Używamy zmiennej helper_pool_pct w stopce
                            draft_text = f"""{_t('draft_intro', lang, f'@{selected_participant_for_draft}')}\n\n{_t('draft_main_text', lang, official_stage, f'@{selected_participant_for_draft}', current_rank, prev_user, next_user, w_participant, last_reported_day, last_status_text)}\n\n{analysis_part}\n\n{_t('draft_footer', lang, str(helper_pool_pct))}"""
                            st.text_area(_t('draft_copy_label', lang), value=draft_text, height=300)
                    else: st.warning(_t('draft_no_data', lang))
            except Exception as e: st.error(_t('draft_error', lang, str(e)))
