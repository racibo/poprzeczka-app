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
    
    # === 1. LOGIKA STARTOWA: PRZECHWYTYWANIE LINKÓW (Deep Linking) ===
    # Sprawdzamy, czy w adresie URL są jakieś parametry
    query_params = st.query_params
    
    if "page" in query_params or "edition" in query_params or "lang" in query_params:
        # Odczyt parametrów
        url_page = query_params.get('page', 'ranking').lower()
        url_edition = query_params.get('edition', 'listopad').lower()
        url_lang = query_params.get('lang', 'pl').lower()
        
        # 1. Ustawiamy JĘZYK w sesji
        target_lang = 'en' if url_lang == 'en' else 'pl'
        st.session_state.lang_select = target_lang
        
        # 2. Ustawiamy STRONĘ (Nawigację) w sesji
        target_key = "nav_november_ranking" # Domyślnie
        
        if url_page == 'ranking' and url_edition == 'listopad':
            target_key = 'nav_november_ranking'
        elif url_page == 'formularz' and url_edition == 'listopad':
            target_key = 'nav_november_form'
        elif url_page == 'ranking' and url_edition == 'grudzien':
            target_key = 'nav_december_ranking'
        elif url_page == 'formularz' and url_edition == 'grudzien':
            target_key = 'nav_december_form'
        
        st.session_state.nav_selection = target_key
        
        # 3. WAŻNE: Czyścimy parametry URL i przeładowujemy stronę
        # Dzięki temu aplikacja ustawi się w dobrym stanie, a "link" nie będzie
        # blokował dalszej nawigacji.
        st.query_params.clear()
        st.rerun()

    # === 2. INICJALIZACJA DOMYŚLNA (Jeśli brak linku) ===
    if 'nav_selection' not in st.session_state:
        st.session_state.nav_selection = "nav_november_ranking"
    
    if 'lang_select' not in st.session_state:
        st.session_state.lang_select = "pl"

    # Pobieramy aktualny język z sesji (ustawiony wyżej przez link lub domyślnie)
    lang = st.session_state.lang_select

    # === 3. PASEK BOCZNY: JĘZYK ===
    # Obliczamy index dla widgetu selectbox, aby wizualnie zgadzał się z sesją
    initial_lang_index = 0 if lang == "en" else 1

    # Widget języka - klucz 'lang_select' automatycznie zaktualizuje session_state
    st.sidebar.selectbox(
        "Język / Language", 
        ["en", "pl"], 
        index=initial_lang_index, 
        key="lang_select_widget", # Używamy innego klucza widgetu, by ręcznie sterować stanem
        on_change=lambda: st.session_state.update(lang_select=st.session_state.lang_select_widget)
    )
    # Synchronizacja odwrotna (jeśli zmienimy język widgetem)
    if 'lang_select_widget' in st.session_state:
        st.session_state.lang_select = st.session_state.lang_select_widget
    
    # Odświeżenie zmiennej lokalnej po ewentualnej zmianie
    lang = st.session_state.lang_select
    
    st.sidebar.markdown("---")

    # === 4. PASEK BOCZNY: MENU GŁÓWNE ===
    
    # Definicja wszystkich opcji (Zależą od aktualnego 'lang')
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

    # Mapowania pomocnicze
    menu_keys = [k for k, v in options_map] 
    reverse_map = {v: k for k, v in options_map}

    # Ustalenie, która pozycja menu ma być aktywna (na podstawie sesji)
    current_key = st.session_state.nav_selection
    
    # Zabezpieczenie: jeśli klucza z sesji nie ma w opcjach (np. zmiana języka), resetujemy na 0
    if current_key in menu_keys:
        initial_index = menu_keys.index(current_key)
    else:
        initial_index = 0

    # Wyświetlenie menu
    selected_name = st.sidebar.selectbox(
        _t('nav_header', lang),
        options=[v for k, v in options_map],
        index=initial_index, 
        key='nav_selection_widget' # Osobny klucz widgetu
    )

    # Aktualizacja wyboru w sesji (zamiana nazwy wizualnej na klucz techniczny)
    selection = reverse_map.get(selected_name, st.session_state.nav_selection)
    st.session_state.nav_selection = selection

    # --- Linki w pasku bocznym ---
    st.sidebar.markdown("---")
    st.sidebar.link_button(_t('sidebar_hive_link', lang), "https://hive.blog/trending/poprzeczka", use_container_width=True)
    
    # --- Log Administratora ---
    with st.sidebar.expander(_t('sidebar_admin_log', lang)):
        sheet = connect_to_google_sheets()
        if sheet:
            try:
                df_logs = load_google_sheet_data(sheet, "LogWpisow")
                if not df_logs.empty:
                    df_logs['Timestamp'] = pd.to_datetime(df_logs['Timestamp'], errors='coerce')
                    df_logs['Timestamp'] = df_logs['Timestamp'].dt.strftime('%Y-%m-%d %H:%M')
                    st.dataframe(
                        df_logs.rename(columns={'Timestamp': 'Time (UTC)'}).sort_values("Time (UTC)", ascending=False).head(20), 
                        width=None,
                        hide_index=True
                    )
                else:
                    st.info(_t('sidebar_log_empty', lang))
            except Exception as e:
                st.error(f"Log error: {e}")

    # === 5. OBSŁUGA GŁÓWNEGO WIDOKU (ROUTING) ===
    
    # Inicjalizacja zmiennych pomocniczych formularza
    if 'submitter_index_plus_one' not in st.session_state: st.session_state.submitter_index_plus_one = 0 
    if 'last_day_entered' not in st.session_state: st.session_state.last_day_entered = 1
    
    # Router
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
        
        # === SZYBKIE LINKI STARTOWE ===
        st.subheader(_t('quick_links_header', lang))

        BASE_URL = "https://poprzeczka.streamlit.app/" 
        
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

        for title, page, edition, link_lang, edition_label in links_data:
            url = f"{BASE_URL}?page={page}&edition={edition}&lang={link_lang}"
            lang_label = _t('quick_links_language_pl', lang) if link_lang == 'pl' else _t('quick_links_language_en', lang)
            link_label = f"🔗 {title} ({edition_label}) {lang_label}"
            st.markdown(f"* [{link_label}]({url})")
            
        st.caption("Created by @racibo & AI Assistant.")

if __name__ == "__main__":
    main()
