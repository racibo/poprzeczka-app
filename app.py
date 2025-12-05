import streamlit as st
from translations import _t
import pandas as pd
from datetime import date, timedelta
import re
import traceback

# Importy lokalne
from config import EDITIONS_CONFIG, MONTH_NAMES
from page_form import show_submission_form
from page_current_ranking import show_current_edition_dashboard
from page_historical_stats import show_historical_stats
from google_connect import connect_to_google_sheets
from data_loader import load_google_sheet_data, process_raw_data

# --- Ustawienia Strony ---
st.set_page_config(
    layout="wide", 
    page_title="Analiza i Zarządzanie Poprzeczką", 
    page_icon="https://raw.githubusercontent.com/racibo/poprzeczka-app/main/logo.png" 
)

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
    # === LOG ADMIN (EXPANDER) ===
    with st.sidebar.expander("📋 Log (Admin)", expanded=False):
        if sheet:
            try:
                df_log = load_google_sheet_data(sheet, "LogWpisow")
                
                if not df_log.empty:
                    df_log_recent = df_log.tail(5).copy()
                    
                    for idx, row in df_log_recent.iterrows():
                        participant = row.get('Participant', 'N/A')
                        timestamp = row.get('Timestamp', 'N/A')
                        day = row.get('Day', 'N/A')
                        status = row.get('Status', 'N/A')
                        
                        try:
                            ts_obj = pd.to_datetime(timestamp)
                            time_str = ts_obj.strftime('%H:%M')
                        except:
                            time_str = str(timestamp)[-5:]
                        
                        st.markdown(f"**@{participant}** - Dzień {day} ({status}) - {time_str}")
                else:
                    st.info("Brak wpisów")
            except Exception as e:
                st.warning(f"Błąd: {e}")
        else:
            st.error("Brak połączenia")
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
