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

    # === PASEK BOCZNY (Sidebar) ===
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
    
    st.sidebar.markdown("---") # Ta linia (Lw. 40) jest już w kodzie
    # ... reszta kodu powinna pozostać bez zmian
    st.sidebar.title(_t('nav_header', lang)) 
    
    # === DEFINICJA OPCJI MENU ===
    # Klucze muszą odpowiadać kluczom w translations.py
    opts_nov = ['nav_november_ranking', 'nav_november_form']
    opts_dec = ['nav_december_ranking', 'nav_december_form']
    opts_hist = ['nav_historical_stats', 'nav_rules', 'nav_join', 'about_app']
    
    # Mapowanie: Tłumaczenie -> Klucz (potrzebne, bo radio zwraca tekst)
    label_to_key = {}
    for key in opts_nov + opts_dec + opts_hist:
        label_to_key[_t(key, lang)] = key

    # Funkcja aktualizująca stan (Callback)
    def update_nav(group_name):
        # 1. Pobieramy wybraną wartość z widgetu, który wywołał zmianę
        changed_widget_key = f"radio_{group_name}"
        selected_label = st.session_state.get(changed_widget_key)
        
        # 2. Aktualizujemy główny wybór nawigacji
        if selected_label:
            st.session_state.nav_selection = label_to_key.get(selected_label)

        # 3. Czyścimy stan POZOSTAŁYCH widgetów (ustawiamy na None)
        # To sprawia, że wizualnie się odznaczają i pozwalają na ponowne kliknięcie w przyszłości
        if group_name == "nov":
            st.session_state.radio_dec = None
            st.session_state.radio_hist = None
        elif group_name == "dec":
            st.session_state.radio_nov = None
            st.session_state.radio_hist = None
        elif group_name == "hist":
            st.session_state.radio_nov = None
            st.session_state.radio_dec = None

    # Wyznaczanie indeksów dla radio buttonów na podstawie aktualnego wyboru
    curr_key = st.session_state.nav_selection
    
    idx_nov = opts_nov.index(curr_key) if curr_key in opts_nov else None
    idx_dec = opts_dec.index(curr_key) if curr_key in opts_dec else None
    idx_hist = opts_hist.index(curr_key) if curr_key in opts_hist else None

    # === RENDEROWANIE MENU ===
    
    # 1. SEKCJA LISTOPAD
    st.sidebar.markdown(_t('menu_section_nov', lang))
    st.sidebar.write("") # Odstęp
    st.sidebar.radio(
        "Listopad",
        options=[_t(k, lang) for k in opts_nov],
        index=idx_nov,
        key="radio_nov",
        label_visibility="collapsed",
        on_change=update_nav,
        args=("nov",)
    )
    
    # 2. SEKCJA GRUDZIEŃ
    st.sidebar.markdown(" ") # Odstęp
    st.sidebar.markdown(_t('menu_section_dec', lang))
    st.sidebar.write("") # Odstęp
    st.sidebar.radio(
        "Grudzień",
        options=[_t(k, lang) for k in opts_dec],
        index=idx_dec,
        key="radio_dec",
        label_visibility="collapsed",
        on_change=update_nav,
        args=("dec",)
    )
    
    # 3. SEKCJA HISTORIA I ZASADY
    st.sidebar.markdown(" ") 
    st.sidebar.markdown(" ") # Większy odstęp
    st.sidebar.markdown(_t('menu_section_hist', lang))
    st.sidebar.radio(
        "Historia",
        options=[_t(k, lang) for k in opts_hist],
        index=idx_hist,
        key="radio_hist",
        label_visibility="collapsed",
        on_change=update_nav,
        args=("hist",)
    )

    # --- Linki i Log ---
    st.sidebar.markdown("---")
    st.sidebar.link_button("🐝 Hive.blog", "https://hive.blog/trending/poprzeczka", use_container_width=True)
    
    with st.sidebar.expander(_t('sidebar_admin_log', lang)):
        sheet = connect_to_google_sheets()
        if sheet:
            df_logs = load_google_sheet_data(sheet, "LogWpisow")
            if not df_logs.empty:
                # Konwersja na format daty i usunięcie sekund
                df_logs['Timestamp'] = pd.to_datetime(df_logs['Timestamp'])
                df_logs['Timestamp'] = df_logs['Timestamp'].dt.strftime('%Y-%m-%d %H:%M')
                
                # Zmiana nazwy kolumny na Time (UTC) dla jasności międzynarodowej
                st.dataframe(
                    df_logs.rename(columns={'Timestamp': 'Time (UTC)'}).sort_values("Time (UTC)", ascending=False).head(20), 
                    width="stretch",  # <--- ZMIANA
                    hide_index=True
                )
            else:
                st.info("Log pusty.")

    # === OBSŁUGA GŁÓWNEGO WIDOKU ===
    
    # Inicjalizacja sesji dla formularzy
    if 'submitter_index_plus_one' not in st.session_state: st.session_state.submitter_index_plus_one = 0 
    if 'last_day_entered' not in st.session_state: st.session_state.last_day_entered = 1
    
    selection = st.session_state.nav_selection

    # Routing
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
        st.caption("Created by @racibo & AI Assistant.")

if __name__ == "__main__":
    main()
