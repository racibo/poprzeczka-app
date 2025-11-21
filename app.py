import streamlit as st
from translations import _t
from page_form import show_submission_form
from page_current_ranking import show_current_edition_dashboard
from page_historical_stats import show_historical_stats

# --- Ustawienia Strony ---
st.set_page_config(
    layout="wide", 
    page_title="Analiza i Zarządzanie Poprzeczką", 
    page_icon="https://raw.githubusercontent.com/racibo/poprzeczka-app/main/logo.png" 
)

def main():
    """Główna funkcja renderująca aplikację Streamlit."""
    
    # === PASEK BOCZNY (Sidebar) ===
    
    # 1. Wybór języka
    st.sidebar.selectbox("Język / Language", ["pl", "en"], index=0, key="lang_select")
    lang = st.session_state.lang_select # Pobieramy z sesji
    
    st.sidebar.markdown("---")
    
    # 2. Tytuł nawigacji
    st.sidebar.title(_t('nav_header', lang)) 
    
    # 3. Menu Główne (Radio)
    # Definiujemy opcje menu
    nav_options = [
        _t('nav_november_ranking', lang), # Zmienione na Listopad
        _t('nav_december_ranking', lang), # Nowe: Grudzień
        _t('nav_submission_form', lang),
        _t('nav_historical_stats', lang)
    ]
    
    app_section = st.sidebar.radio(
        "Menu",
        nav_options,
        label_visibility="collapsed"
    )

    # 4. Dodatkowe elementy paska bocznego
    st.sidebar.markdown("---")
    
    # Link do Hive.blog
    st.sidebar.link_button(
        _t('sidebar_hive_link', lang), 
        "https://hive.blog/trending/poprzeczka", 
        use_container_width=True
    )
    
    # Zasady w expanderze
    with st.sidebar.expander(_t('sidebar_rules_header', lang)):
        st.markdown(_t('sidebar_rules_text', lang))

    # O projekcie
    with st.sidebar.expander(_t('about_app', lang)):
        st.info(_t('about_app_text', lang))
        
    # === CZĘŚĆ GŁÓWNA (Main) ===
    
    # Inicjalizacja zmiennych sesji (jeśli ich nie ma)
    if 'submitter_index_plus_one' not in st.session_state:
        st.session_state.submitter_index_plus_one = 0 
    if 'last_day_entered' not in st.session_state:
        st.session_state.last_day_entered = 1
    
    # Router - co wyświetlić w zależności od wyboru w menu
    
    if app_section == _t('nav_november_ranking', lang):
        # To jest nasza "Bieżąca edycja" (Listopad)
        show_current_edition_dashboard(lang)
        
    elif app_section == _t('nav_december_ranking', lang):
        # Placeholder na Grudzień
        st.header("❄️ Ranking Edycji Grudniowej")
        st.info("Ta edycja rozpocznie się 1 grudnia! Wróć tutaj później.")
        # Tutaj w przyszłości podepniesz funkcję np. show_december_edition(lang)
        
    elif app_section == _t('nav_submission_form', lang):
        show_submission_form(lang)
        
    elif app_section == _t('nav_historical_stats', lang):
        show_historical_stats(lang)

if __name__ == "__main__":
    main()
