import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
from streamlit_extras.mention import mention
from translations import _t
from config import ALL_POSSIBLE_PARTICIPANTS, SUBMITTER_LIST, EDITIONS_CONFIG, MONTH_NAMES, save_config_to_json
from google_connect import connect_to_google_sheets, upload_file_to_hosting, append_to_sheet_dual
from page_current_ranking import calculate_ranking, find_last_complete_stage
from data_loader import load_google_sheet_data, process_raw_data, load_historical_data_from_json

try:
    from notifications import check_and_send_notifications
except ImportError:
    def check_and_send_notifications(*args, **kwargs): pass


# Uczestnicy którzy preferują język polski
PL_PARTICIPANTS = {"browery", "cezary-io", "marianomariano", "racibo", "sk1920"}


def _get_lang_for_participant(participant, current_lang):
    """Zwraca odpowiedni język dla danego uczestnika."""
    if participant and participant in PL_PARTICIPANTS:
        return 'pl'
    elif participant:
        return 'en'
    return current_lang


# ===========================================================
# === PROFIL UCZESTNIKA ===
# ===========================================================

def show_participant_profile(participant, lang, current_data, max_day_reported,
                              elimination_map, complete_stages, participants_list,
                              df_historical, edition_key, current_edition_day):
    """Wyświetla profil uczestnika."""

    edition_label = MONTH_NAMES[edition_key][lang]

    # --- Ranking oficjalny ---
    official_rank = "?"
    try:
        if complete_stages:
            official_stage = complete_stages[-1]
            ranking_off, _ = calculate_ranking(
                current_data, official_stage, lang, participants_list,
                ranking_type='official'
            )
            part_col = _t('ranking_col_participant', lang)
            rank_col = _t('ranking_col_rank', lang)
            row = ranking_off[ranking_off[part_col] == participant]
            if not row.empty:
                official_rank = int(row.iloc[0][rank_col])
    except Exception:
        pass

    # --- Ranking live (nieoficjalny) ---
    live_rank = "?"
    try:
        ranking_live, _ = calculate_ranking(
            current_data, max_day_reported, lang, participants_list,
            ranking_type='live', complete_stages=complete_stages
        )
        part_col = _t('ranking_col_participant', lang)
        rank_col = _t('ranking_col_rank', lang)
        row = ranking_live[ranking_live[part_col] == participant]
        if not row.empty:
            live_rank = int(row.iloc[0][rank_col])
    except Exception:
        pass

    # --- Dane historyczne (obliczane wcześniej, by użyć w statusach) ---
    wins = 0
    pb_val = None
    pb_edition = "—"
    avg_res_l3 = "—"
    last_edition_result = "—"
    last_edition_rank = "—"
    avg_res_all = "—"
    medals = 0

    if not df_historical.empty and participant in df_historical['uczestnik'].values:
        p_hist = df_historical[df_historical['uczestnik'] == participant]
        wins = int((p_hist['miejsce'] == 1).sum())
        medals = int((p_hist['miejsce'] <= 3).sum())

        if not p_hist['rezultat_numeric'].isnull().all():
            pb_val = int(p_hist['rezultat_numeric'].max())
            pb_row = p_hist[p_hist['rezultat_numeric'] == pb_val].iloc[0]
            pb_edition = str(pb_row.get('miesiac_rok_str', '—'))
            avg_res_all = f"{p_hist['rezultat_numeric'].mean():.1f}"

        # Średnia z ostatnich 3 edycji
        last_3_ed = sorted(df_historical['edycja_nr'].unique())[-3:]
        p_hist_l3 = p_hist[p_hist['edycja_nr'].isin(last_3_ed)]
        if not p_hist_l3['rezultat_numeric'].isnull().all():
            avg_res_l3 = f"{p_hist_l3['rezultat_numeric'].mean():.1f}"

        # Wynik w ostatniej edycji
        last_ed_nr = p_hist['edycja_nr'].max()
        last_ed_row = p_hist[p_hist['edycja_nr'] == last_ed_nr]
        if not last_ed_row['rezultat_numeric'].isnull().all():
            last_result_val = int(last_ed_row['rezultat_numeric'].max())
            last_rank_val = int(last_ed_row['miejsce'].min()) if not last_ed_row['miejsce'].isnull().all() else "?"
            last_edition_result = str(last_result_val)
            last_edition_rank = str(last_rank_val)

    # --- Status: odpadł / komunikaty motywacyjne w oparciu o historię ---
    eliminated_on = elimination_map.get(participant)
    days_data = current_data.get(participant, {})

    # Eliminację pokazujemy TYLKO jeśli uczestnik faktycznie wpisał "Niezaliczone"
    # 3 razy z rzędu. Brak wpisu (uczestnik nie uzupełnił danych) NIE jest
    # traktowany jako porażka na stronie profilu/formularza.
    def _check_real_elimination(days_data, eliminated_on):
        if not eliminated_on:
            return False
        consecutive = 0
        for day in range(1, eliminated_on + 1):
            if day in days_data:
                if days_data[day]["status"] == "Niezaliczone":
                    consecutive += 1
                else:
                    consecutive = 0
            else:
                consecutive = 0  # brak wpisu != porażka
            if consecutive >= 3:
                return True
        return False

    confirmed_eliminated = _check_real_elimination(days_data, eliminated_on)

    if confirmed_eliminated:
        status_text = (f"❌ Odpadł/a w dniu {eliminated_on}" if lang == 'pl'
                       else f"❌ Eliminated on day {eliminated_on}")
        status_color = "error"
    else:
        # Status bezpieczny i zachęcający
        if str(last_edition_rank).isdigit() and int(last_edition_rank) <= 5:
            status_text = (f"🔥 Czy powtórzy swoje świetne {last_edition_rank}. miejsce z ostatniej edycji?" if lang == 'pl'
                           else f"🔥 Will they repeat their amazing {last_edition_rank}. place from the last edition?")
        elif pb_val is not None:
            status_text = (f"💪 Walczy! Zobaczymy, czy w tej edycji przebije swój życiowy wynik: {pb_val} etapów." if lang == 'pl'
                           else f"💪 Fighting! Let's see if they beat their PB of {pb_val} stages.")
        else:
            status_text = ("✅ Zgłoszony do gry! Trzymamy kciuki za kolejne etapy." if lang == 'pl'
                           else "✅ In the game! Fingers crossed for the upcoming stages.")
        status_color = "success"

    # --- Wszystkie dni od początku edycji ---
    # Ikony są teraz generowane do BIEŻĄCEGO DNIA EDYCJI zamiast 'max_day_reported'
    all_days_icons = []
    for day in range(1, current_edition_day + 1):
        if confirmed_eliminated and day > eliminated_on:
            all_days_icons.append("⬛")
        elif day in days_data:
            s = days_data[day].get('status', '')
            if s == 'Zaliczone':
                all_days_icons.append('✅')
            elif s == 'Niezaliczone':
                all_days_icons.append('❌')
            else:
                all_days_icons.append('⬜')
        else:
            all_days_icons.append('❓')

    # Grupuj po 10 dni dla czytelności
    all_days_str = ""
    for i, icon in enumerate(all_days_icons):
        if i > 0 and i % 10 == 0:
            all_days_str += "\n"
        all_days_str += icon


    # === WYŚWIETLANIE ===
    with st.container(border=True):

        # Nagłówek z linkiem
        col_name, col_link = st.columns([0.8, 0.2])
        with col_name:
            st.subheader(f"👤 {participant} — {edition_label}")
        with col_link:
            st.link_button(
                f"Hive\n@{participant}",
                f"https://ecency.com/@{participant}/posts",
                use_container_width=True
            )

        # Status
        if status_color == "error":
            st.error(status_text)
        elif status_color == "warning":
            st.warning(status_text)
        else:
            st.success(status_text)

        # Metryki
        col_a, col_b, col_c = st.columns(3)

        with col_a:
            # Usunięto znaki #
            rank_display = f"{official_rank} / {live_rank}*"
            st.metric("📍 " + ("Miejsce" if lang == 'pl' else "Rank"), rank_display)
            st.caption(
                "oficjalny / live*" if lang == 'pl'
                else "official / live*"
            )

        with col_b:
            st.metric("🥇 " + ("Wygrane" if lang == 'pl' else "Wins"), wins)

        with col_c:
            pb_display = str(pb_val) if pb_val is not None else "—"
            st.metric("🏆 " + ("Rekord życiowy" if lang == 'pl' else "Personal best"), pb_display)
            if pb_val is not None:
                st.caption(f"📅 {pb_edition}")

        # Wyjaśnienie live*
        if lang == 'pl':
            st.caption(
                "\\* Live — jak mierzenie czasu maratonu gdy jedni są po 5 km, "
                "a inni dopiero startują. Wiarygodny jest ranking oficjalny."
            )
        else:
            st.caption(
                "\\* Live — like measuring marathon times when some runners are at km 5 "
                "while others just started. Only the official rank is reliable."
            )

        # Wszystkie dni - przeniesione zaraz pod profil
        st.markdown("---")
        if lang == 'pl':
            st.caption(f"**Wszystkie dni tej edycji** (dzień 1 → {current_edition_day}):")
        else:
            st.caption(f"**All days this edition** (day 1 → {current_edition_day}):")
        st.text(all_days_str)
        st.caption("✅ Zaliczone  ❌ Niezaliczone  ⬜ Brak raportu  ❓ Brak danych  ⬛ Po odpadnięciu"
                   if lang == 'pl' else
                   "✅ Passed  ❌ Failed  ⬜ No report  ❓ No data  ⬛ After elimination")

        # Forma - przeniesiona na sam dół (pod wszystkie dni)
        st.markdown("---")
        if lang == 'pl':
            st.markdown("**📈 Forma**")
            st.markdown(
                f"- Ostatnia edycja: najwyższy zaliczony etap **{last_edition_result}**, "
                f"miejsce w klasyfikacji końcowej **{last_edition_rank}**"
            )
            st.markdown(f"- Średni najwyższy zaliczony etap z ostatnich 3 edycji: **{avg_res_l3}**")
        else:
            st.markdown("**📈 Form**")
            st.markdown(
                f"- Last edition: highest passed stage **{last_edition_result}**, "
                f"final position in standings **{last_edition_rank}**"
            )
            st.markdown(f"- Average highest stage over last 3 editions: **{avg_res_l3}**")

        # Historia — zwijana
        with st.expander("📊 " + ("Historia wyników" if lang == 'pl' else "Historical stats")):
            hcol1, hcol2, hcol3 = st.columns(3)
            with hcol1:
                st.metric("🏅 " + ("Medale" if lang == 'pl' else "Medals"), medals)
            with hcol2:
                st.metric("📊 " + ("Śr. wynik ogółem" if lang == 'pl' else "Avg result all"), avg_res_all)
            with hcol3:
                st.metric("📊 " + ("Śr. ost. 3 edycje" if lang == 'pl' else "Avg last 3"), avg_res_l3)


# ===========================================================
# === GŁÓWNA FUNKCJA ===
# ===========================================================

def show_submission_form(lang, edition_key="december", is_active=True):

    cfg = EDITIONS_CONFIG.get(edition_key)
    if not cfg:
        st.error("Błąd konfiguracji edycji.")
        return

    today = datetime.now().date()
    start_date = cfg['start_date']
    
    # Przeliczenie dla bieżącego dnia
    calc_start_date = start_date
    if isinstance(calc_start_date, datetime):
        calc_start_date = calc_start_date.date()
    current_edition_day = (today - calc_start_date).days + 1
    if current_edition_day < 1:
        current_edition_day = 1

    is_upcoming = start_date > today

    edition_label = MONTH_NAMES[edition_key][lang]
    sheet_name = cfg['sheet_name']
    participants_list = cfg['participants']

    # === WYBÓR UCZESTNIKA — na samej górze, steruje językiem ===
    users_list = sorted(participants_list)
    submitters_list = sorted(SUBMITTER_LIST)

    if lang == 'pl':
        select_label = "👤 Wybierz uczestnika:"
        select_placeholder = "Wybierz..."
    else:
        select_label = "👤 Select participant:"
        select_placeholder = "Select..."

    # Dodanie poprzeczki jako opcji do wyboru
    options_list = [None, "poprzeczka (admin)"] + users_list

    selected_participant = st.selectbox(
        select_label,
        options=options_list,
        index=0,
        format_func=lambda x: select_placeholder if x is None else x,
        key=f"profile_participant_{edition_key}"
    )

    # Globalna aktualizacja języka i wymuszenie odświeżenia (rerun) by cały interfejs zassał zmianę
    current_app_lang = st.session_state.get('lang', lang)
    effective_lang = _get_lang_for_participant(selected_participant, current_app_lang)
    
    if selected_participant and effective_lang != current_app_lang:
        st.session_state['lang'] = effective_lang
        st.rerun()

    edition_label = MONTH_NAMES[edition_key][effective_lang]

    if effective_lang == 'pl':
        st.header(f"👤 Profil i Formularz — {edition_label}")
    else:
        st.header(f"👤 Profile & Form — {edition_label}")

    st.markdown("---")

    # === PRZYPADEK A: Edycja przyszła ===
    if is_upcoming:
        start_fmt = start_date.strftime('%d.%m.%Y')
        st.info(f"⏳ {_t('edition_starts_soon', effective_lang, edition_label)}")
        st.markdown(f"📅 Start: **{start_fmt}**")
        st.markdown(_t('join_intro', effective_lang))
        _show_organizer_panel(effective_lang, edition_key, sheet=None)
        return

    # === PRZYPADEK B: Edycja zamknięta ===
    if not is_active:
        st.error(_t('form_error_edition_closed', effective_lang, edition_label))
        _show_organizer_panel(effective_lang, edition_key, sheet=None)
        return

    # === PRZYPADEK C: Aktywna — ładujemy dane ===
    sheet = connect_to_google_sheets()
    if not sheet:
        st.error("Błąd krytyczny: Brak połączenia z Google Sheets.")
        return

    current_data = {}
    max_day_reported = 0
    elimination_map = {}
    complete_stages = []
    df_historical = load_historical_data_from_json()

    try:
        df_raw = load_google_sheet_data(sheet, sheet_name)
        if not df_raw.empty:
            expected_cols = ['Participant', 'Day', 'Status', 'Timestamp', 'Notes']
            current_data, max_day_reported, _ = process_raw_data(df_raw, effective_lang, expected_cols, sheet_name)
            elim_temp = {}
            complete_stages = find_last_complete_stage(current_data, elim_temp, max_day_reported, participants_list)
            _, elimination_map = calculate_ranking(
                current_data, max_day_reported, effective_lang, participants_list,
                ranking_type='live', complete_stages=complete_stages
            )
    except Exception as e:
        st.warning(f"Nie udało się załadować danych edycji: {e}")

    # === PROFIL ===
    if selected_participant and selected_participant != "poprzeczka (admin)" and current_edition_day > 0:
        show_participant_profile(
            participant=selected_participant,
            lang=effective_lang,
            current_data=current_data,
            max_day_reported=max_day_reported,
            elimination_map=elimination_map,
            complete_stages=complete_stages,
            participants_list=participants_list,
            df_historical=df_historical,
            edition_key=edition_key,
            current_edition_day=current_edition_day
        )
        st.markdown("---")
    elif selected_participant:
        if selected_participant != "poprzeczka (admin)":
            st.info("Brak danych dla tej edycji." if effective_lang == 'pl' else "No data for this edition yet.")
        st.markdown("---")

    # ==========================================
    # === FORMULARZ ===
    # ==========================================
    if effective_lang == 'pl':
        st.subheader("📝 Wpisz wynik")
    else:
        st.subheader("📝 Enter result")

    # Informacja o formularzu i nicku
    if selected_participant:
        st.info(f"👤 Formularz dotyczy wyników uczestnika: **{selected_participant}**" if effective_lang == 'pl' 
                else f"👤 This form is for the participant: **{selected_participant}**")

    # Uczestnik = wybrany na górze, submitter = ten sam (chyba że admin)
    participant = selected_participant
    is_admin = st.session_state.get('submitter_is_admin', False)
    
    # Zmieniony tekst Toggle'a
    admin_toggle_label = ("Chcę wprowadzić dane za innego uczestnika - włącz tę opcję" if effective_lang == 'pl'
                          else "I want to enter data for another participant - enable this option")
                          
    is_admin = st.checkbox(admin_toggle_label, value=is_admin, key=f"admin_toggle_{edition_key}")
    st.session_state['submitter_is_admin'] = is_admin

    if is_admin:
        col_adm1, col_adm2 = st.columns(2)
        with col_adm1:
            default_participant_index = 0
            if selected_participant and selected_participant in users_list:
                default_participant_index = users_list.index(selected_participant) + 1
            participant = st.selectbox(
                _t('form_participant_label', effective_lang),
                options=[None] + users_list,
                index=default_participant_index,
                format_func=lambda x: _t('form_participant_placeholder', effective_lang) if x is None else x,
                key=f"part_{edition_key}"
            )
        with col_adm2:
            submitter = st.selectbox(
                _t('form_submitter_label', effective_lang),
                options=[None] + submitters_list,
                index=st.session_state.get('submitter_index_plus_one', 0),
                format_func=lambda x: _t('form_submitter_placeholder', effective_lang) if x is None else x,
                key=f"sub_{edition_key}"
            )
    else:
        submitter = selected_participant
        if not participant:
            st.info("👆 " + ("Wybierz uczestnika na górze strony." if effective_lang == 'pl'
                               else "Select a participant at the top of the page."))

    col1, col2 = st.columns([1, 1])
    with col2:
        day_input = st.number_input(
            _t('form_day_label', effective_lang),
            min_value=1,
            max_value=60,
            value=st.session_state.get('last_day_entered', 1),
            step=1,
            key=f"day_{edition_key}"
        )

        # Kalkulator daty
        if calc_start_date:
            calculated_date = calc_start_date + timedelta(days=day_input - 1)
            pl_months = {
                1: "stycznia", 2: "lutego", 3: "marca", 4: "kwietnia", 5: "maja", 6: "czerwca",
                7: "lipca", 8: "sierpnia", 9: "września", 10: "października", 11: "listopada", 12: "grudnia"
            }
            if effective_lang == 'pl':
                date_str = f"{calculated_date.day} {pl_months[calculated_date.month]}"
                label_text = f"📅 To jest raport za dzień: **{date_str}**"
            else:
                date_str = calculated_date.strftime("%d %B")
                label_text = f"📅 Report for date: **{date_str}**"
            st.caption(label_text)

            if participant and participant != "poprzeczka (admin)":
                hive_url = f"https://ecency.com/@{participant}/posts"
                if effective_lang == 'pl':
                    st.caption(f"👤 Uczestnik: [@{participant}]({hive_url})")
                else:
                    st.caption(f"👤 Participant: [@{participant}]({hive_url})")

            if 'last_submission' in st.session_state and st.session_state.last_submission:
                details = st.session_state.last_submission
                msg = _t('form_success_message', effective_lang, details['participant'], details['day'], details['status_translated'])
                if details.get('file_link'):
                    msg += f" | 🖼️ [Zobacz zdjęcie]({details['file_link']})"
                st.success(msg)
                st.session_state.last_submission = None

    st.markdown(f"**{_t('form_status_label', effective_lang)}**")
    status_val = st.radio(
        "Wybierz:",
        [_t('form_status_pass', effective_lang), _t('form_status_fail', effective_lang), _t('form_status_no_report', effective_lang)],
        key=f"status_{edition_key}",
        label_visibility="collapsed"
    )

    st.write("")
    is_saving = st.session_state.get(f"saving_{edition_key}", False)
    btn_label = ("⏳ Zapisywanie, poczekaj chwilę..." if effective_lang == 'pl' else "⏳ Saving, please wait...") if is_saving else _t('form_submit_button', effective_lang)
    try:
        submitted = st.button(btn_label, type="primary", use_container_width=True, key=f"btn_{edition_key}", disabled=is_saving)
    except TypeError:
        submitted = st.button(btn_label, type="primary", key=f"btn_{edition_key}", disabled=is_saving)

    st.markdown("---")

    with st.expander(_t('form_converters_expander', effective_lang), expanded=False):
        st.info(_t('form_converters_warning', effective_lang))
        st.markdown("""
        * **Rower (Outdoor):** Dystans (km) × **550** = Liczba Kroków
        * **E-Rower:** Dystans (km) × **400** = Liczba Kroków
        * **Wędrówka / Spacer (Strava):** Dystans (km) × **1300**
        * **Bieg:** Dystans (km) × **1100-1300**
        * **Inne:** 1 min intensywnego ruchu ≈ **60-100** kroków.
        """)

    notes = st.text_area(_t('form_notes_label', effective_lang), placeholder=_t('form_notes_placeholder', effective_lang), key=f"note_{edition_key}")
    uploaded_file = st.file_uploader(_t('form_upload_label', effective_lang), type=["png", "jpg", "jpeg"], key=f"upl_{edition_key}")

    # === ZAPIS ===
    if submitted:
        st.session_state[f"saving_{edition_key}"] = True
        if not submitter or not participant:
            st.error(_t('form_error_no_participant', effective_lang))
            st.session_state[f"saving_{edition_key}"] = False
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
                if ui_status == _t('form_status_pass', effective_lang): return "Zaliczone"
                if ui_status == _t('form_status_fail', effective_lang): return "Niezaliczone"
                return "Brak raportu"

            status_key = map_status(status_val)

            try:
                ws = sheet.worksheet(sheet_name)
                ws.append_row([participant, day_input, status_key, full_notes, timestamp])
                ws_log = sheet.worksheet("LogWpisow")
                ws_log.append_row([submitter, participant, day_input, status_key, timestamp, edition_key, full_notes])
                with st.spinner("📧 Sprawdzam powiadomienia..."):
                    check_and_send_notifications(
                        conn=sheet,
                        edition_key=edition_key,
                        current_user=participant,
                        current_day=day_input,
                        current_status=status_key
                    )
                st.session_state.last_submission = {
                    'participant': participant,
                    'day': day_input,
                    'status_translated': status_val,
                    'full_notes': full_notes,
                    'file_link': file_link_text if "http" in file_link_text else None
                }
                st.session_state.last_day_entered = day_input + 1
                st.session_state[f"saving_{edition_key}"] = False
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.session_state[f"saving_{edition_key}"] = False
                st.error(f"Błąd zapisu: {e}")

    # === OSTATNIE ZGŁOSZENIA ===
    st.markdown("---")
    st.subheader("📋 Ostatnie zgłoszenia (Weryfikacja)" if effective_lang == 'pl' else "📋 Recent Submissions (Verification)")
    st.caption("Tutaj możesz sprawdzić, czy Twój wpis dotarł do systemu." if effective_lang == 'pl' else "Check here if your submission was received.")

    try:
        df_log = load_google_sheet_data(sheet, "LogWpisow")
        if not df_log.empty:
            proper_headers = ['Submitter', 'Participant', 'Day', 'Status', 'Timestamp', 'Edition', 'Notes']
            df_log.columns = proper_headers[:len(df_log.columns)]
            if 'Notes' not in df_log.columns:
                df_log['Notes'] = ""
            if 'Timestamp' in df_log.columns:
                df_log['Timestamp'] = pd.to_datetime(df_log['Timestamp'], errors='coerce')
                df_log = df_log.sort_values('Timestamp', ascending=False).head(10)
                df_log['Timestamp'] = df_log['Timestamp'].dt.strftime('%H:%M %d-%m')
                display_cols = ['Submitter', 'Participant', 'Day', 'Status', 'Notes', 'Timestamp']
                final_cols = [c for c in display_cols if c in df_log.columns]
                st.dataframe(df_log[final_cols], hide_index=True, width="stretch",
                             column_config={
                                 "Notes": st.column_config.TextColumn("Notatki / Link", width="medium"),
                                 "Timestamp": st.column_config.TextColumn("Czas", width="small")
                             })
        else:
            st.info("Brak wpisów." if effective_lang == 'pl' else "No entries yet.")
    except Exception as e:
        st.warning(f"Podgląd niedostępny: {e}")

    # === NAJWIĘKSI POMOCNICY ===
    st.markdown("---")
    st.subheader(_t('current_stats_top_submitters', effective_lang))

    # Wyjaśnienie co oznacza liderowanie
    if effective_lang == 'pl':
        st.caption(
            "Liderowanie = obecni liderzy w oficjalnej klasyfikacji bieżącej edycji "
            "oraz medaliści (miejsca 1-3) ostatniej zakończonej edycji."
        )
    else:
        st.caption(
            "Leading = current leaders in the official ranking of this edition "
            "and medallists (places 1-3) from the last finished edition."
        )

    try:
        df_logs = load_google_sheet_data(sheet, "LogWpisow")
        if not df_logs.empty:
            proper_headers = ['Submitter', 'Participant', 'Day', 'Status', 'Timestamp', 'Edition', 'Notes']
            df_logs.columns = proper_headers[:len(df_logs.columns)]

        if effective_lang == 'pl':
            date_label = "📅 Obliczaj pomoc od daty:"
            date_help = "Wkłady przed tą datą nie będą uwzględniane przy liczeniu pomocy."
        else:
            date_label = "📅 Count contributions from date:"
            date_help = "Contributions before this date won't be counted."

        help_from_date = st.date_input(
            date_label,
            value=cfg.get('start_date', datetime.now().date()),
            help=date_help,
            key=f"help_date_{edition_key}"
        )

        total_entries = 0
        community_entries = 0
        helper_counts = pd.Series(dtype=int)

        if not df_logs.empty and 'Timestamp' in df_logs.columns:
            df_logs['Timestamp_parsed'] = pd.to_datetime(df_logs['Timestamp'], errors='coerce')
            help_from_dt = datetime.combine(help_from_date, datetime.min.time())
            df_logs_filtered = df_logs[df_logs['Timestamp_parsed'] >= help_from_dt].copy()
            total_entries = len(df_logs_filtered)
            helpers_subset = df_logs_filtered[df_logs_filtered['Submitter'] != 'poprzeczka (Admin)']
            community_entries = len(helpers_subset)
            helper_counts = helpers_subset['Submitter'].value_counts()

        P = int((community_entries / total_entries) * 100) if total_entries > 0 else 0
        st.session_state['helper_pool_P'] = P
        helper_pool = P * 0.80
        leader_pool = P * 0.20

        all_leaders = set()
        part_col = _t('ranking_col_participant', effective_lang)
        rank_col = _t('ranking_col_rank', effective_lang)

        try:
            df_ed_results = load_google_sheet_data(sheet, sheet_name)
            if not df_ed_results.empty:
                expected_data_cols = ['Participant', 'Day', 'Status', 'Timestamp', 'Notes']
                current_data_proc, max_day_proc, _ = process_raw_data(df_ed_results, effective_lang, expected_data_cols, sheet_name)
                ranking_live2, elim_map_live = calculate_ranking(current_data_proc, max_day_proc, effective_lang, participants_list, ranking_type='live')
                complete_stages_curr = find_last_complete_stage(current_data_proc, elim_map_live, max_day_proc, participants_list)
                if complete_stages_curr:
                    ranking_official2, _ = calculate_ranking(current_data_proc, complete_stages_curr[-1], effective_lang, participants_list, ranking_type='official')
                    if not ranking_official2.empty:
                        min_rank = ranking_official2[rank_col].min()
                        all_leaders.update(ranking_official2[ranking_official2[rank_col] == min_rank][part_col].tolist())
        except Exception:
            pass

        df_hist_r = load_historical_data_from_json()
        if not df_hist_r.empty:
            all_editions_sorted = sorted(df_hist_r['edycja_nr'].unique())
            if all_editions_sorted:
                last_ed_df = df_hist_r[df_hist_r['edycja_nr'] == all_editions_sorted[-1]]
                all_leaders.update(last_ed_df[last_ed_df['miejsce'] <= 3]['uczestnik'].tolist())

        num_leaders = len(all_leaders)
        bonus_per_leader = (leader_pool / num_leaders) if num_leaders > 0 else 0

        rewards_data = []
        for user in set(helper_counts.index.tolist()) | all_leaders:
            user_entries = helper_counts.get(user, 0)
            h_share = (user_entries / community_entries) * helper_pool if community_entries > 0 else 0
            l_share = bonus_per_leader if user in all_leaders else 0
            total_raw = h_share + l_share
            total_rounded = round(total_raw)
            if total_rounded > 0 or h_share > 0 or l_share > 0:
                details_str = (f"pomoc {h_share:.1f}%, liderowanie +{l_share:.1f}%. Razem ≈ {total_rounded}%"
                               if effective_lang == 'pl' else
                               f"help {h_share:.1f}%, leading +{l_share:.1f}%. Total ≈ {total_rounded}%")
                rewards_data.append({
                    "Uczestnik": f"@{user}",
                    "Nagroda": f"{total_rounded}%",
                    "Szczegóły wyliczenia": details_str,
                    "_sort_val": total_raw
                })

        rewards_data.sort(key=lambda x: x['_sort_val'], reverse=True)
        top_rewards = rewards_data[:7]

        if top_rewards:
            df_display = pd.DataFrame(top_rewards).drop(columns=['_sort_val'])
            st.dataframe(df_display, width="stretch", hide_index=True,
                         column_config={
                             "Uczestnik": st.column_config.TextColumn(_t('helpers_col_participant', effective_lang), width="small"),
                             "Nagroda": st.column_config.TextColumn(_t('helpers_col_reward', effective_lang), width="small"),
                             "Szczegóły wyliczenia": st.column_config.TextColumn(_t('helpers_col_details', effective_lang), width="large"),
                         })
            admin_entries = total_entries - community_entries
            if effective_lang == 'pl':
                st.caption(
                    f"Pula nagród: **{P}%** (społeczność wprowadziła {community_entries} z {total_entries} wpisów, "
                    f"admin {admin_entries}). Podział: 80% za pomoc, 20% za liderowanie. Liderzy: {num_leaders} os."
                )
            else:
                st.caption(
                    f"Reward pool: **{P}%** (community entered {community_entries} of {total_entries} entries, "
                    f"admin {admin_entries}). Split: 80% help, 20% leading. Leaders: {num_leaders}."
                )
        else:
            st.info("Brak danych do wyliczenia nagród." if effective_lang == 'pl' else "No data to calculate rewards.")

    except Exception as e:
        st.warning(f"Nie udało się pobrać danych do tabeli pomocników: {e}")

    # === PANEL ORGANIZATORA ===
    _show_organizer_panel(effective_lang, edition_key, sheet)


# ===========================================================
# === PANEL ORGANIZATORA ===
# ===========================================================

def _show_organizer_panel(lang, edition_key, sheet):
    st.markdown("---")
    with st.expander("🛠️ Panel Organizatora / Organizer Panel", expanded=False):
        password = st.text_input("Podaj hasło administratora:", type="password", key="admin_pass")

        if password == "1234":
            st.success("Dostęp przyznany.")

            all_keys = list(EDITIONS_CONFIG.keys())
            try:
                curr_index = all_keys.index(edition_key)
            except ValueError:
                curr_index = 0

            target_edition = st.selectbox("Wybierz edycję do edycji:", options=all_keys, index=curr_index)
            target_cfg = EDITIONS_CONFIG[target_edition]
            st.markdown(f"### Zarządzanie: {MONTH_NAMES[target_edition][lang]}")

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
            st.subheader("2. Status Edycji")
            is_closed = target_cfg.get('is_manually_closed', False)
            st.write(f"Stan obecny: **{'ZAMKNIĘTA' if is_closed else 'OTWARTA'}**")

            col_stat1, _ = st.columns(2)
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
            st.subheader("3. Widoczność w Menu")
            is_hidden = target_cfg.get('is_hidden', False)
            st.write(f"Widoczność w menu: **{'UKRYTA' if is_hidden else 'WIDOCZNA'}**")

            col_vis1, _ = st.columns(2)
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

            st.divider()
            st.subheader("5. Powiadomienia")
            if st.button("🔄 Sprawdź i wyślij newsletter"):
                try:
                    check_and_send_notifications(None, target_edition, "Admin", 0, "Manual")
                    st.success("Wywołano procedurę. Sprawdź okno DEBUG powyżej.")
                except Exception as e:
                    st.error(f"Błąd: {e}")
