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
# 🎯 KOD GOOGLE ANALYTICS
# Wklejamy cały fragment z GA4, używając bloku markdown
# ==============================================================================
GA_CODE = """
<script async src="https://www.googletagmanager.com/gtag/js?id=G-TV1NG7TEL6"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());

  gtag('config', 'G-TV1NG7TEL6');
</script>
"""
# Dodaj kod Analytics do strony używając niebezpiecznego HTML
st.markdown(GA_CODE, unsafe_allow_html=True)
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
        # Obsługuj format ISO (z T i bez strefy czasowej)
        ts_str = str(ts_str).strip()
        # Jeśli ma T, to ISO format
        if 'T' in ts_str:
            return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        # Spróbuj inne formaty
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

def format_timestamp_with_timezone(dt_obj, timezone='UTC'):
    if dt_obj is None:
        return "—"
    try:
        if dt_obj.tzinfo is None:
            dt_obj = pytz.UTC.localize(dt_obj)
        tz = pytz.timezone(timezone)
        local_dt = dt_obj.astimezone(tz)
        return f"{local_dt.strftime('%d.%m.%Y %H:%M:%S')} ({timezone})"
    except Exception:
        return str(dt_obj)

def get_available_timezones():
    return ['UTC', 'Europe/Warsaw', 'Europe/Berlin', 'Europe/London', 'Europe/Paris', 
            'Europe/Amsterdam', 'America/New_York', 'America/Los_Angeles', 'Asia/Tokyo', 'Asia/Bangkok']

def generate_admin_social_post(lang, edition_label, max_day_reported, selected_participants, 
                               df_historical, df_logs, participants_list, include_date=True, 
                               include_stats=True, include_participants=True, include_helpers=False, 
                               include_cta=True):
    md = ""
    title = f"Raport etapu {max_day_reported} - {edition_label}" if lang == 'pl' else f"Stage {max_day_reported} Report - {edition_label}"
    md += f"# {title}\n\n"
    
    if include_date:
        now = datetime.now()
        md += f"📅 **Opublikowano:** {now.strftime('%d.%m.%Y o %H:%M')}\n\n" if lang == 'pl' else f"📅 **Published:** {now.strftime('%m/%d/%Y at %H:%M')}\n\n"
    
    if include_participants and selected_participants:
        mentions = " ".join([f"@{p}" for p in selected_participants])
        md += f"🎯 **Uczestnicy w raporcie:** {mentions}\n\n" if lang == 'pl' else f"🎯 **Featured Participants:** {mentions}\n\n"
    
    if include_stats:
        active_count = len(selected_participants) if selected_participants else 0
        total_count = len(participants_list)
        md += f"## 📊 Podsumowanie Etapu {max_day_reported}\n\n- **Uczestników w raporcie:** {active_count}/{total_count}\n" if lang == 'pl' else f"## 📊 Stage {max_day_reported} Summary\n\n- **Participants Reported:** {active_count}/{total_count}\n"
        
        if not df_logs.empty:
            recent_logs = df_logs[df_logs['Day'].astype(str) == str(max_day_reported)]
            passed_count = len(recent_logs[recent_logs['Status'].str.strip() == 'Zaliczone']) if not recent_logs.empty else 0
            md += f"- **Zaliczyli etap:** {passed_count}\n" if lang == 'pl' else f"- **Passed:** {passed_count}\n"
        md += "\n"
    
    if include_helpers and not df_logs.empty:
        helpers = df_logs[df_logs['Submitter'] != 'poprzeczka (Admin)']['Submitter'].unique()
        if len(helpers) > 0:
            helpers_str = ", ".join(helpers)
            md += f"## 🙋 Dziękujemy\n\nDziękujemy za pomoc w zbieraniu danych: {helpers_str}\n\n" if lang == 'pl' else f"## 🙋 Thanks\n\nThanks for helping with data collection: {helpers_str}\n\n"
    
    if include_cta:
        md += "---\n\n## 📝 Chcesz Wziąć Udział?\n\nWypełnij formularz i dołącz do POPRZECZKI!\n\n" if lang == 'pl' else "---\n\n## 📝 Want to Participate?\n\nFill out the form and join POPRZECZKA!\n\n"
    
    md += "\n#poprzeczka #hive #raport #etap #wyzwanie" if lang == 'pl' else "\n#poprzeczka #hive #report #stage #challenge"
    return md
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
    
    # Definicja pożądanej kolejności kolumn
    # Próbujemy znaleźć kolumnę "Notatki" lub "Notes", jeśli nazwa jest inna
    notes_col = 'Notatki'
    if notes_col not in df_display.columns and 'Notes' in df_display.columns:
        notes_col = 'Notes'
        
    target_cols = ['Participant', 'Submitter', 'Timestamp', 'Day', 'Status', notes_col]
    
    # Wybieramy tylko te kolumny, które faktycznie istnieją w danych
    available_cols = [col for col in target_cols if col in df_display.columns]
    
    st.dataframe(
        df_display[available_cols],
        # Zmieniono 'width=None' na 'width="stretch"'
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
    
    # === GENERATOR POSTÓW ===
    st.subheader("📱 Generator Postów na Media")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Wybór dnia
        if 'Day' in df_logs.columns:
            editions_list = sorted(df_logs['Day'].unique())
        else:
            editions_list = []

        if editions_list:
            selected_day = st.selectbox(
                f"📅 Etap (dzień) do raportu - {edition_name}:",
                options=editions_list,
                index=len(editions_list) - 1,
                key="post_edition_admin"
            )
        else:
            st.warning("Brak danych w logach")
            selected_day = 1
        
        # Język
        post_lang = st.radio(
            "Język:",
            options=["Polski", "English"],
            horizontal=True,
            key="post_lang_admin_expanded"
        )
        post_lang_key = 'pl' if post_lang == "Polski" else 'en'
    
    with col2:
        st.markdown("**Zawartość posta:**")
        include_date = st.checkbox("📅 Data", value=True, key="inc_date")
        include_ranking = st.checkbox("🏆 Klasyfikacja", value=True, key="inc_ranking")
        include_stats = st.checkbox("📊 Statystyki", value=True, key="inc_stats")
        include_helpers = st.checkbox("🙋 Dziękowanie pomocnikom", value=False, key="inc_help")
    
    st.divider()
    
    # === PRZYCISK GENEROWANIA ===
    if st.button("✨ Generuj Post dla Etapu " + str(selected_day), type="primary", use_container_width=True):
        df_selected_stage = df_logs[df_logs['Day'].astype(str) == str(selected_day)]
        
        # === OBLICZ RANKING (OFICJALNY) ===
        try:
            cfg = EDITIONS_CONFIG.get(edition_key, EDITIONS_CONFIG.get('november', {}))
            sheet_name = cfg.get('sheet_name', '')
            participants_list = cfg.get('participants', [])
            
            df_raw_data = load_google_sheet_data(sheet, sheet_name)
            if not df_raw_data.empty:
                expected_cols = ['Participant', 'Day', 'Status']
                current_data, max_day, _ = process_raw_data(df_raw_data, post_lang_key, expected_cols, sheet_name)
                
                from page_current_ranking import calculate_ranking
                ranking_df, elimination_map = calculate_ranking(current_data, int(selected_day), post_lang_key, participants_list, ranking_type='official')
            else:
                ranking_df = pd.DataFrame()
        except:
            ranking_df = pd.DataFrame()
        
        # === GENERUJ TREŚĆ POSTA ===
        md = f"# Raport Etapu {selected_day} - {edition_name}\n\n"
        
        if include_date:
            now = datetime.now()
            md += f"📅 **{now.strftime('%d.%m.%Y o %H:%M')}**\n\n"
        
        if include_ranking and not ranking_df.empty:
            md += "## 🏆 Klasyfikacja\n\n"
            participant_col = _t('ranking_col_participant', post_lang_key)
            rank_col = _t('ranking_col_rank', post_lang_key)
            highest_col = _t('ranking_col_highest_pass', post_lang_key)
            
            top_5 = ranking_df.head(5)
            for idx, row in top_5.iterrows():
                rank = row[rank_col]
                participant = row[participant_col]
                highest = row[highest_col]
                md += f"{rank}. [@{participant}](https://hive.blog/@{participant}) - Etap: {highest}\n"
            md += "\n"
        
        if include_stats:
            cfg = EDITIONS_CONFIG.get(edition_key, {})
            total_participants = len(cfg.get('participants', [])) if cfg else 0
            passed = len(df_selected_stage[df_selected_stage['Status'].str.strip() == 'Zaliczone'])
            
            md += "## 📊 Statystyki Etapu\n\n"
            md += f"- **Uczestników w edycji:** {total_participants}\n"
            md += f"- **Zaliczyli etap:** {passed}\n"
            if total_participants > 0:
                md += f"- **Procent sukcesu:** {int((passed/total_participants)*100)}%\n"
            md += "\n"
        
        if include_helpers:
            helpers = df_selected_stage[~df_selected_stage['Submitter'].str.contains('Admin', case=False, na=False)]['Submitter'].unique()
            if len(helpers) > 0:
                md += "## 🙋 Dziękujemy\n\n"
                helpers_str = ", ".join(helpers)
                md += f"Dziękujemy za pomoc w zbieraniu danych: {helpers_str}\n\n"
        
        md += "---\n\n#poprzeczka #hive #raport #etap"
        
        st.session_state.admin_generated_post = md
        st.session_state.admin_post_edited = md
        st.rerun()
    
    # === EDYCJA I WYŚWIETLANIE POSTA ===
    if 'admin_generated_post' not in st.session_state:
        st.session_state.admin_generated_post = ""
    if 'admin_post_edited' not in st.session_state:
        st.session_state.admin_post_edited = ""
    
    if st.session_state.admin_generated_post:
        st.markdown("---")
        st.subheader("✏️ Edycja i podgląd")
        
        edited_content = st.text_area(
            "Post:",
            value=st.session_state.admin_post_edited,
            height=250,
            key="admin_post_textarea_expanded"
        )
        if edited_content != st.session_state.admin_post_edited:
            st.session_state.admin_post_edited = edited_content
        
        col_preview, col_copy = st.columns(2)
        with col_preview:
            with st.expander("👁️ Podgląd HTML"):
                st.markdown(st.session_state.admin_post_edited)
        with col_copy:
            st.info("📋 Skopiuj (Ctrl+C)")
            st.code(st.session_state.admin_post_edited, language="markdown")
    
    st.markdown("---")
    
    # === DYNAMIKA WPROWADZANIA DANYCH - NOWY WYKRES LINIOWY ===
    st.subheader("📊 Dynamika Pomocy (Wykres w Czasie)")
    
    # 1. Przygotowanie danych
    df_chart = df_logs.copy()
    if 'Timestamp' in df_chart.columns:
        df_chart['Timestamp_parsed'] = df_chart['Timestamp'].apply(parse_timestamp_safely)
        # Usuń wiersze bez daty
        df_chart = df_chart.dropna(subset=['Timestamp_parsed'])
        df_chart['Date'] = df_chart['Timestamp_parsed'].apply(lambda x: x.date())
    else:
        st.warning("Brak kolumny Timestamp do wygenerowania wykresu.")
        return

    # Oznaczamy czy wpis jest od pomocnika (nie Admin)
    # Zakładamy, że admin to 'poprzeczka (Admin)' lub zawiera 'Admin'
    df_chart['IsHelper'] = df_chart['Submitter'].apply(
        lambda x: 0 if 'Admin' in str(x) else 1
    )
    
    # Agregacja dzienna
    daily_stats = df_chart.groupby('Date').agg(
        TotalEntries=('Participant', 'count'),
        HelperEntries=('IsHelper', 'sum')
    ).sort_index()
    
    if daily_stats.empty:
        st.info("Za mało danych do wygenerowania wykresu.")
    else:
        # Funkcja pomocnicza do obliczania procentu na oknach (Rolling Sum Helpers / Rolling Sum Total)
        # Nie można robić średniej z procentów dziennych, trzeba sumować liczniki i mianowniki.
        def calculate_rolling_pct(df, window):
            rolled_helpers = df['HelperEntries'].rolling(window=window, min_periods=1).sum()
            rolled_total = df['TotalEntries'].rolling(window=window, min_periods=1).sum()
            # Unikamy dzielenia przez zero
            return (rolled_helpers / rolled_total.replace(0, 1) * 100).fillna(0)

        # 2. Obliczanie serii danych
        # A. Pomoc w danym dniu
        daily_stats['Pct_Daily'] = (daily_stats['HelperEntries'] / daily_stats['TotalEntries'].replace(0, 1) * 100).fillna(0)
        
        # B. Ostatnie 2 dni (Rolling 2)
        daily_stats['Pct_2Day'] = calculate_rolling_pct(daily_stats, window=2)
        
        # C. Ostatni tydzień (Rolling 7)
        daily_stats['Pct_7Day'] = calculate_rolling_pct(daily_stats, window=7)
        
        # D. Ostatni miesiąc (Rolling 30)
        daily_stats['Pct_30Day'] = calculate_rolling_pct(daily_stats, window=30)
        
        # E. Od początku (Cumulative)
        daily_stats['Cum_Helpers'] = daily_stats['HelperEntries'].cumsum()
        daily_stats['Cum_Total'] = daily_stats['TotalEntries'].cumsum()
        daily_stats['Pct_AllTime'] = (daily_stats['Cum_Helpers'] / daily_stats['Cum_Total'].replace(0, 1) * 100).fillna(0)
        
        # 3. Rysowanie Wykresu
        fig, ax = plt.subplots(figsize=(12, 6))
        plt.style.use('dark_background')
        ax.set_facecolor('#0e1117')
        fig.patch.set_facecolor('#0e1117')
        
        dates = daily_stats.index
        
        # Rysowanie linii z różnymi stylami
        ax.plot(dates, daily_stats['Pct_Daily'], label='Dzień (Daily)', color='#88FFFF', alpha=0.5, linewidth=1, linestyle=':')
        ax.plot(dates, daily_stats['Pct_2Day'], label='2 Dni (Rolling)', color='#00d9ff', linewidth=1.5, linestyle='--')
        ax.plot(dates, daily_stats['Pct_7Day'], label='Tydzień (7 days)', color='#00ff9d', linewidth=2)
        ax.plot(dates, daily_stats['Pct_30Day'], label='Miesiąc (30 days)', color='#ffcc00', linewidth=2)
        ax.plot(dates, daily_stats['Pct_AllTime'], label='Od początku (All time)', color='#ff0055', linewidth=3)
        
        # Formatowanie
        ax.set_ylim(0, 105)
        ax.set_ylabel("% Pomocy (Entries form Helpers)", color='white')
        ax.set_xlabel("Data", color='white')
        ax.set_title("Dynamika Zaangażowania Społeczności", color='white', fontsize=14, fontweight='bold')
        
        # Legenda
        ax.legend(loc='upper left', frameon=True, facecolor='#262730', edgecolor='white')
        
        # Siatka i kolory osi
        ax.grid(color='#444444', linestyle='--', linewidth=0.5, alpha=0.5)
        ax.tick_params(axis='x', colors='white', rotation=45)
        ax.tick_params(axis='y', colors='white')
        for spine in ax.spines.values():
            spine.set_color('#444444')
            
        st.pyplot(fig)

    st.markdown("---")
    
    # === STATYSTYKI GŁÓWNE (LICZBY) ===
    st.subheader("📈 Statystyki Ogólne")
    
    total_entries = len(df_logs)
    admin_count = len(df_logs[df_logs['Submitter'].str.contains('Admin', case=False, na=False)]) if 'Submitter' in df_logs.columns else 0
    helper_count = total_entries - admin_count
    helper_pct_all = int((helper_count / total_entries * 100)) if total_entries > 0 else 0
    unique_helpers = df_logs[~df_logs['Submitter'].str.contains('Admin', case=False, na=False)]['Submitter'].nunique() if 'Submitter' in df_logs.columns else 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Razem wpisów", total_entries)
    
    with col2:
        st.metric("% od Pomocników (Total)", f"{helper_pct_all}%")
    
    with col3:
        st.metric("Wpisy Admina", admin_count)
    
    with col4:
        st.metric("Aktywni Pomocnicy", unique_helpers)
def check_if_edition_is_finished(sheet, edition_key):
    """
    Sprawdza czy edycja jest zakończona (wszyscy uczestnicy odpadli).
    Zwraca True jeśli wszystkich uczestników eliminowano.
    """
    try:
        cfg = EDITIONS_CONFIG.get(edition_key)
        if not cfg:
            return False
            
        sheet_name = cfg['sheet_name']
        participants_list = cfg['participants']
        
        # Ładujemy dane
        df_raw = load_google_sheet_data(sheet, sheet_name)
        if df_raw.empty:
            return False
        
        # Przetwarzamy dane
        expected_cols = ['Participant', 'Day', 'Status']
        current_data, max_day, success = process_raw_data(df_raw, 'pl', expected_cols, sheet_name)
        
        if not success or max_day == 0:
            return False
        
        # Liczymy eliminacje (3 z rzędu porażek)
        from page_current_ranking import calculate_ranking
        _, elimination_map = calculate_ranking(current_data, max_day, 'pl', participants_list, ranking_type='live')
        
        # Jeśli wszyscy są w mapie eliminacji, to edycja zakończona
        eliminated_count = sum(1 for p in participants_list if elimination_map.get(p) is not None)
        
        return eliminated_count == len(participants_list)
        
    except Exception:
        return False

def main():
    """Główna funkcja renderująca aplikację Streamlit."""
    
    # Połączenie do Google Sheets
    sheet = connect_to_google_sheets()

    # === 1. INICJALIZACJA I STATUSY EDYCJI ===
    TODAY = date.today()
    edition_statuses = {}
    
    # Logika automatycznego wykrywania statusu
    # EDYCJA STARTUJE 1-go dnia miesiąca i trwa aż wszyscy odpadną
    for key, cfg in EDITIONS_CONFIG.items():
        start_date = cfg['start_date']
        start_month = start_date.month
        start_year = start_date.year
        
        today_month = TODAY.month
        today_year = TODAY.year
        
        status = 'UNKNOWN'
        icon = '❓'
        
        # 1. Jeśli edycja startuje w przyszłości
        if start_year > today_year or (start_year == today_year and start_month > today_month):
            status = 'UPCOMING'
            icon = '⏳'  # Klepsydra - edycja się nie zaczęła
        
        # 2. Edycja startuje w obecnym miesiącu lub wcześniej
        elif start_year < today_year or (start_year == today_year and start_month <= today_month):
            # Domyślnie FINALIZATION (finiszuje) - ostatni miesiąc przed obecnym
            # LUB ACTIVE - obecny miesiąc
            
            # Obliczamy ile miesięcy wstecz startowała ta edycja
            months_since_start = (today_year - start_year) * 12 + (today_month - start_month)
            
            if start_month == today_month and start_year == today_year:
                # Obecny miesiąc = ACTIVE
                status = 'ACTIVE'
                icon = '🟢'
            elif (start_year == today_year and start_month == today_month - 1) or (start_year == today_year - 1 and start_month == 12 and today_month == 1):
                # Poprzedni miesiąc = FINALIZATION
                status = 'FINALIZATION'
                icon = '🚩'
            else:
                # Starsze lub przyszłe = FINISHED
                status = 'FINISHED'
                icon = '🏁'
            
            # Override: jeśli jest ręcznie zamknięta
            if cfg.get('is_manually_closed', False):
                status = 'FINISHED'
                icon = '🏁'
        
        # Zapisujemy wynik
        edition_statuses[key] = {
            'status': status,
            'icon': icon
        }
    
    # === 2. WIDOCZNE KLUCZE EDYCJI ===
    VISIBLE_EDITIONS_KEYS = list(EDITIONS_CONFIG.keys()) 
    
    # Inicjalizacja domyślnego wyboru
    default_nav_key = "nav_historical_stats"
    
    # Spróbuj znaleźć pierwszą aktywną edycję
    active_edition_key = None
    for key, status_data in edition_statuses.items():
        if status_data['status'] == 'ACTIVE':
            active_edition_key = key
            break
    
    if active_edition_key:
        default_nav_key = f"nav_{active_edition_key}_ranking"
    else:
        # Jeśli nie ma ACTIVE, spróbuj FINALIZATION
        for key, status_data in edition_statuses.items():
            if status_data['status'] == 'FINALIZATION':
                default_nav_key = f"nav_{key}_ranking"
                break

    # === 3. LOGIKA STARTOWA: PRZECHWYTYWANIE LINKÓW (Deep Linking) ===
    query_params = st.query_params
    
    if "page" in query_params or "edition" in query_params or "lang" in query_params:
        # Odczyt i walidacja parametrów
        url_page = query_params.get('page', 'ranking')[0].lower() if isinstance(query_params.get('page'), list) else query_params.get('page', 'ranking').lower()
        url_edition = query_params.get('edition', 'listopad')[0].lower() if isinstance(query_params.get('edition'), list) else query_params.get('edition', 'listopad').lower()
        url_lang = query_params.get('lang', 'pl')[0].lower() if isinstance(query_params.get('lang'), list) else query_params.get('lang', 'pl').lower()
        
        # Ustawiamy JĘZYK
        if url_lang in ['pl', 'en']:
            st.session_state.lang_select = url_lang

        # Mapowanie URL na klucz edycji
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
    
    # 3.2. Domyślna Inicjalizacja Sesji
    if 'nav_selection' not in st.session_state:
        st.session_state.nav_selection = default_nav_key
    
    if 'lang_select' not in st.session_state:
        st.session_state.lang_select = 'pl'
    
    lang = st.session_state.lang_select
    
    # Inicjalizacja innych zmiennych sesji
    if 'race_current_day' not in st.session_state: 
        st.session_state.race_current_day = 1
    if 'animate_charts' not in st.session_state: 
        st.session_state.animate_charts = False
    if 'success_message_key' not in st.session_state: 
        st.session_state.success_message_key = None
    if 'submitter_index_plus_one' not in st.session_state: 
        st.session_state.submitter_index_plus_one = 0 
    if 'last_day_entered' not in st.session_state: 
        st.session_state.last_day_entered = 1

    # === PASEK BOCZNY (Sidebar) ===
    st.sidebar.selectbox("Język / Language", ["pl", "en"], index=0 if lang == 'pl' else 1, key="lang_select")
    lang = st.session_state.lang_select
    
    st.sidebar.markdown("---\n")
    st.sidebar.title(_t('nav_header', lang)) 

    # === 4. MENU ROZWIJALNE (EDYCJE) ===
    with st.sidebar.expander(_t('nav_editions_expander', lang), expanded=True):
        # Przechodzimy przez edycje
        for key in VISIBLE_EDITIONS_KEYS:
            status_data = edition_statuses.get(key, {})
            cfg = EDITIONS_CONFIG[key]
            
            status = status_data.get('status', 'UNKNOWN')
            icon = status_data.get('icon', '❓')  # Różne ikonki na podstawie statusu!
            
            month_label = MONTH_NAMES[key]['pl'] if lang == 'pl' else MONTH_NAMES[key]['en']
            
            st.markdown(f"**{icon} {month_label}**")
            
            col1, col2 = st.columns(2)
            
            # 1. Edycja Nadchodząca (UPCOMING)
            if status == 'UPCOMING':
                with col1:
                    if st.button(f"{_t('nav_edition_ranking_active', lang, month_label)}", key=f"btn_{key}_ranking", use_container_width=True):
                        st.session_state.nav_selection = f"nav_{key}_ranking"
                        st.rerun()
            
            # 2. Edycja Bieżąca (ACTIVE)
            elif status == 'ACTIVE':
                with col1:
                    if st.button(f"{_t('nav_edition_ranking_active', lang, month_label)}", key=f"btn_{key}_ranking", use_container_width=True):
                        st.session_state.nav_selection = f"nav_{key}_ranking"
                        st.rerun()
                with col2:
                    if st.button(f"{_t('nav_edition_form_active', lang, month_label)}", key=f"btn_{key}_form", use_container_width=True):
                        st.session_state.nav_selection = f"nav_{key}_form"
                        st.rerun()
            
            # 3. Edycja Finalizująca (FINALIZATION)
            elif status == 'FINALIZATION':
                with col1:
                    if st.button(f"{_t('nav_edition_ranking_active', lang, month_label)}", key=f"btn_{key}_ranking", use_container_width=True):
                        st.session_state.nav_selection = f"nav_{key}_ranking"
                        st.rerun()
                with col2:
                    if st.button(f"{_t('nav_edition_form_active', lang, month_label)}", key=f"btn_{key}_form", use_container_width=True):
                        st.session_state.nav_selection = f"nav_{key}_form"
                        st.rerun()

            # 4. Edycja Zakończona (FINISHED)
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

    # === 5. MENU STATYCZNE ===

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
# === LOG ADMIN (EXPANDER) + WSKAŹNIK POMOCY ===
    
    # Pobierz ostatnie wpisy i wskaźnik pomocy
    helper_percentage_all = 0
    helper_percentage_recent = 0
    if sheet:
        try:
            df_log = load_google_sheet_data(sheet, "LogWpisow")
            
            if not df_log.empty:
                # Procent wpisów od pomocników ze WSZYSTKICH wpisów
                total_entries_all = len(df_log)
                admin_entries_all = len(df_log[df_log['Submitter'] == 'poprzeczka (Admin)']) if 'Submitter' in df_log.columns else 0
                helper_entries_all = total_entries_all - admin_entries_all
                helper_percentage_all = int((helper_entries_all / total_entries_all * 100)) if total_entries_all > 0 else 0
                
                # Procent wpisów od pomocników z OSTATNICH 200 wpisów
                df_log_recent_200 = df_log.iloc[-200:].copy()
                total_entries_recent = len(df_log_recent_200)
                admin_entries_recent = len(df_log_recent_200[df_log_recent_200['Submitter'] == 'poprzeczka (Admin)']) if 'Submitter' in df_log_recent_200.columns else 0
                helper_entries_recent = total_entries_recent - admin_entries_recent
                helper_percentage_recent = int((helper_entries_recent / total_entries_recent * 100)) if total_entries_recent > 0 else 0
        except:
            pass
    
    # Tytuł z wskaźnikami
    log_title = f"📋 Log (Admin) - Pomoc: {helper_percentage_all}% ({helper_percentage_recent}% z ostatnich 200)"
    with st.sidebar.expander(log_title, expanded=False):
        # Znalezienie aktualnej edycji
        active_edition_key = None
        for key, status_data in edition_statuses.items():
            if status_data['status'] == 'ACTIVE':
                active_edition_key = key
                break
        if not active_edition_key:
            for key, status_data in edition_statuses.items():
                if status_data['status'] == 'FINALIZATION':
                    active_edition_key = key
                    break
        if not active_edition_key:
            active_edition_key = 'november'
        
        show_admin_panel_expanded(lang=lang, sheet=sheet, edition_key=active_edition_key)
    st.sidebar.markdown("---\n")
# === 6. ROUTING I WIDOK GŁÓWNY ===
    
    match_edition = re.match(r"nav_(\w+?)_(ranking|form)$", st.session_state.nav_selection)
    
    if match_edition:
        edition_key, page_type = match_edition.groups()
        
        if page_type == 'ranking':
            show_current_edition_dashboard(lang, edition_key=edition_key)
        elif page_type == 'form':
            # Formularz jest dostępny dla ACTIVE i FINALIZATION edycji
            status = edition_statuses.get(edition_key, {}).get('status', 'UNKNOWN')
            is_form_open = status in ['ACTIVE', 'FINALIZATION']
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
        show_admin_panel(lang=lang, sheet=sheet)

    elif st.session_state.nav_selection == 'about_app':
        st.header(_t('about_app', lang))
        st.markdown(_t('about_app_text', lang))
        
        # === SZYBKIE LINKI ===
        st.subheader(_t('quick_links_header', lang))
        BASE_URL = "https://poprzeczka.streamlit.app/" 
        
        for edition_key in VISIBLE_EDITIONS_KEYS:
            status_data = edition_statuses.get(edition_key, {})
            status = status_data.get('status', 'UNKNOWN')
            
            # Pokaż linki tylko dla AKTYWNYCH i FINISZUJĄCYCH
            if status == 'UPCOMING': 
                continue

            m_pl = MONTH_NAMES[edition_key]['pl']
            m_en = MONTH_NAMES[edition_key]['en']
            p_pl = MONTH_NAMES[edition_key]['url_param_pl']
            p_en = MONTH_NAMES[edition_key]['url_param_en']
            
            st.markdown(f"**{m_pl} / {m_en}**")
            
            # Linki do Rankingów
            u_r_pl = f"{BASE_URL}?page=ranking&edition={p_pl}&lang=pl"
            u_r_en = f"{BASE_URL}?page=ranking&edition={p_en}&lang=en"
            st.markdown(f"- {_t('quick_links_ranking', lang)} {_t('quick_links_language_pl', lang)}: [{u_r_pl}]({u_r_pl})")
            st.markdown(f"- {_t('quick_links_ranking', lang)} {_t('quick_links_language_en', lang)}: [{u_r_en}]({u_r_en})")
            
            # Linki do Formularzy (tylko jeśli aktywna LUB finalizująca)
            if status in ['ACTIVE', 'FINALIZATION']:
                u_f_pl = f"{BASE_URL}?page=formularz&edition={p_pl}&lang=pl"
                u_f_en = f"{BASE_URL}?page=formularz&edition={p_en}&lang=en"
                st.markdown(f"- {_t('quick_links_form', lang)} {_t('quick_links_language_pl', lang)}: [{u_f_pl}]({u_f_pl})")
                st.markdown(f"- {_t('quick_links_form', lang)} {_t('quick_links_language_en', lang)}: [{u_f_en}]({u_f_en})")

        st.markdown("---\n")
        st.markdown(f"**URL do wklejenia** (Link do strony startowej):")
        st.code(BASE_URL)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        st.error(f"Błąd: {e}")
        import traceback
        st.code(traceback.format_exc())
