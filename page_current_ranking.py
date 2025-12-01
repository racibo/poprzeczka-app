import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import time
import numpy as np
from datetime import datetime 
from streamlit_extras.mention import mention
from translations import _t
from config import EDITIONS
from google_connect import connect_to_google_sheets
from data_loader import load_google_sheet_data, load_historical_data_from_json, process_raw_data

# === Funkcje Pomocnicze ===

def clean_title_for_chart(text):
    """Usuwa emotikony z tekstu, aby uniknąć ostrzeżeń matplotlib (Missing Glyph)."""
    return text.replace("📉", "").replace("🔥", "").replace("🏁", "").strip()

def calculate_ranking(data, max_day_reported, lang, participants_list, ranking_type='live'):
    """Oblicza ranking na podstawie zasad gry."""
    ranking_data = []
    elimination_map = {} 

    for participant in participants_list:
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

        failed_stages_str = ", ".join(map(str, sorted(failed_stages)[:10])) + ("..." if len(failed_stages) > 10 else "")

        if ranking_type == 'live':
            failed_col_key = 'ranking_col_failed_list_live'
            if not eliminated_on_day and consecutive_fails == 2:
                failed_stages_str += " ❗"
        else: # 'official'
            failed_col_key = 'ranking_col_failed_list_official'
            failed_stages_str = ", ".join(map(str, sorted(failed_stages)))

        ranking_data.append({
            _t('ranking_col_participant', lang): participant,
            _t('ranking_col_highest_pass', lang): highest_completed,
            "sort_key_failure_tuple": get_failure_tuple(failed_stages, highest_completed),
            _t('ranking_col_status', lang): status_text,
            _t(failed_col_key, lang): failed_stages_str,
            "eliminated_on_day": eliminated_on_day 
        })
        elimination_map[participant] = eliminated_on_day 
    
    def sort_key(entry):
        return (
            -entry[_t('ranking_col_highest_pass', lang)], 
            entry["sort_key_failure_tuple"]               
        )

    ranking_data.sort(key=sort_key)
    
    rank_col_name = _t('ranking_col_rank', lang)
    last_sort_key = None
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
    
    cols_to_return = [
        rank_col_name, 
        _t('ranking_col_participant', lang), 
        _t('ranking_col_highest_pass', lang), 
        _t('ranking_col_status', lang)
    ]
    if failed_col_name in df_ranking.columns:
        cols_to_return.append(failed_col_name)
    
    return df_ranking[cols_to_return], elimination_map

def calculate_current_stats(data, max_day, lang, participants_list):
    """Oblicza najdłuższe serie zaliczeń."""
    streaks = []
    for participant in participants_list:
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
    
    return df_streaks[df_streaks["Seria"].isin(top_3_values) & (df_streaks["Seria"] > 0)] 

def calculate_rabbit_stats(data, max_day, elimination_map, lang, participants_list):
    """Oblicza 'Zające' - aktywni uczestnicy z największą liczbą potknięć."""
    stumbles = []
    for participant in participants_list:
        is_active = elimination_map.get(participant) is None or elimination_map.get(participant) > max_day
        
        if is_active:
            days_data = data.get(participant, {})
            fails_count = 0
            for day in range(1, max_day + 1):
                if day not in days_data or days_data[day]["status"] != "Zaliczone":
                    fails_count += 1
            
            if fails_count > 0:
                stumbles.append({"Uczestnik": participant, "Potknięcia": fails_count})
    
    df_stumbles = pd.DataFrame(stumbles).sort_values(by="Potknięcia", ascending=False)
    
    if df_stumbles.empty:
        return pd.DataFrame(columns=["Uczestnik", "Potknięcia"])

    top_values = sorted(df_stumbles["Potknięcia"].unique(), reverse=True)[:3]
    return df_stumbles[df_stumbles["Potknięcia"].isin(top_values)]

def find_last_complete_stage(data, elimination_map, max_day, participants_list):
    """Znajduje ostatni dzień z kompletnymi danymi."""
    participant_max_days = {
        p: max((int(k) for k in data.get(p, {}).keys()), default=0)
        for p in participants_list
    }

    complete_stages = []
    for day in range(1, max_day + 1): 
        is_complete_for_all = True
        active_participants_on_this_day = []

        for p in participants_list:
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

def get_race_data_for_day(data, day_to_show, lang, participants_list):
    """Oblicza dane do wyścigu."""
    scores = {p: 0 for p in participants_list} 
    for day in range(1, day_to_show + 1):
        for p in participants_list:
            if p in data and day in data.get(p, {}) and data[p][day]["status"] == "Zaliczone":
                scores[p] = day 
    
    return pd.DataFrame.from_dict(
        scores, orient='index', columns=[_t('current_stats_race_total', lang)]
    ).reindex(participants_list)

def show_historical_context(df_historical, lang, participants_list):
    """Wyświetla tabelę kontekstu historycznego."""
    hist_data = df_historical[df_historical['uczestnik'].isin(participants_list)].copy()
    
    if hist_data.empty:
        st.info(_t('current_ranking_historical_no_data', lang))
        return

# Modyfikacja: Najpierw standardowe statystyki bez liczby edycji
    stats = hist_data.groupby('uczestnik').agg(
        pb_result=pd.NamedAgg(column='rezultat_numeric', aggfunc='max'),
        avg_result=pd.NamedAgg(column='rezultat_numeric', aggfunc='mean'),
        # Tu usunęliśmy błędne zliczanie edycji
        best_position=pd.NamedAgg(column='miejsce', aggfunc='min'),
        medals_top3=pd.NamedAgg(column='miejsce', aggfunc=lambda x: (x <= 3).sum())
    )

    # Obliczamy liczbę edycji ODDZIELNIE, biorąc pod uwagę tylko te z wynikiem (nie NaN)
    real_editions_count = hist_data.dropna(subset=['rezultat_numeric']).groupby('uczestnik')['edycja_nr'].nunique()
    
    # Dodajemy poprawną kolumnę do tabeli statystyk
    stats['editions_count'] = real_editions_count
    
    last_3_editions_nr = sorted(df_historical['edycja_nr'].unique())[-3:]
    hist_last_3 = hist_data[hist_data['edycja_nr'].isin(last_3_editions_nr)]
    
    if not hist_last_3.empty:
        avg_last_3 = hist_last_3.groupby('uczestnik')['rezultat_numeric'].mean().reset_index(name='avg_last_3')
        stats = stats.reset_index().merge(avg_last_3, on='uczestnik', how='left').set_index('uczestnik')
    else:
        stats['avg_last_3'] = np.nan

    stats = stats.reindex(participants_list)
    
    participant_col_name = _t('ranking_col_participant', lang)
    
    stats = stats.reset_index()
    if 'uczestnik' in stats.columns:
        stats = stats.rename(columns={'uczestnik': 'uczestnik_raw'})
    elif 'index' in stats.columns:
        stats = stats.rename(columns={'index': 'uczestnik_raw'})

    stats_display = pd.DataFrame()
    if 'uczestnik_raw' in stats.columns:
        stats_display[participant_col_name] = stats['uczestnik_raw']
    else:
        stats_display[participant_col_name] = stats.iloc[:, 0] if not stats.empty else []
    
    stats_display[_t('hist_context_pb', lang)] = stats['pb_result'].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "—")
    stats_display[_t('hist_context_avg', lang)] = stats['avg_result'].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "—")
    stats_display[_t('hist_context_avg_last_3', lang)] = stats['avg_last_3'].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "—")
    stats_display[_t('hist_context_best_pos', lang)] = stats['best_position'].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "—")
    stats_display[_t('hist_context_medals', lang)] = stats['medals_top3'].apply(lambda x: f"{x:.0f}" if pd.notna(x) and x > 0 else "—")
    stats_display[_t('hist_context_editions', lang)] = stats['editions_count'].apply(lambda x: f"{x:.0f}" if pd.notna(x) and x > 0 else "—")

    st.dataframe(
        stats_display.sort_values(by=_t('hist_context_avg', lang), ascending=False), 
        width="stretch",
        hide_index=True
    )

def show_selected_participant_details(participant, rank, df_historical, current_data, max_day_reported, lang):
    """Wyświetla szczegóły dla JEDNEGO wybranego uczestnika."""
    
    wins, medals, prev_rank_str = 0, 0, _t('summary_no_hist_data', lang)
    avg_res_all, avg_res_l3, avg_pos_all = "—", "—", "—"

    if not df_historical.empty and participant in df_historical['uczestnik'].values:
        p_hist = df_historical[df_historical['uczestnik'] == participant]
        wins = (p_hist['miejsce'] == 1).sum()
        medals = (p_hist['miejsce'] <= 3).sum()
        
        last_edition_nr = p_hist['edycja_nr'].max()
        last_rank = p_hist[p_hist['edycja_nr'] == last_edition_nr]['miejsce'].min()
        if pd.notna(last_rank):
            prev_rank_str = str(int(last_rank))
            
        if not p_hist['rezultat_numeric'].isnull().all():
            avg_res_all = f"{p_hist['rezultat_numeric'].mean():.1f}"
            
        last_3_ed = sorted(df_historical['edycja_nr'].unique())[-3:]
        p_hist_l3 = p_hist[p_hist['edycja_nr'].isin(last_3_ed)]
        if not p_hist_l3['rezultat_numeric'].isnull().all():
            avg_res_l3 = f"{p_hist_l3['rezultat_numeric'].mean():.1f}"
            
        if not p_hist['miejsce'].isnull().all():
            avg_pos_all = f"{p_hist['miejsce'].mean():.1f}"

    last_5_results_icons = []
    participant_days = current_data.get(participant, {})
    for day in range(max_day_reported, max(0, max_day_reported - 5), -1):
        if day in participant_days:
            status_key = participant_days[day].get("status", "Brak raportu")
            icon = "✅" if status_key == "Zaliczone" else ("❌" if status_key == "Niezaliczone" else "❓")
        else:
            icon = "❓"
        last_5_results_icons.append(icon)
    last_5_str = " ".join(last_5_results_icons)

    with st.container(border=True):
        col_info, col_link = st.columns([0.8, 0.2])
        with col_info:
            st.subheader(f"👤 {participant}")
            st.markdown(f"""
            **{_t('summary_current_rank', lang)}:** {rank} | 
            **{_t('summary_previous_rank', lang)}:** {prev_rank_str}
            
            🥇 **{_t('summary_wins', lang)}:** {wins} | 
            🏅 **{_t('summary_medals', lang)}:** {medals}
            
            **{_t('card_hist_stats_header', lang)}**
            * {_t('card_avg_total', lang)}: **{avg_res_all}**
            * {_t('card_avg_l3', lang)}: **{avg_res_l3}**
            * {_t('card_avg_pos', lang)}: **{avg_pos_all}**
            
            📅 **{_t('summary_last_5_days', lang)}:** {last_5_str}
            """)
            
            caption_text = {
                'pl': f"👉 Więcej danych w zakładce: **{_t('nav_historical_stats', lang)}**",
                'en': f"👉 More data in: **{_t('nav_historical_stats', lang)}** tab"
            }
            st.caption(caption_text[lang])
            
        with col_link:
            st.write("")
            st.link_button(f"Hive\n@{participant}", f"https://hive.blog/@{participant}", use_container_width=True)

def show_daily_rank_progression(current_data, complete_stages, lang, participants_list):
    """Generuje wykres liniowy pokazujący zmiany miejsca w rankingu dzień po dniu."""
    labels = {
        'pl': {'loading': "Generowanie wykresu historycznego...", 'title': "Przebieg rywalizacji (Zmiana miejsc)", 'day': "Dzień", 'rank': "Miejsce"},
        'en': {'loading': "Generating history chart...", 'title': "Competition Progress (Rank History)", 'day': "Day", 'rank': "Rank"}
    }
    txt = labels.get(lang, labels['pl'])

    max_day_to_show = complete_stages[-1] if complete_stages else 0
    if max_day_to_show == 0:
        st.info("Brak kompletnych etapów do wyświetlenia wykresu.")
        return

    with st.spinner(txt['loading']):
        progress_data = {}
        for day in range(1, max_day_to_show + 1):
            df_daily, _ = calculate_ranking(current_data, day, lang, participants_list, ranking_type='live')
            part_col = _t('ranking_col_participant', lang)
            rank_col = _t('ranking_col_rank', lang)
            progress_data[day] = df_daily.set_index(part_col)[rank_col].to_dict()
            
        df_progress = pd.DataFrame.from_dict(progress_data, orient='index')
        
        if df_progress.empty:
            st.info("Brak danych do wyświetlenia wykresu.")
            return

        fig, ax = plt.subplots(figsize=(12, 8))
        plt.style.use('dark_background')
        ax.set_facecolor('#0e1117')
        fig.patch.set_facecolor('#0e1117')
        
        colors = plt.cm.tab20(np.linspace(0, 1, len(df_progress.columns)))
        
        for i, participant in enumerate(df_progress.columns):
            ax.plot(df_progress.index, df_progress[participant], marker='o', markersize=4, label=participant, color=colors[i], linewidth=1.5)
            last_val = df_progress[participant].iloc[-1]
            if pd.notna(last_val):
                ax.text(max_day_to_show + 0.2, last_val, f" {participant}", verticalalignment='center', fontsize=9, color=colors[i], fontweight='bold')

        ax.invert_yaxis()
        ax.set_title(clean_title_for_chart(txt['title']), color='white')
        ax.set_xlabel(txt['day'], color='white')
        ax.set_ylabel(txt['rank'], color='white')
        ax.grid(True, which='both', linestyle='--', linewidth=0.3, alpha=0.5)
        ax.set_xticks(df_progress.index)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        
        ax.tick_params(axis='x', colors='white')
        ax.tick_params(axis='y', colors='white')
        for spine in ax.spines.values():
            spine.set_color('#444444')

        st.pyplot(fig)

def show_stage_analysis(current_data, max_day_reported, elimination_map, complete_stages, lang, participants_list):
    """Wyświetla statystyki trudności etapów (wykres + tekst)."""
    
    if 'stage_analysis_expanded' not in st.session_state:
        st.session_state.stage_analysis_expanded = False

    lbl = {
        'pl': {
            'expander': "📊 Analiza Etapów (Trudność)",
            'tool_header': "🔎 Sprawdź, kto zaliczył / nie zaliczył",
            'select_stage': "Wybierz numer etapu:",
            'check_btn': "Pokaż listę",
            'pass_header': "✅ Zaliczyli:",
            'fail_header': "❌ Nie zaliczyli:",
            'no_one': "Brak",
            'everyone_passed': "Wszyscy (aktywni) zaliczyli!",
            'everyone_failed': "Nikt nie zaliczył!"
        },
        'en': {
            'expander': "📊 Stage Analysis (Difficulty)",
            'tool_header': "🔎 Check pass/fail list",
            'select_stage': "Select stage number:",
            'check_btn': "Show list",
            'pass_header': "✅ Passed:",
            'fail_header': "❌ Failed:",
            'no_one': "None",
            'everyone_passed': "Everyone (active) passed!",
            'everyone_failed': "No one passed!"
        }
    }
    txt = lbl.get(lang, lbl['pl'])

    def toggle_stage_analysis():
        st.session_state.stage_analysis_expanded = True

    with st.expander(txt['expander'], expanded=st.session_state.stage_analysis_expanded):
        stage_fail_rates = {}
        max_fail_rate = -1
        hardest_stage_num = -1
        
        for day in complete_stages:
            fails = 0
            total_active = 0
            
            for p in participants_list:
                elim_day = elimination_map.get(p)
                if elim_day is not None and elim_day < day:
                    continue 
                
                total_active += 1
                p_data = current_data.get(p, {})
                if day not in p_data or p_data[day]['status'] != "Zaliczone":
                    fails += 1
            
            rate = (fails / total_active * 100) if total_active > 0 else 0
            stage_fail_rates[day] = rate
            
            if rate > max_fail_rate:
                max_fail_rate = rate
                hardest_stage_num = day
        
        if hardest_stage_num != -1:
            st.markdown(_t('stage_analysis_hardest', lang, hardest_stage_num, max_fail_rate))
        
        if stage_fail_rates:
            days = list(stage_fail_rates.keys())
            rates = list(stage_fail_rates.values())
            
            fig, ax = plt.subplots(figsize=(10, 4))
            plt.style.use('dark_background')
            ax.set_facecolor('#0e1117')
            fig.patch.set_facecolor('#0e1117')
            
            ax.plot(days, rates, marker='o', color='#ff4b4b', linewidth=2)
            ax.fill_between(days, rates, color='#ff4b4b', alpha=0.2)
            
            ax.set_title(clean_title_for_chart(_t('stage_analysis_title', lang)), color='white')
            ax.set_ylabel(_t('stage_analysis_y_axis', lang), color='white')
            ax.set_xlabel("Dzień / Stage", color='white')
            ax.grid(True, linestyle='--', alpha=0.3)
            ax.set_ylim(0, 105)
            ax.set_xticks(days)
            ax.xaxis.set_major_locator(MaxNLocator(integer=True))
            
            for spine in ax.spines.values():
                spine.set_color('#444444')
            ax.tick_params(axis='x', colors='white')
            ax.tick_params(axis='y', colors='white')
            
            st.pyplot(fig)
            
        st.divider()
        
        st.markdown(f"**{txt['tool_header']}**")
        
        col_sel, col_btn = st.columns([3, 1])
        with col_sel:
            selected_day_check = st.selectbox(txt['select_stage'], options=range(1, max_day_reported + 1), index=max_day_reported-1, key="stage_checker_select")
        with col_btn:
            st.write("") 
            st.write("") 
            check_clicked = st.button(txt['check_btn'], on_click=toggle_stage_analysis)

        if selected_day_check:
            passed_list = []
            failed_list = []
            
            for p in participants_list:
                elim_day = elimination_map.get(p)
                if elim_day is not None and elim_day < selected_day_check:
                    continue
                
                p_data = current_data.get(p, {})
                if selected_day_check in p_data and p_data[selected_day_check]['status'] == "Zaliczone":
                    passed_list.append(f"@{p}")
                else:
                    failed_list.append(f"@{p}")
            
            c_pass, c_fail = st.columns(2)
            with c_pass:
                st.write(txt['pass_header'])
                if passed_list:
                    st.code(" ".join(passed_list), language=None)
                else:
                    st.write(f"_{txt['everyone_failed']}_")
                    
            with c_fail:
                st.write(txt['fail_header'])
                if failed_list:
                    st.code(" ".join(failed_list), language=None)
                else:
                    st.write(f"_{txt['everyone_passed']}_")

def show_survival_comparison(current_data, max_day_reported, df_historical, lang, elimination_map, complete_stages, participants_list):
    """Porównuje krzywą przetrwania obecnej edycji z 3 ostatnimi."""
    
    current_limit_day = complete_stages[-1] if complete_stages else 1
    current_days_axis = range(1, current_limit_day + 1)
    
    total_participants = len(participants_list)
    current_percentages = []
    
    for d in current_days_axis:
        active_count = 0
        for p in participants_list:
            e_day = elimination_map.get(p)
            if e_day is None or e_day >= d:
                active_count += 1
        current_percentages.append((active_count / total_participants) * 100)

    hist_data = {}
    max_hist_day = 0
    
    if not df_historical.empty:
        editions = sorted(df_historical['miesiac_rok_str'].unique(), key=lambda x: datetime.strptime(x, '%m.%Y'), reverse=True)
        last_3_editions = editions[:3]
        
        for ed in last_3_editions:
            ed_df = df_historical[df_historical['miesiac_rok_str'] == ed].copy()
            if ed_df.empty: continue
            
            ed_df['dropout_day'] = ed_df['rezultat_numeric'] + 3
            total_in_ed = len(ed_df)
            
            percentages = []
            max_day_in_ed = int(ed_df['dropout_day'].max())
            plot_days_hist = max_day_in_ed + 2 
            
            if plot_days_hist > max_hist_day:
                max_hist_day = plot_days_hist
            
            for d in range(1, plot_days_hist + 1):
                active = (ed_df['dropout_day'] > d).sum()
                pct = (active / total_in_ed) * 100
                percentages.append(pct)
                if pct == 0 and len(percentages) > 5:
                    break
            
            hist_data[ed] = percentages

    with st.expander(_t('survival_chart_header', lang)):
        fig, ax = plt.subplots(figsize=(10, 6))
        plt.style.use('dark_background')
        ax.set_facecolor('#0e1117')
        fig.patch.set_facecolor('#0e1117')
        
        for ed_name, pct_list in hist_data.items():
            x_hist = range(1, len(pct_list) + 1)
            ax.plot(x_hist, pct_list, linestyle='--', alpha=0.6, label=ed_name)
            
        ax.plot(current_days_axis, current_percentages, color='#00ff00', linewidth=3, marker='o', label=_t('survival_current_legend', lang))
        
        ax.set_title(clean_title_for_chart(_t('survival_chart_title', lang)), color='white')
        ax.set_xlabel("Dzień / Stage", color='white')
        ax.set_ylabel(_t('survival_y_axis', lang), color='white')
        ax.set_ylim(0, 105)
        
        global_max_x = max(max_hist_day, current_limit_day)
        ax.set_xlim(1, global_max_x + 1)
        
        ax.grid(True, linestyle='--', alpha=0.3)
        ax.legend()
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        
        for spine in ax.spines.values():
            spine.set_color('#444444')
        ax.tick_params(axis='x', colors='white')
        ax.tick_params(axis='y', colors='white')

        st.pyplot(fig)

def get_past_winners_positions(df_historical, current_ranking_df, lang):
    """Znajduje obecne pozycje zwycięzców poprzednich 3 edycji."""
    if df_historical.empty:
        return []
    
    all_editions = sorted(df_historical['miesiac_rok_str'].unique(), key=lambda x: datetime.strptime(x, '%m.%Y'), reverse=True)
    last_3_editions = all_editions[:3]
    
    recent_hist = df_historical[df_historical['miesiac_rok_str'].isin(last_3_editions)]
    past_winners = recent_hist[recent_hist['miejsce'] == 1]['uczestnik'].unique().tolist()
    
    current_positions = []
    participant_col = _t('ranking_col_participant', lang)
    rank_col = _t('ranking_col_rank', lang)
    
    for winner in past_winners:
        if winner in current_ranking_df[participant_col].values:
            rank = current_ranking_df[current_ranking_df[participant_col] == winner][rank_col].values[0]
            current_positions.append(f"@{winner} ({rank})")
            
    return current_positions

def generate_weekly_summary_markdown(week_num, current_data, df_historical, df_logs, lang, participants_list):
    """Generuje tekst podsumowania dla konkretnego tygodnia (np. 7, 14, 21 dzień)."""
    
    day_limit = week_num * 7
    
    # 1. Ranking na dany dzień
    ranking_df, elimination_map = calculate_ranking(current_data, day_limit, lang, participants_list, ranking_type='live')
    participant_col = _t('ranking_col_participant', lang)
    rank_col = _t('ranking_col_rank', lang)
    
    # Liderzy (Miejsce 1)
    leaders = ranking_df[ranking_df[rank_col] == 1][participant_col].tolist()
    leaders_str = ", ".join([f"@{l}" for l in leaders])
    leader_text = _t('weekly_leader_sg', lang, leaders_str) if len(leaders) == 1 else _t('weekly_leader_pl', lang, leaders_str)
    
    # Pościg (Miejsca 2-5) - Tylko jeśli liderów jest mniej niż 5
    chasing_str = ""
    chasers_md = ""
    if len(leaders) < 5:
        chasers = ranking_df[(ranking_df[rank_col] > 1) & (ranking_df[rank_col] <= 5)][participant_col].tolist()
        if chasers:
            chasing_str = ", ".join([f"@{c}" for c in chasers])
            chasers_md = _t('weekly_chasers', lang, chasing_str)
    
    # 2. Byli zwycięzcy (ost 3 edycje)
    past_winners_info = get_past_winners_positions(df_historical, ranking_df, lang)
    past_winners_str = ", ".join(past_winners_info) if past_winners_info else "brak danych"
    
    # 3. Liczba uczestników
    started_count = len(participants_list)
    active_count = 0
    for p in participants_list:
        elim_day = elimination_map.get(p)
        if elim_day is None or elim_day > day_limit:
            active_count += 1
            
    status_word = "nadal" if active_count == started_count else ("już tylko" if lang == 'pl' else "only")
    
    # 4. Porównanie historyczne (proste)
    comparison_str = "brak danych historycznych"
    if not df_historical.empty:
        editions = df_historical['miesiac_rok_str'].unique()
        hist_active_pcts = []
        for ed in editions:
            ed_df = df_historical[df_historical['miesiac_rok_str'] == ed]
            total_ed = len(ed_df)
            active_at_limit = ((ed_df['rezultat_numeric'] + 3) > day_limit).sum()
            if total_ed > 0:
                hist_active_pcts.append(active_at_limit / total_ed)
        
        if hist_active_pcts:
            avg_hist_pct = sum(hist_active_pcts) / len(hist_active_pcts)
            current_pct = active_count / started_count if started_count > 0 else 0
            diff = current_pct - avg_hist_pct
            
            if diff > 0.1: comparison_str = "jest zauważalnie lepiej" if lang == 'pl' else "is noticeably better"
            elif diff > 0.05: comparison_str = "jest lepiej" if lang == 'pl' else "is better"
            elif diff < -0.1: comparison_str = "jest zauważalnie gorzej" if lang == 'pl' else "is noticeably worse"
            elif diff < -0.05: comparison_str = "jest gorzej" if lang == 'pl' else "is worse"
            else: comparison_str = "jest podobnie" if lang == 'pl' else "is similar"
            
    # 5. Algorytm Nagród
    rewards_str = ""
    helper_pct_val = 0
    
    if not df_logs.empty and 'Submitter' in df_logs.columns:
        df_logs['Day_Num'] = pd.to_numeric(df_logs['Day'], errors='coerce')
        logs_subset = df_logs[df_logs['Day_Num'] <= day_limit]
        
        if not logs_subset.empty:
            helpers_subset = logs_subset[logs_subset['Submitter'] != 'poprzeczka (Admin)']
            
            total_subset_entries = len(logs_subset)
            if total_subset_entries > 0:
                helper_pct_val = int((len(helpers_subset) / total_subset_entries) * 100)
            
            P = helper_pct_val
            
            if P > 0:
                helper_pool = P * 0.80
                leader_pool = P * 0.20
                user_rewards = {}
                
                helper_counts = helpers_subset['Submitter'].value_counts()
                total_helper_entries = helper_counts.sum()
                
                for user, count in helper_counts.items():
                    share = (count / total_helper_entries) * helper_pool
                    user_rewards[user] = user_rewards.get(user, 0) + share
                    
                top_leaders = ranking_df[(ranking_df[rank_col] <= 5)][participant_col].unique()
                top_leaders = top_leaders[:5] 
                
                if len(top_leaders) > 0:
                    share_per_leader = leader_pool / len(top_leaders)
                    for leader in top_leaders:
                        user_rewards[leader] = user_rewards.get(leader, 0) + share_per_leader
                
                final_rewards = []
                for user, val in user_rewards.items():
                    r_val = round(val)
                    if r_val > 0:
                        final_rewards.append((user, r_val))
                
                final_rewards.sort(key=lambda x: x[1], reverse=True)
                
                # Limit max 7 osób
                final_rewards = final_rewards[:7]
                
                rewards_list = [f"{val}% - @{user}" for user, val in final_rewards]
                rewards_str = ", ".join(rewards_list)

    # SZABLON MD
    summary_text = f"""
{_t('weekly_intro', lang, week_num)}
{leader_text} {chasers_md}
{_t('weekly_winners', lang, past_winners_str)}

{_t('weekly_participants', lang, started_count, day_limit, active_count, status_word)}
{_t('weekly_comparison', lang, comparison_str)}

{_t('weekly_footer_new', lang, helper_pct_val)}
{rewards_str}
"""
    return summary_text

# === Główna Funkcja Strony ===

def show_current_edition_dashboard(lang, edition_key="november"):
    """Wyświetla dashboard dla wybranej edycji."""
    
    cfg = EDITIONS.get(edition_key, EDITIONS['november'])
    sheet_name = cfg['sheet_name']
    label = cfg['label_' + lang]
    participants_list = cfg['participants']  # <--- POBIERAMY LISTĘ Z CONFIGA
    
    st.header(f"{_t('current_header', lang)}: {label}")
    
    sheet = connect_to_google_sheets()
    if not sheet: return 

    try:
        df_raw_data = load_google_sheet_data(sheet, sheet_name)
    except Exception:
        st.error(f"Nie znaleziono arkusza: {sheet_name}. Utwórz go w Google Sheets!")
        return

    df_raw_logs = load_google_sheet_data(sheet, "LogWpisow")
    df_historical = load_historical_data_from_json()
    
    if df_raw_data.empty:
        st.info(_t('current_no_data', lang))
        return

    expected_data_cols = ['Participant', 'Day', 'Status', 'Timestamp', 'Notes']
    current_data, max_day_reported, success_data = process_raw_data(df_raw_data, lang, expected_data_cols, sheet_name)
    
    if not success_data or max_day_reported == 0:
        return

    # --- Ranking Live ---
    st.subheader(_t('current_ranking_header', lang))
    try:
        ranking_df, elimination_map = calculate_ranking(current_data, max_day_reported, lang, participants_list, ranking_type='live')
        
        st.info(_t('ranking_selection_instruction', lang))

        ranking_df_display = ranking_df.copy()
        
        selection = st.dataframe(
            ranking_df_display, 
            width="stretch", 
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        if selection.selection.rows:
            selected_index = selection.selection.rows[0]
            participant_col = _t('ranking_col_participant', lang)
            rank_col = _t('ranking_col_rank', lang)
            
            selected_participant = ranking_df_display.iloc[selected_index][participant_col]
            selected_rank = ranking_df_display.iloc[selected_index][rank_col]
            
            show_selected_participant_details(
                selected_participant, 
                selected_rank, 
                df_historical, 
                current_data, 
                max_day_reported, 
                lang
            )
        
    except Exception as e:
        st.error(_t('current_ranking_error', lang, e))
        st.exception(e) 
        elimination_map = {} 
        
    st.markdown("---")

    # --- Ranking Oficjalny ---
    st.subheader(_t('current_official_ranking_header', lang))
    complete_stages = find_last_complete_stage(current_data, elimination_map, max_day_reported, participants_list)
    
    if complete_stages:
        default_stage = complete_stages[-1]
        selected_stage = st.select_slider(
            _t('current_official_stage_selector', lang),
            options=complete_stages, 
            value=default_stage 
        )
        st.info(_t('current_official_ranking_desc', lang, selected_stage))
        try:
            official_ranking_df, _ = calculate_ranking(current_data, selected_stage, lang, participants_list, ranking_type='official')
            st.dataframe(official_ranking_df, width="stretch", hide_index=True)
        except Exception as e:
            st.error(_t('current_ranking_error', lang, e))
    else:
        st.info(_t('current_official_ranking_none', lang))
    
    st.markdown("---")
    
    # --- Podsumowania Tygodniowe (PRZENIESIONE TUTAJ) ---
    max_complete_day = complete_stages[-1] if complete_stages else 0
    weeks_completed = max_complete_day // 7
    
    if weeks_completed > 0:
        for w in range(1, weeks_completed + 1):
            with st.expander(_t('weekly_summary_title', lang, w, w*7), expanded=False):
                summary_md = generate_weekly_summary_markdown(w, current_data, df_historical, df_raw_logs, lang, participants_list)
                st.code(summary_md, language="markdown")
        st.markdown("---")

    # --- Kompletność ---
    st.subheader(_t('current_completeness_header', lang))
    
    pivot_data = []
    completeness_participant_col = _t('completeness_col_participant', lang) 
    for participant in participants_list:
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
            
    if pivot_data:
        df_pivot = pd.DataFrame(pivot_data)
        days_to_show = [day for day in range(1, max_day_reported + 1)]
        completeness_pivot = df_pivot.pivot(
            index=completeness_participant_col, 
            columns=_t('completeness_col_day', lang),
            values="Status"
        ).reindex(columns=days_to_show, fill_value="").reindex(index=sorted(participants_list))
        
        completeness_pivot_display = completeness_pivot.reset_index()
        completeness_pivot_display.columns = completeness_pivot_display.columns.astype(str)
        
        # UŻYWAMY use_container_width ZAMIAST width=None
        st.dataframe(completeness_pivot_display, width="stretch", hide_index=True)
    else:
        st.info(_t('current_completeness_no_data', lang))

    st.subheader(_t('current_stats_header', lang))
    
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"**{_t('current_stats_streaks', lang)}**")
        st.caption(_t('current_stats_streaks_desc', lang))
        df_streaks = calculate_current_stats(current_data, max_day_reported, lang, participants_list)
        if not df_streaks.empty:
            for _, row in df_streaks.iterrows():
                mention(label=f"**{row['Uczestnik']}** ({row['Seria']} {_t('current_stats_streaks_days', lang)})", icon="🔥", url=f"https://hive.blog/@{row['Uczestnik']}")
        else:
            st.info("Brak znaczących serii.")
    
    with col2:
        st.markdown(f"**{_t('stats_rabbits_title', lang)}**")
        st.caption(_t('stats_rabbits_desc', lang))
        df_rabbits = calculate_rabbit_stats(current_data, max_day_reported, elimination_map, lang, participants_list)
        if not df_rabbits.empty:
            for _, row in df_rabbits.iterrows():
                mention(label=f"**{row['Uczestnik']}** ({row['Potknięcia']} wpadek)", icon="🐰", url=f"https://hive.blog/@{row['Uczestnik']}")
        else:
            st.info("Brak wybitnych zająców.")

    st.markdown("---")

    # === NOWY WYKRES WYŚCIGU (RACE CHART) ===
    st.subheader(_t('current_stats_race_header', lang))
    st.info(_t('current_stats_race_desc', lang))
    
    max_axis_day = max(31, max_day_reported)
    
    # Inicjalizacja sesji dla numeru dnia
    if 'race_current_day' not in st.session_state:
        st.session_state.race_current_day = max_day_reported
    
    # Kolumny kontrolne (tytuł, - , dzień, + , przycisk animacji)
    c_label, c_minus, c_input, c_plus, c_anim = st.columns([2, 1, 1, 1, 2])
    
    with c_label:
        mode = st.radio(_t('current_stats_race_mode', lang), (_t('current_stats_race_mode_manual', lang), _t('current_stats_race_mode_anim', lang)), horizontal=True, label_visibility="collapsed")
    
    # Obsługa przycisków +/-
    def decrease_day():
        if st.session_state.race_current_day > 1:
            st.session_state.race_current_day -= 1
            
    def increase_day():
        if st.session_state.race_current_day < max_day_reported:
            st.session_state.race_current_day += 1
            
    with c_minus:
        st.button(_t('race_btn_prev', lang), on_click=decrease_day, use_container_width=True)
    with c_plus:
        st.button(_t('race_btn_next', lang), on_click=increase_day, use_container_width=True)
    with c_input:
        # Input numeryczny, zsynchronizowany z sesją
        st.number_input(_t('race_input_label', lang), min_value=1, max_value=max_day_reported, key='race_current_day', label_visibility="collapsed")
        
    chart_placeholder = st.empty()
    
    # Kolory
    colors = plt.cm.tab20(np.linspace(0, 1, len(participants_list)))
    color_map = {p: colors[i] for i, p in enumerate(sorted(participants_list))}

    def draw_chart(day):
        df_race = get_race_data_for_day(current_data, day, lang, participants_list)
        # Sortujemy - ODWRACAMY ORDER aby A było na górze (dla barh)
        df_race = df_race.sort_index(ascending=False)
        
        fig, ax = plt.subplots(figsize=(10, max(6, len(participants_list)*0.3))) # Wysokość zależna od liczby graczy
        plt.style.use('dark_background')
        ax.set_facecolor('#0e1117')
        fig.patch.set_facecolor('#0e1117')
        
        bars = ax.barh(df_race.index, df_race[_t('current_stats_race_total', lang)], color=[color_map.get(p, 'gray') for p in df_race.index])
        
        ax.set_xlim(0, max_axis_day) 
        # CZYSTY TYTUŁ (bez emotikon)
        ax.set_title(clean_title_for_chart(f"{_t('current_stats_race_day', lang)}: {day}"), color='white')
        ax.tick_params(axis='x', colors='white')
        ax.tick_params(axis='y', colors='white')
        for spine in ax.spines.values():
            spine.set_color('#444444')
        
        # Dodanie wartości na końcu słupka
        for bar in bars:
            width = bar.get_width()
            ax.text(width + 0.5, bar.get_y() + bar.get_height()/2, f'{int(width)}', ha='left', va='center', color='white', fontsize=8)

        plt.tight_layout()
        return fig

    if mode == _t('current_stats_race_mode_anim', lang):
        with c_anim:
            if st.button(_t('current_stats_race_button', lang), type="primary", use_container_width=True):
                # Animacja
                for day in range(1, max_day_reported + 1):
                    fig = draw_chart(day)
                    with chart_placeholder.container():
                        st.pyplot(fig)
                    plt.close(fig)
                    time.sleep(0.1)
                # USUNIĘTO reset stanu sesji tutaj, aby uniknąć błędu StreamlitAPIException
    else:
        # Tryb ręczny - rysujemy dla aktualnego dnia z sesji
        fig = draw_chart(st.session_state.race_current_day)
        with chart_placeholder.container():
            st.pyplot(fig)
        plt.close(fig)

    st.markdown("---")
    
    expander_title = "📉 Pokaż wykres przebiegu rywalizacji (Historia miejsc)" if lang == 'pl' else "📉 Show Competition Progress (Rank History)"
    with st.expander(expander_title):
        show_daily_rank_progression(current_data, complete_stages, lang, participants_list)
        
    show_survival_comparison(current_data, max_day_reported, df_historical, lang, elimination_map, complete_stages, participants_list)
    show_stage_analysis(current_data, max_day_reported, elimination_map, complete_stages, lang, participants_list)

    with st.expander(_t('current_ranking_rules_expander_label', lang)):
        st.markdown(_t('current_ranking_rules', lang, max_day_reported))

    if not df_historical.empty:
        with st.expander(_t('current_ranking_historical_expander', lang)):
            show_historical_context(df_historical, lang, participants_list)
