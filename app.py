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
    
    st.sidebar.title(_t('nav_header', 'pl')) 
    
    # Domyślny język ustawiony na 'pl', ale użytkownik może zmienić
    lang = st.sidebar.selectbox("Język / Language", ["pl", "en"], index=0)
    
    if 'submitter_index_plus_one' not in st.session_state:
        st.session_state.submitter_index_plus_one = 0 
    if 'last_day_entered' not in st.session_state:
        st.session_state.last_day_entered = 1
    
    app_section = st.sidebar.radio(
        _t('nav_header', lang),
        [
            _t('nav_current_ranking', lang),
            _t('nav_submission_form', lang),
            _t('nav_historical_stats', lang)
        ],
        label_visibility="collapsed"
    )

    st.sidebar.markdown("---")
    with st.sidebar.expander(_t('about_app', lang)):
        st.info(_t('about_app_text', lang))
    
    if app_section == _t('nav_submission_form', lang):
        show_submission_form(lang)
    elif app_section == _t('nav_current_ranking', lang):
        show_current_edition_dashboard(lang)
    elif app_section == _t('nav_historical_stats', lang):
        show_historical_stats(lang)

if __name__ == "__main__":
    main()