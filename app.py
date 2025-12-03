import streamlit as st
from translations import _t
import pandas as pd
from page_form import show_submission_form
from page_current_ranking import show_current_edition_dashboard
from page_historical_stats import show_historical_stats
from google_connect import connect_to_google_sheets
from data_loader import load_google_sheet_data

# --- Ustawienia Strony ---
st.set_page_config(
    layout="wide", 
    page_title="Analiza i Zarządzanie Poprzeczką", 
    page_icon="https://raw.githubusercontent.com/racibo/poprzeczka-app/main/logo.png" 
)

def main():
    """Główna funkcja renderująca aplikację Streamlit."""
    
    # === STARTUP LOGIC: URL PARAMS & SESSION INIT ===
    query_params = st.query_params
    
    # 1. Odczyt i walidacja parametrów startowych z URL
    url_page = query_params.get('page', ['ranking'])[0].lower() # np. 'ranking', 'formularz'
    url_edition = query_params.get('edition', ['listopad'])[0].lower() # np. 'listopad', 'grudzien'
    url_lang = query_params.get('lang', ['pl'])[0].lower() # np. 'pl', 'en'
    
    # 2. Mapowanie na klucze nawigacji Streamlit ('nav_november_ranking')
    start_selection_key = "nav_november_ranking" # Domyślna wartość
    
    if url_page == 'ranking' and url_edition == 'listopad':
        start_selection_key = 'nav_november_ranking'
    elif url_page == 'formularz' and url_edition == 'listopad':
        start_selection_key = 'nav_november_form'
    elif url_page == 'ranking' and url_edition == 'grudzien':
        start_selection_key = 'nav_december_ranking'
    elif url_page == 'formularz' and url_edition == 'grudzien':
        start_selection_key = 'nav_december_form'
        
    # Ustalenie języka startowego (dla sidebar index)
    start_lang_value = 'en' if url_lang == 'en' else 'pl'
    
    # Inicjalizacja sesji dla wyboru menu
    # TYLKO nav_selection, aby widget selectbox mógł ustawić 'lang_select'
    if 'nav_selection' not in st.session_state:
        st.session_state.nav_selection = start_selection_key

    # === PASEK BOCZNY (Sidebar): JĘZYK ===
    # Używamy start_lang_value do obliczenia INDEXU, co rozwiązuje błąd konfliktu
    # "en" to index 0, "pl" to index 1
    initial_lang_index = 0 if start_lang_value == "en" else 1

    st.sidebar.selectbox(
        "Język / Language", 
        ["en", "pl"], 
        index=initial_lang_index, 
        key="lang_select"
    )
    lang = st.session_state.lang_select
    
    st.sidebar.markdown("---")

    # === DEFINICJA OPCJI MENU (Jedno źródło prawdy) ===
    # Klucze z translations.py
    
    options_map = [
        ('nav_november_ranking', _t('nav_november_ranking', lang)),
        ('nav_november_form', _t('nav_november_form', lang)),
        ('nav_december_ranking', _t('nav_december_ranking', lang)),
        ('nav_december_form', _t('nav_december_form', lang)),
        ('nav_historical_stats', _t('nav_historical_stats', lang)),
        ('nav_rules', _t('nav_rules', lang)),
        ('nav_join', _t('nav_join', lang)),
        ('about_app', _t('about_app', lang)),
    ]

    # 1. Zdefiniowanie kluczy menu i mapowania zwrotnego
    menu_keys = [k for k, v in options_map] 
    reverse_map = {v: k for k, v in options_map}

    # 2. Obliczenie indexu startowego na podstawie klucza z sesji (ustawionego przez URL)
    # Zabezpieczenie: jeśli klucza nie ma w liście, ustawiamy 0
    if st.session_state.nav_selection in menu_keys:
        initial_index = menu_keys.index(st.session_state.nav_selection)
    else:
        initial_index = 0

    # === PASEK BOCZNY (Sidebar): NAWIGACJA ===

    # Pokaż selectbox i pobierz WYBRANĄ PRZETŁUMACZONĄ NAZWĘ
    # Używamy obliczonego initial_index, aby odzwierciedlić wybór z URL
    selected_name = st.sidebar.selectbox(
        _t('nav_header', lang),
        options=[v for k, v in options_map],
        index=initial_index, 
        key='nav_selection_select'
    )

    # KLUCZOWA ZMIANA: Przekształć wybraną nazwę z powrotem na STAŁY KLUCZ
    # To jest klucz, który jest używany w routingu (np. 'nav_november_form')
    selection = reverse_map.get(selected_name, st.session_state.nav_selection)
    
    # Zapisz klucz do sesji (zamiast przetłumaczonej nazwy), aby utrzymać stan
    st.session_state.nav_selection = selection

    # --- Linki Zewnętrzne i Log Administratora ---
    st.sidebar.markdown("---")
    st.sidebar.link_button(_t('sidebar_hive_link', lang), "https://hive.blog/trending/poprzeczka", use_container_width=True)
    
    with st.sidebar.expander(_t('sidebar_admin_log', lang)):
        sheet = connect_to_google_sheets()
        if sheet:
            try:
                df_logs = load_google_sheet_data(sheet, "LogWpisow")
                if not df_logs.empty:
                    # Konwersja na format daty i usunięcie sekund
                    df_logs['Timestamp'] = pd.to_datetime(df_logs['Timestamp'], errors='coerce')
                    df_logs['Timestamp'] = df_logs['Timestamp'].dt.strftime('%Y-%m-%d %H:%M')
                    
                    # Zmiana nazwy kolumny na Time (UTC) dla jasności międzynarodowej
                    st.dataframe(
                        df_logs.rename(columns={'Timestamp': 'Time (UTC)'}).sort_values("Time (UTC)", ascending=False).head(20), 
                        width="stretch",
                        hide_index=True
                    )
                else:
                    st.info(_t('sidebar_log_empty', lang))
            except Exception as e:
                st.error(f"Error loading log: {e}")

    # === OBSŁUGA GŁÓWNEGO WIDOKU (ROUTING) ===
    
    # Inicjalizacja sesji dla formularzy (jeśli nie istnieją)
    if 'submitter_index_plus_one' not in st.session_state: st.session_state.submitter_index_plus_one = 0 
    if 'last_day_entered' not in st.session_state: st.session_state.last_day_entered = 1
    
    # Używamy zmiennej 'selection', która na pewno jest kluczem (np. 'nav_november_ranking')
    if selection == 'nav_november_ranking':
        show_current_edition_dashboard(lang, edition_key="november")
    elif selection == 'nav_november_form':
        show_submission_form(lang, edition_key="november")
        
    elif selection == 'nav_december_ranking':
        show_current_edition_dashboard(lang, edition_key="december")
    elif selection == 'nav_december_form':
        show_submission_form(lang, edition_key="december")
        
    elif selection == 'nav_historical_stats':
        show_historical_stats(lang)
        
    elif selection == 'nav_rules':
        st.header(_t('sidebar_rules_header', lang))
        st.markdown(_t('sidebar_rules_text', lang))
        
    elif selection == 'nav_join':
        st.header(_t('nav_join', lang))
        st.info(_t('join_intro', lang))
        st.markdown(f"""
        1. {_t('join_step_1', lang)}
        2. {_t('join_step_2', lang)}
        3. {_t('join_step_3', lang)}
        4. {_t('join_step_4', lang)}
        """)
        
    elif selection == 'about_app':
        st.header(_t('about_app', lang))
        st.markdown(_t('about_app_text', lang))
        
        # === NOWY BLOK: SZYBKIE LINKI STARTOWE ===
        st.subheader(_t('quick_links_header', lang))

        # UWAGA: Używamy stałego adresu URL aplikacji
        BASE_URL = "https://poprzeczka.streamlit.app/" 
        
        # Definicja linków
        # (Tekst, page, edition, lang, Sekcja)
        links_data = [
            # Rankingi PL
            (_t('quick_links_ranking', lang), 'ranking', 'listopad', 'pl', _t('quick_links_edition_nov', lang)),
            (_t('quick_links_ranking', lang), 'ranking', 'grudzien', 'pl', _t('quick_links_edition_dec', lang)),
            # Formularze PL
            (_t('quick_links_form', lang), 'formularz', 'listopad', 'pl', _t('quick_links_edition_nov', lang)),
            (_t('quick_links_form', lang), 'formularz', 'grudzien', 'pl', _t('quick_links_edition_dec', lang)),
            # ---
            # Rankingi EN
            (_t('quick_links_ranking', lang), 'ranking', 'listopad', 'en', _t('quick_links_edition_nov', lang)),
            (_t('quick_links_ranking', lang), 'ranking', 'grudzien', 'en', _t('quick_links_edition_dec', lang)),
            # Formularze EN
            (_t('quick_links_form', lang), 'formularz', 'listopad', 'en', _t('quick_links_edition_nov', lang)),
            (_t('quick_links_form', lang), 'formularz', 'grudzien', 'en', _t('quick_links_edition_dec', lang)),
        ]

        # Generowanie i wyświetlanie linków
        for title, page, edition, link_lang, edition_label in links_data:
            # Tworzenie pełnego URL
            url = f"{BASE_URL}?page={page}&edition={edition}&lang={link_lang}"
            
            # Tworzenie etykiety dla linku
            lang_label = _t('quick_links_language_pl', lang) if link_lang == 'pl' else _t('quick_links_language_en', lang)
            link_label = f"🔗 {title} ({edition_label}) {lang_label}"
            
            st.markdown(f"* [{link_label}]({url})")
            
        # === KONIEC NOWEGO BLOKU ===
        st.caption("Created by @racibo & AI Assistant.")

if __name__ == "__main__":
    main()
