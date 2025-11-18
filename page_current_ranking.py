import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import time
import numpy as np
from streamlit_extras.mention import mention
from translations import _t
from config import CURRENT_PARTICIPANTS
from google_connect import connect_to_google_sheets
from data_loader import load_google_sheet_data, load_historical_data_from_json, process_raw_data

# === Funkcje Pomocnicze dla Rankingu Bieżącej Edycji ===

def calculate_ranking(data, max_day_reported, lang, ranking_type='live'):
    """Oblicza ranking na podstawie zasad gry."""
    ranking_data = []
    elimination_map = {} 

    for participant in CURRENT_PARTICIPANTS:
        days_data = data.get(participant, {})
        failed_stages = []
        completed_stages = []
        consecutive_fails = 0
        eliminated_on_day = None
        
        for day in range(1, max_day_reported + 1):
            if eliminated_on_day: 
                break
            
            if day in days_data:
                status = days_data[day]["status"]
                
                if status == "Zaliczone":
                    completed_stages.append(day)
                    consecutive_fails = 0 
                else: 
                    failed_stages.append(day)
                    consecutive_fails += 1
            else:
                failed_stages.append(day)
                consecutive_fails += 1
            
            if consecutive_fails >= 3:
                eliminated_on_day = day
                break 

        highest_completed = max(completed_stages) if completed_stages else 0
        status_text = _t('ranking_status_eliminated', lang, eliminated_on_day) if eliminated_on_day else _t('ranking_status_active', lang)
        
        def get_failure_tuple(p_failures, p_highest):
            start_day = max(p_highest, max_day_reported) if not eliminated_on_day else p_highest
            if eliminated_on_day:
                start_day = eliminated_on_day
            return tuple(1 if d in p_failures else 0 for d in range(start_day, 0, -1))

        if ranking_type == 'live':
            failed_col_key = 'ranking_col_failed_list_live'
            failed_stages_str = ", ".join(map(str, sorted(failed_stages)[:10])) + ("..." if len(failed_stages) > 10 else "")
        else: # 'official'
            failed_col_key = 'ranking_col_failed_list_official'
            failed_stages_str = ", ".join(map(str, sorted(failed_stages)))

        ranking_data.append({
            _t('ranking_col_participant', lang): participant,
            _t('ranking_col_highest_pass', lang): highest_completed,
            "sort_key_failure_tuple": get_failure_tuple(failed_stages, highest_completed),
            _t('ranking_col_status', lang): status_text,
            _t(failed_col_key, lang): failed_stages_str 
        })
        elimination_map[participant] = eliminated_on_day 
    
    def sort_key(entry):
        return (
            -entry[_t('ranking_col_highest_pass', lang)], 
            entry["sort_key_failure_tuple"]               
        )

    ranking_data.sort(key=sort_key)
    
    rank_col_name = _t('ranking_col_rank', lang)
    for i, entry in enumerate(ranking_data):
        current_sort_key = (
            entry[_t('ranking_col_highest_pass', lang)], 
            entry["sort_key_failure_tuple"]
        )
        
        if i > 0 and current_sort_key == last_sort_key:
            entry[rank_col_name] = ranking_data[i-1][rank_col_name] 
        else:
            entry[rank_col_name] = i + 1 
        
        last_sort_key = current_sort_key
    
    df_ranking = pd.DataFrame(ranking_data)
    
    if not df_ranking.empty:
        df_ranking[rank_col_name] = df_ranking[rank_col_name].astype(int)
    
    if ranking_type == 'live':
        failed_col_name = _t('ranking_col_failed_list_live', lang)
    else:
        failed_col_name = _t('ranking_col_failed_list_official', lang)
    
    # Sprawdzenie, czy kolumna istnieje przed próbą jej wybrania
    cols_to_return = [
        rank_col_name, 
        _t('ranking_col_participant', lang), 
        _t('ranking_col_highest_pass', lang), 
        _t('ranking_col_status', lang)
    ]
    if failed_col_name in df_ranking.columns:
        cols_to_return.append(failed_col_name)
    
    return df_ranking[cols_to_return], elimination_map


def calculate_current_stats(data, max_day, lang):
    """Oblicza najdłuższe serie zaliczeń (niekoniecznie aktywne)."""
    streaks = []
    for participant in CURRENT_PARTICIPANTS:
        days_data = data.get(participant, {})
        current_streak = 0
        max_streak = 0
        
        for day in range(1, max_day + 1):
            if day in days_data and days_data[day]["status"] == "Zaliczone":
                current_streak += 1
            else:
                max_streak = max(max_streak, current_streak)
                current_streak = 0
        max_streak = max(max_streak, current_streak) 
        
        streaks.append({"Uczestnik": participant, "Seria": max_streak})

    df_streaks = pd.DataFrame(streaks).sort_values(by="Seria", ascending=False)
    
    if df_streaks.empty or df_streaks["Seria"].max() == 0:
        return pd.DataFrame(columns=["Uczestnik", "Seria"]) 
        
    top_streaks_values = df_streaks["Seria"].unique()
    top_3_values = sorted(top_streaks_values, reverse=True)[:3]
    
    df_top_streaks = df_streaks[df_streaks["Seria"].isin(top_3_values)]
    
    return df_top_streaks[df_top_streaks["Seria"] > 0] 

def find_last_complete_stage(data, elimination_map, max_day):
    """
    Znajduje ostatni dzień, dla którego wszyscy aktywni uczestnicy mają dane
    (jawne lub wywnioskowane przez przyszłe wpisy).
    """
    
    participant_max_days = {
        p: max((int(k) for k in data.get(p, {}).keys()), default=0)
        for p in CURRENT_PARTICIPANTS
    }

    complete_stages = []
    for day in range(1, max_day + 1): 
        is_complete_for_all = True
        active_participants_on_this_day = []

        for p in CURRENT_PARTICIPANTS:
            elim_day = elimination_map.get(p)
            if elim_day is None or elim_day >= day: 
                active_participants_on_this_day.append(p)
        
        if not active_participants_on_this_day and max_day > 0:
            continue 

        for p in active_participants_on_this_day:
            has_explicit_entry = day in data.get(p, {})
            has_future_entry = participant_max_days.get(p, 0) > day

            if not has_explicit_entry and not has_future_entry:
                is_complete_for_all = False
                break 
        
        if is_complete_for_all:
            complete_stages.append(day) 
            
    return complete_stages 

def get_race_data_for_day(data, day_to_show, lang):
    """Oblicza najwyższy zaliczony etap dla każdego gracza na koniec danego dnia."""
    scores = {p: 0 for p in CURRENT_PARTICIPANTS} 
    for day in range(1, day_to_show + 1):
        for p in CURRENT_PARTICIPANTS:
            if p in data and day in data.get(p, {}) and data[p][day]["status"] == "Zaliczone":
                scores[p] = day 
    
    df_race = pd.DataFrame.from_dict(
        scores, 
        orient='index', 
        columns=[_t('current_stats_race_total', lang)]
    ).reindex(CURRENT_PARTICIPANTS) # Stała kolejność
    
    return df_race

def show_historical_context(df_historical, lang):
    """
    Wyświetla tabelę z kontekstem historycznym dla OBECNYCH uczestników.
    """
    
    hist_data = df_historical[df_historical['uczestnik'].isin(CURRENT_PARTICIPANTS)].copy()
    
    if hist_data.empty:
        st.info(_t('current_ranking_historical_no_data', lang))
        return

    # Obliczanie statystyk
    stats = hist_data.groupby('uczestnik').agg(
        pb_result=pd.NamedAgg(column='rezultat_numeric', aggfunc='max'),
        avg_result=pd.NamedAgg(column='rezultat_numeric', aggfunc='mean'),
        editions_count=pd.NamedAgg(column='edycja_nr', aggfunc='nunique'),
        best_position=pd.NamedAgg(column='miejsce', aggfunc='min'),
        medals_top3=pd.NamedAgg(column='miejsce', aggfunc=lambda x: (x <= 3).sum())
    )
    
    # Obliczanie "Ostatnie X edycji"
    last_3_editions_nr = sorted(df_historical['edycja_nr'].unique())[-3:]
    hist_last_3 = hist_data[hist_data['edycja_nr'].isin(last_3_editions_nr)]
    avg_last_3 = hist_last_3.groupby('uczestnik')['rezultat_numeric'].mean().rename('avg_last_3')
    
    stats = stats.join(avg_last_3)
    
    # Dodanie brakujących uczestników (tych bez historii)
    stats = stats.reindex(CURRENT_PARTICIPANTS)
    
    participant_col_name = _t('ranking_col_participant', lang)
    
    # <<< POPRAWKA: Bezpieczne resetowanie indeksu i zmiana nazwy >>>
    stats = stats.reset_index()
    # Jeśli kolumna po resecie nazywa się 'uczestnik' (bo tak było w groupby), zmieniamy na 'uczestnik_raw'
    if 'uczestnik' in stats.columns:
        stats = stats.rename(columns={'uczestnik': 'uczestnik_raw'})
    # Na wypadek gdyby nazwała się 'index'
    elif 'index' in stats.columns:
        stats = stats.rename(columns={'index': 'uczestnik_raw'})

    
    stats_display = pd.DataFrame()
    # Teraz bezpiecznie pobieramy uczestnik_raw
    if 'uczestnik_raw' in stats.columns:
        stats_display[participant_col_name] = stats['uczestnik_raw']
    else:
        # Fallback, gdyby coś poszło nie tak (np. pusty dataframe)
        stats_display[participant_col_name] = stats.iloc[:, 0] if not stats.empty else []

    
    stats_display[_t('hist_context_pb', lang)] = stats['pb_result'].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "—")
    stats_display[_t('hist_context_avg', lang)] = stats['avg_result'].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "—")
    stats_display[_t('hist_context_avg_last_3', lang)] = stats['avg_last_3'].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "—")
    stats_display[_t('hist_context_best_pos', lang)] = stats['best_position'].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "—")
    stats_display[_t('hist_context_medals', lang)] = stats['medals_top3'].apply(lambda x: f"{x:.0f}" if pd.notna(x) and x > 0 else "—")
    stats_display[_t('hist_context_editions', lang)] = stats['editions_count'].apply(lambda x: f"{x:.0f}" if pd.notna(x) and x > 0 else "—")

    # Sortowanie wg średniego wyniku
    stats_display = stats_display.sort_values(by=_t('hist_context_avg', lang), ascending=False)
    
    st.dataframe(
        stats_display, 
        use_container_width=True, 
        hide_index=True
    )

def show_participant_summary(current_ranking_df, df_historical, current_data, max_day_reported, lang):
    """
    Wyświetla rozwijalną listę ze szczegółami każdego uczestnika.
    (Ta funkcja zachowuje linki, zgodnie z prośbą)
    """
    participant_col = _t('ranking_col_participant', lang)
    rank_col = _t('ranking_col_rank', lang)
    
    current_rank_map = current_ranking_df.set_index(participant_col)[rank_col].to_dict()

    if not df_historical.empty:
        hist_stats = df_historical.groupby('uczestnik').agg(
            winner_count=pd.NamedAgg(column='miejsce', aggfunc=lambda x: (x == 1).sum()),
            medalist_count=pd.NamedAgg(column='miejsce', aggfunc=lambda x: (x <= 3).sum())
        )
        df_historical_sorted = df_historical.sort_values('miesiac', ascending=False)
        last_rank_map = df_historical_sorted.drop_duplicates('uczestnik').set_index('uczestnik')['miejsce'].to_dict()
    else:
        hist_stats = pd.DataFrame(columns=['winner_count', 'medalist_count'])
        last_rank_map = {}

    participants_list = current_ranking_df[participant_col].tolist()
    num_participants = len(participants_list)

    for i, participant in enumerate(participants_list):
        current_rank = current_rank_map.get(participant, 'N/A')
        
        if participant in hist_stats.index:
            wins = hist_stats.loc[participant, 'winner_count']
            medals = hist_stats.loc[participant, 'medalist_count']
            prev_rank = int(last_rank_map.get(participant, 0))
            prev_rank_str = str(prev_rank) if prev_rank > 0 else "N/A"
        else:
            wins, medals, prev_rank_str = 0, 0, _t('summary_no_hist_data', lang)

        last_5_results_icons = []
        participant_days = current_data.get(participant, {})
        for day in range(max_day_reported, max_day_reported - 5, -1):
            if day < 1:
                break
            
            if day in participant_days:
                status_key = participant_days[day].get("status", "Brak raportu")
                icon = "✅" if status_key == "Zaliczone" else ("❌" if status_key == "Niezaliczone" else "❓")
            else:
                icon = "❓"
            last_5_results_icons.append(icon)
            
        last_5_str = " ".join(last_5_results_icons)

        stats_str = f"**{participant}** | {_t('summary_current_rank', lang)}: **{current_rank}** | {_t('summary_previous_rank', lang)}: {prev_rank_str} | {_t('summary_wins', lang)}: {wins} | {_t('summary_medals', lang)}: {medals} | {_t('summary_last_5_days', lang)}: {last_5_str}"

        col1, col2 = st.columns([0.8, 0.2])
        with col1:
            st.markdown(stats_str, unsafe_allow_html=True)
        with col2:
            st.link_button(_t('summary_profile_link', lang), f"https://hive.blog/@{participant}", use_container_width=True)
        
        if i < num_participants - 1:
            st.divider()

# === Główna Funkcja Strony ===

def show_current_edition_dashboard(lang):
    """Wyświetla dashboard dla bieżącej edycji."""
    st.header(_t('current_header', lang))
    
    sheet = connect_to_google_sheets()
    if not sheet:
        return 

    df_raw_data = load_google_sheet_data(sheet, "BiezacaEdycja")
    df_raw_logs = load_google_sheet_data(sheet, "LogWpisow")
    
    df_historical = load_historical_data_from_json()
    
    if df_raw_data.empty:
        st.info(_t('current_no_data', lang))
        return

    expected_data_cols = ['Participant', 'Day', 'Status', 'Timestamp', 'Notes']
    current_data, max_day_reported, success_data = process_raw_data(df_raw_data, lang, expected_data_cols, "BiezacaEdycja")
    
    if not success_data or max_day_reported == 0:
        return

    st.subheader(_t('current_ranking_header', lang))
    
    try:
        ranking_df, elimination_map = calculate_ranking(current_data, max_day_reported, lang, ranking_type='live')
        
        with st.expander(_t('current_ranking_rules_expander_label', lang)):
            st.markdown(_t('current_ranking_rules', lang, max_day_reported))
        
        st.dataframe(
            ranking_df, 
            use_container_width=True, 
            hide_index=True
        )
        
        with st.expander(_t('participant_summary_expander', lang)):
            caption_text = {
                'pl': f"Szczegółowe dane historyczne znajdziesz w zakładce: **{_t('nav_historical_stats', lang)}**",
                'en': f"Detailed historical data can be found in the: **{_t('nav_historical_stats', lang)}** tab"
            }
            st.caption(caption_text[lang])
            show_participant_summary(ranking_df, df_historical, current_data, max_day_reported, lang)

        if not df_historical.empty:
            with st.expander(_t('current_ranking_historical_expander', lang)):
                show_historical_context(df_historical, lang)
        
    except Exception as e:
        st.error(_t('current_ranking_error', lang, e))
        st.exception(e) 
        elimination_map = {} 
        
    st.markdown("---")

    st.subheader(_t('current_official_ranking_header', lang))
    
    complete_stages = find_last_complete_stage(current_data, elimination_map, max_day_reported)
    
    if complete_stages:
        default_stage = complete_stages[-1]
        
        selected_stage = st.select_slider(
            _t('current_official_stage_selector', lang),
            options=complete_stages, 
            value=default_stage 
        )
        
        st.info(_t('current_official_ranking_desc', lang, selected_stage))
        
        try:
            official_ranking_df, _ = calculate_ranking(current_data, selected_stage, lang, ranking_type='official')
            
            st.dataframe(
                official_ranking_df, 
                use_container_width=True, 
                hide_index=True
            )
            
        except Exception as e:
            st.error(_t('current_ranking_error', lang, e))
    else:
        st.info(_t('current_official_ranking_none', lang))
    
    st.markdown("---")
    
    st.subheader(_t('current_completeness_header', lang))
    
    pivot_data = []
    completeness_participant_col = _t('completeness_col_participant', lang) 
    
    for participant in CURRENT_PARTICIPANTS:
        days_data = current_data.get(participant, {})
        eliminated_on = elimination_map.get(participant)

        for day in range(1, max_day_reported + 1):
            if eliminated_on and day > eliminated_on:
                status_icon = "" 
            elif day in days_data:
                status_key = days_data[day].get("status", "Brak raportu")
                status_icon = "✅" if status_key == "Zaliczone" else ("❌" if status_key == "Niezaliczone" else "❓")
            else:
                status_icon = "❓" 

            pivot_data.append({
                completeness_participant_col: participant, 
                _t('completeness_col_day', lang): day,
                "Status": status_icon
            })
            
    if not pivot_data:
        st.info(_t('current_completeness_no_data', lang))
        return

    df_pivot = pd.DataFrame(pivot_data)
    
    days_to_show = [day for day in range(1, max_day_reported + 1)]
    
    completeness_pivot = df_pivot.pivot(
        index=completeness_participant_col, 
        columns=_t('completeness_col_day', lang),
        values="Status"
    ).reindex(columns=days_to_show, fill_value="").reindex(index=sorted(CURRENT_PARTICIPANTS))
    
    completeness_pivot_display = completeness_pivot.reset_index()

    # <<< POPRAWKA: Konwersja nagłówków kolumn na stringi (naprawa błędu mixed types) >>>
    completeness_pivot_display.columns = completeness_pivot_display.columns.astype(str)
    
    st.dataframe(
        completeness_pivot_display, 
        hide_index=True
    )

    st.subheader(_t('current_stats_header', lang))
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"**{_t('current_stats_top_submitters', lang)}**")
        st.caption(_t('current_stats_top_submitters_desc', lang))
        
        expected_log_cols = ['Submitter', 'Participant', 'Day', 'Status_Reported', 'Timestamp']
        if df_raw_logs.empty:
            st.info(_t('current_log_empty', lang))
        elif not all(col in df_raw_logs.columns for col in expected_log_cols):
            st.error(_t('current_header_check_error', lang))
            st.json({
                _t('current_header_check_details', lang, "LogWpisow"): "",
                _t('current_header_check_expected', lang): expected_log_cols,
                _t('current_header_check_found', lang): df_raw_logs.columns.tolist()
            })
        else:
            df_helpers = df_raw_logs[df_raw_logs['Submitter'] != 'poprzeczka (Admin)']
            
            total_entries = len(df_raw_logs)
            helper_entries = len(df_helpers)
            admin_entries = total_entries - helper_entries
            
            if total_entries > 0:
                helper_percentage = (helper_entries / total_entries) * 100
            else:
                helper_percentage = 0
            
            all_submitters = df_helpers['Submitter'].value_counts() 
            
            if all_submitters.empty:
                st.info(_t('current_stats_top_submitters_none', lang))
            else:
                for name, count in all_submitters.items():
                    mention(
                        label=f"**{name}** ({count} wpisów)", 
                        icon="🏆", 
                        url=f"https://hive.blog/@{name}"
                    )
            
            st.markdown("---")
            st.caption(_t('current_stats_top_submitters_percentage', lang, helper_percentage, helper_entries, admin_entries))

    with col2:
        st.markdown(f"**{_t('current_stats_streaks', lang)}**")
        st.caption(_t('current_stats_streaks_desc', lang))
        
        df_streaks = calculate_current_stats(current_data, max_day_reported, lang)
        
        if not df_streaks.empty:
            for _, row in df_streaks.iterrows():
                mention(
                    label=f"**{row['Uczestnik']}** ({row['Seria']} {_t('current_stats_streaks_days', lang)})", 
                    icon="🔥", 
                    url=f"https://hive.blog/@{row['Uczestnik']}"
                )
        else:
            st.info("Brak znaczących serii.")
            
    st.markdown("---")

    st.subheader(_t('current_stats_race_header', lang))
    st.write(_t('current_stats_race_desc', lang))
    
    chart_placeholder = st.empty()
    
    mode = st.radio(
        _t('current_stats_race_mode', lang), 
        (_t('current_stats_race_mode_anim', lang), _t('current_stats_race_mode_manual', lang)), 
        index=1, 
        horizontal=True,
    )
    
    plt.style.use('dark_background') 
    max_axis_day = max(31, max_day_reported)
    
    if mode == _t('current_stats_race_mode_anim', lang):
        if st.button(_t('current_stats_race_button', lang)):
            scores = {p: 0 for p in CURRENT_PARTICIPANTS} 
            for day in range(1, max_day_reported + 1):
                for p in CURRENT_PARTICIPANTS:
                    if p in current_data and day in current_data.get(p, {}) and current_data[p][day]["status"] == "Zaliczone":
                        scores[p] = day 
                
                df_race = pd.DataFrame.from_dict(
                    scores, orient='index', columns=[_t('current_stats_race_total', lang)]
                ).reindex(CURRENT_PARTICIPANTS)
                
                fig, ax = plt.subplots(figsize=(10, 6))
                sorted_index = sorted(df_race.index, reverse=True) 
                ax.barh(sorted_index, df_race.loc[sorted_index, _t('current_stats_race_total', lang)])
                ax.set_xlim(0, max_axis_day) 
                ax.set_title(f"{_t('current_stats_race_day', lang)}: {day}")
                plt.tight_layout() 
                
                with chart_placeholder.container():
                    st.pyplot(fig)
                plt.close(fig) 
                time.sleep(0.1) 
    else:
        race_day_slider = st.slider(
            _t('current_stats_race_day', lang), 
            1, max_day_reported, max_day_reported
        )
        
        df_race = get_race_data_for_day(current_data, race_day_slider, lang)
        
        fig, ax = plt.subplots(figsize=(10, 6))
        sorted_index = sorted(df_race.index, reverse=True) 
        ax.barh(sorted_index, df_race.loc[sorted_index, _t('current_stats_race_total', lang)])
        ax.set_xlim(0, max_axis_day) 
        ax.set_title(f"{_t('current_stats_race_day', lang)}: {race_day_slider}")
        plt.tight_layout() 
        
        with chart_placeholder.container():
            st.pyplot(fig)
        plt.close(fig)


    if st.checkbox(_t('current_log_expander', lang)):
        expected_log_cols = ['Submitter', 'Participant', 'Day', 'Status_Reported', 'Timestamp']
        if not df_raw_logs.empty and all(col in df_raw_logs.columns for col in expected_log_cols):
            df_log_sorted = df_raw_logs.sort_values("Timestamp", ascending=False)
            st.dataframe(df_log_sorted, use_container_width=True)
        else:
            st.info(_t('current_log_empty', lang))