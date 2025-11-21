import streamlit as st
from translations import _t
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
    
    # === PASEK BOCZNY (Sidebar) ===
    
    # 1. Wybór języka
    st.sidebar.selectbox("Język / Language", ["pl", "en"], index=0, key="lang_select")
    lang = st.session_state.lang_select
    
    st.sidebar.markdown("---")
    
    # 2. Tytuł nawigacji
    st.sidebar.title(_t('nav_header', lang)) 
    
    # 3. Menu Główne (Radio)
    nav_options = [
        _t('nav_november_ranking', lang), 
        _t('nav_december_ranking', lang),
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
    
    st.sidebar.link_button(
        _t('sidebar_hive_link', lang), 
        "https://hive.blog/trending/poprzeczka", 
        use_container_width=True
    )
    
    with st.sidebar.expander(_t('sidebar_rules_header', lang)):
        st.markdown(_t('sidebar_rules_text', lang))

    with st.sidebar.expander(_t('about_app', lang)):
        st.info(_t('about_app_text', lang))
        
    # <<< DYSKRETNY LOG ADMINA (NA DOLE PASKU BOCZNEGO) >>>
    st.sidebar.markdown("---")
    with st.sidebar.expander(_t('sidebar_admin_log', lang)):
        sheet = connect_to_google_sheets()
        if sheet:
            df_logs = load_google_sheet_data(sheet, "LogWpisow")
            if not df_logs.empty:
                # Pokazujemy tylko ostatnie 50 wpisów, posortowane od najnowszych
                st.dataframe(
                    df_logs.sort_values("Timestamp", ascending=False).head(50), 
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info(_t('sidebar_log_empty', lang))
        
    # === CZĘŚĆ GŁÓWNA (Main) ===
    
    if 'submitter_index_plus_one' not in st.session_state:
        st.session_state.submitter_index_plus_one = 0 
    if 'last_day_entered' not in st.session_state:
        st.session_state.last_day_entered = 1
    
    if app_section == _t('nav_november_ranking', lang):
        show_current_edition_dashboard(lang)
        
    elif app_section == _t('nav_december_ranking', lang):
        st.header("❄️ Ranking Edycji Grudniowej")
        st.info("Ta edycja rozpocznie się 1 grudnia! Wróć tutaj później.")
        
    elif app_section == _t('nav_submission_form', lang):
        show_submission_form(lang)
        
    elif app_section == _t('nav_historical_stats', lang):
        show_historical_stats(lang)

if __name__ == "__main__":
    main()
