import streamlit as st
from translations import _t
import pandas as pd
from datetime import date, timedelta, datetime
import pytz
import re
import traceback
import matplotlib.pyplot as plt
import numpy as np

# Importy lokalne
from config import EDITIONS_CONFIG, MONTH_NAMES
from page_form import show_submission_form
from page_current_ranking import show_current_edition_dashboard
from page_historical_stats import show_historical_stats
from google_connect import connect_to_google_sheets
from data_loader import load_google_sheet_data, process_raw_data

# ==============================================================================
# 🎯 KOD GOOGLE ANALYTICS (Bezpośrednie wstawienie)
# ==============================================================================
st.markdown("""
<script async src="https://www.googletagmanager.com/gtag/js?id=G-TV1NG7TEL6"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());

  gtag('config', 'G-TV1NG7TEL6');
</script>
""", unsafe_allow_html=True)
# ==============================================================================


# --- Ustawienia Strony ---
st.set_page_config(
    layout="wide", 
    page_title="Analiza i Zarządzanie Poprzeczką", 
    page_icon="https://raw.githubusercontent.com/racibo/poprzeczka-app/main/logo.png" 
)

# ===== FUNKCJE ADMIN =====

def parse_timestamp_safely(ts_str):
    """Parsuje timestamp ISO format (2025-11-16T00:00:49.929422)"""
    if pd.isna(ts_str) or not ts_str or ts_str == "":
        return None
    
    try:
        ts_str = str(ts_str).strip()
        if 'T' in ts_str:
            return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%d.%m.%Y %H:%M:%S',
            '%d.%m.%Y %H:%M',
            '%Y-%m-%d %H:%M',
            '%m/%d/%Y %H:%M:%S',
        ]
        for fmt in formats:
            try:
                return datetime.strptime(ts_str, fmt)
            except ValueError:
                continue
    except Exception:
        pass
    return None

def format_timestamp_with_timezone(dt_obj, timezone='Europe/Warsaw'):
    """Formatuje datetime do formatu: 16.11 09:48"""
    if dt_obj is None:
        return "—"
    try:
        if dt_obj.tzinfo is None:
            dt_obj = pytz.UTC.localize(dt_obj)
        tz = pytz.timezone(timezone)
        local_dt = dt_obj.astimezone(tz)
        return local_dt.strftime('%d.%m %H:%M')
    except Exception as e:
        return "—"

def show_admin_panel_expanded(lang='pl', sheet=None, edition_key='november'):
    """Wyświetla panel administratora w rozwijalnym menu Log."""
    
    if not sheet:
        st.error("Nie można połączyć się z Google Sheets")
        return
    
    try:
        df_logs = load_google_sheet_data(sheet, "LogWpisow")
    except Exception as e:
        st.error(f"Błąd ładowania logów: {e}")
        return
    
    if df_logs.empty:
        st.info("Brak wpisów w logach")
        return
    
    # === NAZWA EDYCJI ===
    edition_name = MONTH_NAMES.get(edition_key, {}).get(lang, 'Edycja')
    
    # === OSTATNIE WPISY (ZMODYFIKOWANA TABELA) ===
    st.subheader("📝 Ostatnie 30 wpisów:")
    
    df_log_recent = df_logs.copy()
    if 'Timestamp' in df_log_recent.columns:
        df_log_recent['Timestamp_parsed'] = df_log_recent['Timestamp'].apply(parse_timestamp_safely)
        df_log_recent = df_log_recent.sort_values('Timestamp_parsed', ascending=False, na_position='last')
    
    df_display = df_log_recent.head(30).copy()
    
    if 'Timestamp' in df_display.columns:
        df_display['Timestamp'] = df_display['Timestamp'].apply(
            lambda x: format_timestamp_with_timezone(parse_timestamp_safely(x), 'Europe/Warsaw')
        )
    
    notes_col = 'Notatki'
    if notes_col not in df_display.columns and 'Notes' in df_display.columns:
        notes_col = 'Notes'
        
    target_cols = ['Participant', 'Submitter', 'Timestamp', 'Day', 'Status', notes_col]
    available_cols = [col for col in target_cols if col in df_display.columns]
    
    st.dataframe(
        df_display[available_cols],
        width="stretch", 
        hide_index=True,
        height=600,
        column_config={
            "Timestamp": st.column_config.TextColumn("Czas", width="medium"),
            "Participant": st.column_config.TextColumn("Uczestnik", width="medium"),
            "Submitter": st.column_config.TextColumn("Zgłaszający", width="medium"),
            "Day": st.column_config.TextColumn("Dzień", width="small"),
            "Status": st.column_config.TextColumn("Status", width="small"),
            notes_col: st.column_config.TextColumn("Notatki", width="large"),
        }
    )
    
    st.markdown("---")
        
    # === DYNAMIKA WPROWADZANIA DANYCH - WYKRES ===
    st.subheader("📊 Dynamika Pomocy")
    
    df_chart = df_logs.copy()
    if 'Timestamp' in df_chart.columns:
        df_chart['Timestamp_parsed'] = df_chart['Timestamp'].apply(parse_timestamp_safely)
        df_chart = df_chart.dropna(subset=['Timestamp_parsed'])
        df_chart['Date'] = df_chart['Timestamp_parsed'].apply(lambda x: x.date())
    else:
        st.warning("Brak kolumny Timestamp.")
        return

    df_chart['IsHelper'] = df_chart['Submitter'].apply(lambda x: 0 if 'Admin' in str(x) else 1)
    
    daily_stats = df_chart.groupby('Date').agg(
        TotalEntries=('Participant', 'count'),
        HelperEntries=('IsHelper', 'sum')
    ).sort_index()
    
    if not daily_stats.empty:
        def calculate_rolling_pct(df, window):
            rolled_helpers = df['HelperEntries'].rolling(window=window, min_periods=1).sum()
            rolled_total = df['TotalEntries'].rolling(window=window, min_periods=1).sum()
            return (rolled_helpers / rolled_total.replace(0, 1) * 100).fillna(0)

        daily_stats['Pct_Daily'] = (daily_stats['HelperEntries'] / daily_stats['TotalEntries'].replace(0, 1) * 100).fillna(0)
        daily_stats['Pct_2Day'] = calculate_rolling_pct(daily_stats, window=2)
        daily_stats['Pct_7Day'] = calculate_rolling_pct(daily_stats, window=7)
        daily_stats['Pct_30Day'] = calculate_rolling_pct(daily_stats, window=30)
        
        daily_stats['Cum_Helpers'] = daily_stats['HelperEntries'].cumsum()
        daily_stats['Cum_Total'] = daily_stats['TotalEntries'].cumsum()
        daily_stats['Pct_AllTime'] = (daily_stats['Cum_Helpers'] / daily_stats['Cum_Total'].replace(0, 1) * 100).fillna(0)
        
        fig, ax = plt.subplots(figsize=(12, 6))
        plt.style.use('dark_background')
        ax.set_facecolor('#0e1117')
        fig.patch.set_facecolor('#0e1117')
        
        dates = daily_stats.index
        ax.plot(dates, daily_stats['Pct_Daily'], label='Dzień (Daily)', color='#88FFFF', alpha=0.5, linewidth=1, linestyle=':')
        ax.plot(dates, daily_stats['Pct_2Day'], label='2 Dni (Rolling)', color='#00d9ff', linewidth=1.5, linestyle='--')
        ax.plot(dates, daily_stats['Pct_7Day'], label='Tydzień (7 days)', color='#00ff9d', linewidth=2)
        ax.plot(dates, daily_stats['Pct_30Day'], label='Miesiąc (30 days)', color='#ffcc00', linewidth=2)
        ax.plot(dates, daily_stats['Pct_AllTime'], label='Od początku (All time)', color='#ff0055', linewidth=3)
        
        ax.set_ylim(0, 105)
        ax.set_ylabel("% Pomocy", color='white')
        ax.set_xlabel("Data", color='white')
        ax.legend(loc='upper left', frameon=True, facecolor='#262730', edgecolor='white')
        ax.grid(color='#444444', linestyle='--', linewidth=0.5, alpha=0.5)
        ax.tick_params(colors='white')
        for spine in ax.spines.values():
            spine.set_color('#444444')
            
        st.pyplot(fig)

    st.markdown("---")
    
    st.subheader("📈 Statystyki Ogólne")
    
    total_entries = len(df_logs)
    admin_count = len(df_logs[df_logs['Submitter'].str.contains('Admin', case=False, na=False)]) if 'Submitter' in df_logs.columns else 0
    helper_count = total_entries - admin_count
    helper_pct_all = int((helper_count / total_entries * 100)) if total_entries > 0 else 0
    unique_helpers = df_logs[~df_logs['Submitter'].str.contains('Admin', case=False, na=False)]['Submitter'].nunique() if 'Submitter' in df_logs.columns else 0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Razem wpisów", total_entries)
    col2.metric("% od Pomocników", f"{helper_pct_all}%")
    col3.metric("Wpisy Admina", admin_count)
    col4.metric("Aktywni Pomocnicy", unique_helpers)

def check_if_edition_is_finished(sheet, edition_key):
    """Sprawdza czy edycja jest zakończona."""
    try:
        cfg = EDITIONS_CONFIG.get(edition_key)
        if not cfg: return False
        
        sheet_name = cfg['sheet_name']
        participants_list = cfg['participants']
        df_raw = load_google_sheet_data(sheet, sheet_name)
        if df_raw.empty: return False
        
        expected_cols = ['Participant', 'Day', 'Status']
        current_data, max_day, success = process_raw_data(df_raw, 'pl', expected_cols, sheet_name)
        
        if not success or max_day == 0: return False
        
        from page_current_ranking import calculate_ranking
        _, elimination_map = calculate_ranking(current_data, max_day, 'pl', participants_list, ranking_type='live')
        
        eliminated_count = sum(1 for p in participants_list if elimination_map.get(p) is not None)
        return eliminated_count == len(participants_list)
        
    except Exception:
        return False

def main():
    """Główna funkcja renderująca aplikację Streamlit."""
    
    sheet = connect_to_google_sheets()

    # === 1. INICJALIZACJA I STATUSY EDYCJI ===
    TODAY = date.today()
    edition_statuses = {}
    
    for key, cfg in EDITIONS_CONFIG.items():
        start_date = cfg['start_date']
        start_month = start_date.month
        start_year = start_date.year
        today_month = TODAY.month
        today_year = TODAY.year
        
        status = 'UNKNOWN'
        icon = '❓'
        
        if start_year > today_year or (start_year == today_year and start_month > today_month):
            status = 'UPCOMING'
            icon = '⏳'
        elif start_year < today_year or (start_year == today_year and start_month <= today_month):
            months_since_start = (today_year - start_year) * 12 + (today_month - start_month)
            if start_month == today_month and start_year == today_year:
                status = 'ACTIVE'
                icon = '🟢'
            elif (start_year == today_year and start_month == today_month - 1) or (start_year == today_year - 1 and start_month == 12 and today_month == 1):
                status = 'FINALIZATION'
                icon = '🚩'
            else:
                status = 'FINISHED'
                icon = '🏁'
            
            if cfg.get('is_manually_closed', False):
                status = 'FINISHED'
                icon = '🏁'
        
        edition_statuses[key] = {'status': status, 'icon': icon}
    
    VISIBLE_EDITIONS_KEYS = [k for k, v in EDITIONS_CONFIG.items() if not v.get('is_hidden', False)] 
    
    default_nav_key = "nav_historical_stats"
    active_edition_key = None
    for key, status_data in edition_statuses.items():
        if status_data['status'] == 'ACTIVE':
            active_edition_key = key
            break
    
    if active_edition_key:
        default_nav_key = f"nav_{active_edition_key}_ranking"
    else:
        for key, status_data in edition_statuses.items():
            if status_data['status'] == 'FINALIZATION':
                default_nav_key = f"nav_{key}_ranking"
                break

    # === 3. DEEP LINKING ===
    query_params = st.query_params
    
    if "page" in query_params or "edition" in query_params or "lang" in query_params:
        url_page = query_params.get('page', 'ranking')[0].lower() if isinstance(query_params.get('page'), list) else query_params.get('page', 'ranking').lower()
        url_edition = query_params.get('edition', 'listopad')[0].lower() if isinstance(query_params.get('edition'), list) else query_params.get('edition', 'listopad').lower()
        url_lang = query_params.get('lang', 'pl')[0].lower() if isinstance(query_params.get('lang'), list) else query_params.get('lang', 'pl').lower()
        
        if url_lang in ['pl', 'en']:
            st.session_state.lang_select = url_lang

        edition_mapping = {cfg['url_param_pl']: key for key, cfg in MONTH_NAMES.items()}
        edition_mapping.update({cfg['url_param_en']: key for key, cfg in MONTH_NAMES.items()})
        
        edition_key_from_url = edition_mapping.get(url_edition)
        
        if edition_key_from_url:
            if url_page == 'ranking':
                if edition_statuses.get(edition_key_from_url, {}).get('status') == 'UPCOMING':
                    st.session_state.nav_selection = "nav_historical_stats"
                else:
                    st.session_state.nav_selection = f"nav_{edition_key_from_url}_ranking"
            elif url_page == 'formularz':
                if edition_statuses.get(edition_key_from_url, {}).get('status') != 'ACTIVE':
                    st.session_state.nav_selection = f"nav_{edition_key_from_url}_ranking"
                else:
                    st.session_state.nav_selection = f"nav_{edition_key_from_url}_form"
            else:
                st.session_state.nav_selection = default_nav_key
        else:
            st.session_state.nav_selection = default_nav_key
    
    if 'nav_selection' not in st.session_state:
        st.session_state.nav_selection = default_nav_key
    
    if 'lang_select' not in st.session_state:
        st.session_state.lang_select = 'pl'
    
    lang = st.session_state.lang_select
    
    # Inicjalizacja sesji
    if 'race_current_day' not in st.session_state: st.session_state.race_current_day = 1
    if 'animate_charts' not in st.session_state: st.session_state.animate_charts = False
    if 'success_message_key' not in st.session_state: st.session_state.success_message_key = None
    if 'submitter_index_plus_one' not in st.session_state: st.session_state.submitter_index_plus_one = 0 
    if 'last_day_entered' not in st.session_state: st.session_state.last_day_entered = 1

    # === PASEK BOCZNY ===
    st.sidebar.selectbox("Język / Language", ["pl", "en"], index=0 if lang == 'pl' else 1, key="lang_select")
    lang = st.session_state.lang_select
    
    st.sidebar.markdown("---\n")
    st.sidebar.title(_t('nav_header', lang)) 

    # === MENU EDYCJE ===
    with st.sidebar.expander(_t('nav_editions_expander', lang), expanded=True):
        for key in VISIBLE_EDITIONS_KEYS:
            status_data = edition_statuses.get(key, {})
            status = status_data.get('status', 'UNKNOWN')
            icon = status_data.get('icon', '❓')
            
            month_label = MONTH_NAMES[key]['pl'] if lang == 'pl' else MONTH_NAMES[key]['en']
            
            st.markdown(f"**{icon} {month_label}**")
            col1, col2 = st.columns(2)
            
            if status == 'UPCOMING':
                with col1:
                    if st.button(f"{_t('nav_edition_ranking_upcoming', lang, month_label)}", key=f"btn_{key}_ranking", use_container_width=True):
                        st.session_state.nav_selection = f"nav_{key}_ranking"
                        st.rerun()
                with col2:
                    if st.button(f"{_t('nav_edition_form_active', lang, month_label)}", key=f"btn_{key}_form", use_container_width=True):
                        st.session_state.nav_selection = f"nav_{key}_form"
                        st.rerun()
            
            elif status == 'ACTIVE':
                with col1:
                    if st.button(f"{_t('nav_edition_ranking_active', lang, month_label)}", key=f"btn_{key}_ranking", use_container_width=True):
                        st.session_state.nav_selection = f"nav_{key}_ranking"
                        st.rerun()
                with col2:
                    if st.button(f"{_t('nav_edition_form_active', lang, month_label)}", key=f"btn_{key}_form", use_container_width=True):
                        st.session_state.nav_selection = f"nav_{key}_form"
                        st.rerun()
            
            elif status == 'FINALIZATION':
                with col1:
                    if st.button(f"{_t('nav_edition_ranking_active', lang, month_label)}", key=f"btn_{key}_ranking", use_container_width=True):
                        st.session_state.nav_selection = f"nav_{key}_ranking"
                        st.rerun()
                with col2:
                    if st.button(f"{_t('nav_edition_form_active', lang, month_label)}", key=f"btn_{key}_form", use_container_width=True):
                        st.session_state.nav_selection = f"nav_{key}_form"
                        st.rerun()

            elif status == 'FINISHED':
                with col1:
                    if st.button(f"{_t('nav_edition_ranking_finished', lang, month_label)}", key=f"btn_{key}_ranking", use_container_width=True):
                        st.session_state.nav_selection = f"nav_{key}_ranking"
                        st.rerun()
                with col2:
                    if st.button(f"{_t('nav_edition_form_finished', lang, month_label)}", key=f"btn_{key}_form", use_container_width=True):
                        st.session_state.nav_selection = f"nav_{key}_form"
                        st.rerun()
            st.divider()

    st.sidebar.markdown("---\n")

    # === MENU STATYCZNE ===
    st.sidebar.subheader(_t('nav_static_header', lang))
    static_buttons = [
        (_t('nav_historical_stats', lang), 'nav_historical_stats'),
        (_t('nav_rules', lang), 'nav_rules'),
        (_t('nav_join', lang), 'nav_join'),
        (_t('about_app', lang), 'about_app'),
    ]
    
    for label, key in static_buttons:
        if st.sidebar.button(label, key=f"btn_{key}", use_container_width=True):
            st.session_state.nav_selection = key
            st.rerun()
            
    # === LOG ADMIN ===
    helper_percentage_all = 0
    helper_percentage_recent = 0
    if sheet:
        try:
            df_log = load_google_sheet_data(sheet, "LogWpisow")
            if not df_log.empty:
                total_entries_all = len(df_log)
                admin_entries_all = len(df_log[df_log['Submitter'] == 'poprzeczka (Admin)']) if 'Submitter' in df_log.columns else 0
                helper_entries_all = total_entries_all - admin_entries_all
                helper_percentage_all = int((helper_entries_all / total_entries_all * 100)) if total_entries_all > 0 else 0
                
                df_log_recent_200 = df_log.iloc[-200:].copy()
                total_entries_recent = len(df_log_recent_200)
                admin_entries_recent = len(df_log_recent_200[df_log_recent_200['Submitter'] == 'poprzeczka (Admin)']) if 'Submitter' in df_log_recent_200.columns else 0
                helper_entries_recent = total_entries_recent - admin_entries_recent
                helper_percentage_recent = int((helper_entries_recent / total_entries_recent * 100)) if total_entries_recent > 0 else 0
        except:
            pass
    
    log_title = f"📋 Log (Admin) - Pomoc: {helper_percentage_all}% ({helper_percentage_recent}% z ost. 200)"
    with st.sidebar.expander(log_title, expanded=False):
        admin_edition_key = active_edition_key if active_edition_key else 'december'
        show_admin_panel_expanded(lang=lang, sheet=sheet, edition_key=admin_edition_key)
        
    st.sidebar.markdown("---\n")

    # === ROUTING ===
    
    if 'nav_selection' not in st.session_state:
        st.session_state.nav_selection = 'nav_december_ranking' 

    match_edition = re.match(r"nav_(\w+?)_(ranking|form)$", st.session_state.nav_selection)

    if match_edition:
        edition_key, page_type = match_edition.groups()
        
        if page_type == 'ranking':
            show_current_edition_dashboard(lang, edition_key=edition_key)
        
        elif page_type == 'form':
            status_info = edition_statuses.get(edition_key, {})
            status = status_info.get('status', 'UNKNOWN')
            is_form_open = status in ['ACTIVE', 'FINALIZATION', 'UPCOMING']
            show_submission_form(lang, edition_key=edition_key, is_active=is_form_open)

    elif st.session_state.nav_selection == 'nav_historical_stats':
        show_historical_stats(lang)
        
    elif st.session_state.nav_selection == 'nav_rules':
        st.header(_t('sidebar_rules_header', lang))
        st.markdown(_t('sidebar_rules_text', lang))
        
    elif st.session_state.nav_selection == 'nav_join':
        st.header(_t('nav_join', lang))
        st.info(_t('join_intro', lang))
        st.markdown(f"""
        1. {_t('join_step_1', lang)}
        2. {_t('join_step_2', lang)}
        3. {_t('join_step_3', lang)}
        4. {_t('join_step_4', lang)}
        """)
        
    elif st.session_state.nav_selection == 'admin_panel':
        show_admin_panel_expanded(lang=lang, sheet=sheet)

    elif st.session_state.nav_selection == 'about_app':
        st.header(_t('about_app', lang))
        st.markdown(_t('about_app_text', lang))

    # === SZYBKIE LINKI (Zagnieżdżone w MAIN) ===
    st.subheader(_t('quick_links_header', lang))
    BASE_URL = "https://poprzeczka.streamlit.app/" 
            
    st.markdown(f"""
    Poniższe linki otwierają stronę główną w wybranym języku. 
    Aplikacja automatycznie załaduje aktualną edycję.
    """)
            
    link_pl = f"{BASE_URL}?lang=pl"
    link_en = f"{BASE_URL}?lang=en"
            
    st.markdown(f"🇵🇱 **Polska wersja:** [{link_pl}]({link_pl})")
    st.markdown(f"🇬🇧 **English version:** [{link_en}]({link_en})")

    # Linki do formularza obecnej edycji
    active_key_links = None
    for key, status_data in edition_statuses.items():
        if status_data['status'] == 'ACTIVE':
            active_key_links = key
            break
            
    if active_key_links:
        st.markdown("---")
        st.markdown(f"📝 **Szybki dostęp do formularza (Obecna edycja):**")
        p_pl = MONTH_NAMES[active_key_links]['url_param_pl']
        p_en = MONTH_NAMES[active_key_links]['url_param_en']
        
        form_pl = f"{BASE_URL}?page=formularz&edition={p_pl}&lang=pl"
        form_en = f"{BASE_URL}?page=formularz&edition={p_en}&lang=en"
        
        st.markdown(f"- [Formularz PL]({form_pl})")
        st.markdown(f"- [Form EN]({form_en})")

    st.markdown("---\n")
    st.markdown(f"**URL do wklejenia** (Link do strony startowej):")
    st.code(BASE_URL)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        st.error(f"Błąd: {e}")
        st.code(traceback.format_exc())
