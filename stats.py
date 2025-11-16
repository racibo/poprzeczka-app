import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import json
from datetime import datetime
import numpy as np
import os
from scipy.stats import pearsonr
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import gspread # Do obsługi Google Sheets
from oauth2client.service_account import ServiceAccountCredentials
import io
import time
from streamlit_extras.mention import mention # Do podziękowań

# --- Ustawienia Strony ---
st.set_page_config(layout="wide", page_title="Analiza i Zarządzanie Poprzeczką")

# === Definicje Plików i Uczestników ===
FILE_HISTORICAL = "historical_results.json" 
GOOGLE_SHEET_NAME = "Baza Danych Poprzeczki" 

CURRENT_PARTICIPANTS = sorted([
    'ataraksja', 'browery', 'cezary-io', 'edycu007', 'ervin-lemark', 
    'fredkese', 'homesteadlt', 'manuvert', 'marianomariano', 'merthin', 
    'navidjahanshahi', 'new.things', 'patif2025', 'racibo', 'sk1920'
])
SUBMITTER_LIST = CURRENT_PARTICIPANTS + ['poprzeczka (Admin)']


# === Słownik Tłumaczeń (PL/EN) ===
translations = {
    'pl': {
        'app_title': "Analiza i Zarządzanie Poprzeczką",
        'nav_header': "Nawigacja",
        'nav_current_ranking': "📊 Ranking Bieżącej Edycji",
        'nav_submission_form': "📋 Formularz Wprowadzania Danych",
        'nav_historical_stats': "📈 Statystyki Historyczne",
        'form_header': "Formularz zgłoszeniowy Poprzeczki",
        'form_info': "Wprowadź dane za konkretny etap (dzień) rywalizacji.",
        'form_submitter_label': "Twoja nazwa (Kto wprowadza dane?)",
        'form_submitter_placeholder': "Wybierz, kto wprowadza dane...",
        'form_participant_label': "Uczestnik, którego dotyczy wpis",
        'form_participant_placeholder': "Wybierz uczestnika...",
        'form_day_label': "Etap (numer dnia)",
        'form_status_label': "Status etapu",
        'form_status_pass': "Zaliczone",
        'form_status_fail': "Niezaliczone",
        'form_status_no_report': "Brak raportu",
        'form_status_info': "Uwaga: 'Niezaliczone' oraz 'Brak raportu' mają ten sam skutek (etap niezaliczony).",
        'form_converters_expander': "ℹ️ Informacja o przelicznikach (dla danych ze Strava itp.)",
        'form_converters_warning': "Jeśli zgłaszasz kroki z aktywności (np. Strava, Garmin), stosujemy poniższe przeliczniki. Upewnij się, że Twój wynik końcowy jest poprawny.",
        'form_notes_label': "Inne (opcjonalnie)",
        'form_notes_placeholder': "Np. 'Dane ze Strava', 'Link do zrzutu ekranu: ...', 'Zapomniałem zegarka'",
        'form_upload_label': "Zrzut ekranu (opcjonalnie) - na razie tylko informacyjnie",
        'form_thanks_note': "> W miarę możliwości będę nagradzał za pomoc we współtworzeniu rozgrywki. Z góry dziękuję za pomoc!",
        'form_submit_button': "Zapisz dane",
        'form_success_message': "Pomyślnie zapisano: **{0}** - Dzień {1} - Status: **{2}**",
        'form_error_message': "Wystąpił błąd podczas zapisu danych: {0}",
        'form_error_no_participant': "Błąd: Musisz wybrać uczestnika i wprowadzającego.",
        'form_confirmation_header': "Szczegóły zapisu (potwierdzenie)",
        'form_confirmation_participant': "Uczestnik",
        'form_confirmation_day': "Etap (Dzień)",
        'form_confirmation_status': "Status",
        'form_confirmation_notes': "Notatki",
        'form_confirmation_notes_empty': "Brak",
        'form_overwrite_info': "W razie pomyłki, po prostu wprowadź dane dla tego samego uczestnika i dnia jeszcze raz. Nowy wpis nadpisze stary w rankingu.",
        'current_header': "📊 Ranking i Status Bieżącej Edycji",
        'current_no_data': "Brak danych dla bieżącej edycji. Wprowadź pierwsze dane za pomocą formularza.",
        'current_ranking_header': "Aktualna Klasyfikacja",
        'current_ranking_rules': """
        Klasyfikacja jest liczona na żywo zgodnie z zasadami:
        1.  Sortowanie po **najwyższym zaliczonym etapie** (malejąco).
        2.  Przy remisie, sortowanie odbywa się przez porównanie wyników etap po etapie (zaczynając od góry). Pierwsza różnica decyduje - osoba z 'Niezaliczonym' etapem przegrywa.
        3.  Odpadnięcie następuje po **3 kolejnych** niepowodzeniach (Niezaliczone / Brak raportu) *biorąc pod uwagę tylko zaraportowane dni*.
        """,
        'current_ranking_error': "Wystąpił błąd podczas obliczania rankingu: {0}",
        'current_header_check_error': "BŁĄD KONFIGURACJI: Sprawdź nagłówki w Arkuszu Google!",
        'current_header_check_details': "Aplikacja nie może odczytać danych, ponieważ nagłówki w zakładce 'BiezacaEdycja' są nieprawidłowe.",
        'current_header_check_expected': "Oczekiwane nagłówki",
        'current_header_check_found': "Znalezione nagłówki",
        'ranking_col_participant': "Uczestnik",
        'ranking_col_highest_pass': "Najw. Zaliczone",
        'ranking_col_status': "Status",
        'ranking_col_failed_list': "Niezaliczone (pierwsze 10)",
        'ranking_status_active': "W grze",
        'ranking_status_eliminated': "Odpadł (Dzień {0})",
        'current_completeness_header': "Kompletność Danych (Ostatnie {0} etapów)",
        'current_completeness_no_data': "Brak danych do wyświetlenia kompletności.",
        'completeness_col_day': "Dzień",
        'completeness_col_participant': "Uczestnik",
        'current_log_expander': "Pokaż log wpisów (dla Admina)",
        'current_log_empty': "Log wpisów jest pusty.",
        'current_stats_header': "🏆 Statystyki Bieżącej Edycji",
        'current_stats_top_submitters': "Najwięksi Pomocnicy (dzięki!)",
        # <<< POPRAWKA 3 (Zmiana tekstu) >>>
        'current_stats_top_submitters_desc': "Osoby, które najczęściej wprowadzały dane do systemu. Postaram się nagrodzić Was jakimiś tokenami.",
        'current_stats_streaks': "Najdłuższe Aktywne Serie Zaliczeń",
        'current_stats_streaks_desc': "Uczestnicy z najdłuższą nieprzerwaną serią zaliczonych etapów (do ostatniego zaraportowanego dnia).",
        'current_stats_streaks_days': "dni",
        'current_stats_race_header': "🏁 Wyścig Zaliczeń (Liczba Zwycięstw Etapowych)",
        'current_stats_race_desc': "Animacja pokazująca łączną liczbę zaliczonych etapów, dzień po dniu.",
        'current_stats_race_button': "Uruchom Wyścig!",
        'current_stats_race_day': "Etap",
        'current_stats_race_total': "Suma zaliczeń",
        'title': "Interaktywna analiza rywalizacji krokowej",
        'sidebar_header': "🎛️ Filtry i opcje",
        'select_period': "Wybierz okres",
        'manual_select': "Wybierz miesiące ręcznie",
        'last_n_editions': "Ostatnie {0} edycji",
        'all_editions': "Wszystkie edycje",
        'select_users': "Wybierz uczestników",
        'select_all_users': "Wszyscy uczestnicy",
        'min_editions': "Minimalna liczba edycji",
        'chart_type': "Wybierz typ wykresu",
        'results': "Wyniki",
        'positions': "Miejsca",
        'comparison_chart_title_results': "Porównanie wyników graczy",
        'comparison_chart_title_positions': "Porównanie pozycji graczy",
        'y_axis_results': "Wynik",
        'y_axis_positions': "Miejsce",
        'x_axis_month': "Miesiąc",
        'x_axis_edition': "Numer edycji",
        'personal_records': "🏅 Rekordy osobiste",
        'best_result': "Najlepszy wynik",
        'worst_result': "Najgorszy wynik",
        'best_position': "Najlepsze miejsce",
        'worst_position': "Najgorsze miejsce",
        'avg_result': "Średni wynik",
        'avg_position': "Średnie miejsce",
        'edition': "Edycja",
        'participant': "Uczestnik",
        'result': "Wynik",
        'position': "Miejsce",
        'no_data_selected': "Brak danych dla wybranych filtrów.",
        'monthly_summary': "Zestawienie miesięczne",
        'monthly_summary_results': "Zestawienie miesięczne (Wyniki)",
        'monthly_summary_positions': "Zestawienie miesięczne (Miejsca)",
        'monthly_summary_desc': "Tabela przedstawia wyniki i zajęte miejsca w poszczególnych edycjach.",
        'distribution_of_results': "Rozkład wyników",
        'histogram_title_results': "Histogram wyników",
        'histogram_title_positions': "Histogram miejsc",
        'player_stats': "Statystyki graczy (min. edycji)",
        'count_col': "Liczba edycji",
        'mean_col': "Średnia",
        'min_col': "Minimum",
        'max_col': "Maksimum",
        'median_col': "Mediana",
        'std_col': "Odch. std.",
        'correlation_analysis': "Analiza korelacji (Wynik vs Miejsce)",
        'correlation_r': "Współczynnik korelacji (r):",
        'correlation_p': "Wartość p:",
        'correlation_desc_strong_neg': "Silna ujemna korelacja: Wzrost wyniku wiąże się z lepszą pozycją (niższy numer miejsca).",
        'correlation_desc_weak_neg': "Słaba ujemna korelacja: Wzrost wyniku może wiązać się z lepszą pozycją (niższy numer miejsca).",
        'correlation_desc_no': "Brak korelacji: Wynik nie ma związku z miejscem.",
        'correlation_desc_not_significant': "Korelacja nie jest statystycznie istotna (p > 0.05).",
        'medal_classification_title': "Klasyfikacja miejsc",
        'position_col': "Pozycja",
        'medals_col': "Medale",
        'total_medals_col': "Suma medali",
        'total_participations': "Liczba startów",
        'user_details_header': "Szczegółowe statystyki uczestnika",
        'select_single_user': "Wybierz jednego uczestnika z filtrów, aby zobaczyć jego rekordy osobiste.",
        'heatmap_title': "Mapa cieplna zajmowanych miejsc",
        'heatmap_desc': "Wizualizacja miejsc zajmowanych przez uczestników. Jaśniejszy kolor oznacza lepsze (niższe) miejsce.",
        'medal_race_title': "Historyczny wyścig medalowy",
        'medal_race_desc': "Wykres pokazuje skumulowaną liczbę medali (miejsca 1-3) dla uczestników po każdej edycji.",
        'cumulative_medals': "Łączna liczba medali (Top {0})",
        'about_app': "O aplikacji",
        'about_app_text': "Ta aplikacja Streamlit służy do interaktywnej wizualizacji, analizy danych historycznych oraz zarządzania bieżącą edycją rywalizacji krokowej.",
        'participants_per_edition': "Liczba uczestników w poszczególnych edycjach",
        'avg_result_pos_per_edition': "Średni wynik i pozycja w poszczególnych edycjach",
        'avg_result_edition': "Średni wynik",
        'avg_position_edition': "Średnia pozycja",
        'select_medal_range': "Wybierz zakres miejsc medalowych",
        'top_1': "Tylko 1. miejsce",
        'top_3': "Top 3 (1-3)",
        'top_5': "Top 5 (1-5)",
        'top_10': "Top 10 (1-10)",
        'custom_range': "Zakres niestandardowy",
        'min_medal_position': "Minimalna pozycja medalowa",
        'max_medal_position': "Maksymalna pozycja medalowa",
        'scatter_plot_title': "Wyniki uczestników w poszczególnych edycjach (z miejscami)",
        'scatter_plot_desc': "Wykres punktowy przedstawiający wyniki każdego uczestnika w kolejnych edycjach. Kolor punktu oznacza zajęte miejsce.",
        'position_legend': "Miejsce",
        'participants_chart_title': "Liczba uczestników w poszczególnych edycjach",
        'participants_chart_ylabel': "Liczba uczestników",
        'edition_ranking_title': "Ranking edycji rozgrywki",
        'edition_ranking_desc': "Tabela przedstawia ranking edycji od najlepszej do najgorszej, na podstawie średniego wyniku i średniej pozycji.",
        'overall_records_title': "Chronologiczna tablica rekordów całej rozgrywki",
        'overall_records_desc': "Tabela przedstawia najwyższe wyniki osiągnięte w całej rozgrywce po każdej edycji.",
        'personal_records_timeline_title': "Chronologiczna tablica rekordów osobistych uczestników",
        'personal_records_timeline_desc': "Tabela przedstawia, kiedy poszczególni uczestnicy pobijali swoje rekordy osobiste.",
        'record_holder': "Rekordzista",
        'record_value': "Wartość rekordu",
        'previous_record': "Poprzedni rekord",
        'record_broken_by': "Rekord pobity przez",
        'new_record': "Nowy rekord",
        'old_record': "Stary rekord",
        'edition_winner': "Zwycięzca edycji",
        'medal_classification_classic_title': "Klasyfikacja medalowa (Top 3)",
        'survival_analysis_title': "Analiza przetrwania uczestników",
        'survival_analysis_desc': "Wykres pokazuje, ilu uczestników pozostało w grze każdego dnia. Uczestnik odpada 3 dni po ostatnim zaliczonym etapie (np. wynik 10 oznacza odpadnięcie 13. dnia).",
        'survival_analysis_select_editions': "Wybierz edycje do porównania",
        'survival_analysis_x_axis': "Dzień rozgrywki",
        'survival_analysis_y_axis': "Liczba aktywnych uczestników",
        'survival_analysis_legend': "Edycja",
        'survival_analysis_no_selection': "Wybierz co najmniej jedną edycję, aby zobaczyć analizę przetrwania.",
    },
    'en': {
        # ... (Tłumaczenia EN) ...
        'app_title': "Step Challenge Analysis & Management",
        'nav_header': "Navigation",
        'nav_current_ranking': "📊 Current Edition Ranking",
        'nav_submission_form': "📋 Data Entry Form",
        'nav_historical_stats': "📈 Historical Stats",
        'form_header': "Step Challenge Submission Form",
        'form_info': "Enter data for a specific stage (day) of the competition.",
        'form_submitter_label': "Your Name (Who is entering the data?)",
        'form_submitter_placeholder': "Select submitter...",
        'form_participant_label': "Participant (Data subject)",
        'form_participant_placeholder': "Select participant...",
        'form_day_label': "Stage (Day number)",
        'form_status_label': "Stage Status",
        'form_status_pass': "Passed",
        'form_status_fail': "Failed",
        'form_status_no_report': "No Report",
        'form_status_info': "Note: 'Failed' and 'No Report' have the same effect (stage failed).",
        'form_converters_expander': "ℹ️ Info about converters (for Strava data, etc.)",
        'form_converters_warning': "If you are reporting steps from activities (e.g., Strava, Garmin), we use the converters below. Please ensure your final score is correct.",
        'form_notes_label': "Other (optional)",
        'form_notes_placeholder': "e.g., 'Data from Strava', 'Screenshot link: ...', 'Forgot my watch'",
        'form_upload_label': "Screenshot (optional) - for info only",
        'form_thanks_note': "> Where possible, I will reward assistance in co-creating the game. Thank you in advance for your help!",
        'form_submit_button': "Save Data",
        'form_success_message': "Successfully saved: **{0}** - Day {1} - Status: **{2}**",
        'form_error_message': "An error occurred while saving data: {0}",
        'form_error_no_participant': "Error: You must select a submitter and a participant.",
        'form_confirmation_header': "Submission Details (Confirmation)",
        'form_confirmation_participant': "Participant",
        'form_confirmation_day': "Stage (Day)",
        'form_confirmation_status': "Status",
        'form_confirmation_notes': "Notes",
        'form_confirmation_notes_empty': "None",
        'form_overwrite_info': "If you make a mistake, just re-enter the data for the same participant and day. The new entry will overwrite the old one in the ranking.",
        'current_header': "📊 Current Edition Ranking & Status",
        'current_no_data': "No data for the current edition. Please enter the first data using the form.",
        'current_ranking_header': "Current Standings",
        'current_ranking_rules': """
        Standings are calculated live according to the rules:
        1.  Sorted by the **highest completed stage** (descending).
        2.  On a tie, sorted by comparing stage results top-down. The first difference decides - the participant with a 'Failed' stage loses.
        3.  Elimination occurs after **3 consecutive failures** (Failed / No Report) *based on reported days only*.
        """,
        'current_ranking_error': "An error occurred while calculating the ranking: {0}",
        'current_header_check_error': "CONFIG ERROR: Check Google Sheet Headers!",
        'current_header_check_details': "The app cannot read data because the headers in the 'BiezacaEdycja' worksheet are incorrect.",
        'current_header_check_expected': "Expected Headers",
        'current_header_check_found': "Found Headers",
        'ranking_col_participant': "Participant",
        'ranking_col_highest_pass': "Highest Pass",
        'ranking_col_status': "Status",
        'ranking_col_failed_list': "Failed Stages (first 10)",
        'ranking_status_active': "In Game",
        'ranking_status_eliminated': "Eliminated (Day {0})",
        'current_completeness_header': "Data Completeness (Last {0} stages)",
        'current_completeness_no_data': "No data to display completeness.",
        'completeness_col_day': "Day",
        'completeness_col_participant': "Participant",
        'current_log_expander': "Show submission log (for Admin)",
        'current_log_empty': "Submission log is empty.",
        'current_stats_header': "🏆 Current Edition Stats",
        'current_stats_top_submitters': "Top Helpers (Thank You!)",
        'current_stats_top_submitters_desc': "The people who submitted data most often. I will try to reward you with some tokens.",
        'current_stats_streaks': "Longest Active Pass Streaks",
        'current_stats_streaks_desc': "Participants with the longest unbroken streak of passed stages (up to the last reported day).",
        'current_stats_streaks_days': "days",
        'current_stats_race_header': "🏁 Pass Race (Total Stage Wins)",
        'current_stats_race_desc': "Animation showing the cumulative number of passed stages, day by day.",
        'current_stats_race_button': "Start the Race!",
        'current_stats_race_day': "Stage",
        'current_stats_race_total': "Total Passes",
        'title': "Interactive Step Challenge Analysis",
        'sidebar_header': "🎛️ Filters & Options",
        'select_period': "Select period",
        'manual_select': "Select months manually",
        'last_n_editions': "Last {0} editions",
        'all_editions': "All editions",
        'select_users': "Select participants",
        'select_all_users': "All participants",
        'min_editions': "Minimum number of editions",
        'chart_type': "Select chart type",
        'results': "Results",
        'positions': "Positions",
        'comparison_chart_title_results': "Player Results Comparison",
        'comparison_chart_title_positions': "Player Positions Comparison",
        'y_axis_results': "Result",
        'y_axis_positions': "Position",
        'x_axis_month': "Month",
        'x_axis_edition': "Edition Number",
        'personal_records': "🏅 Personal Records",
        'best_result': "Best Result",
        'worst_result': "Worst Result",
        'best_position': "Best Position",
        'worst_position': "Worst Position",
        'avg_result': "Avg. Result",
        'avg_position': "Avg. Position",
        'edition': "Edition",
        'participant': "Participant",
        'result': "Result",
        'position': "Position",
        'no_data_selected': "No data for the selected filters.",
        'monthly_summary': "Monthly Summary",
        'monthly_summary_results': "Monthly Summary (Results)",
        'monthly_summary_positions': "Monthly Summary (Positions)",
        'monthly_summary_desc': "The table shows the results and positions in individual editions.",
        'distribution_of_results': "Results Distribution",
        'histogram_title_results': "Histogram of Results",
        'histogram_title_positions': "Histogram of Positions",
        'player_stats': "Player Stats (min. editions)",
        'count_col': "Edition Count",
        'mean_col': "Mean",
        'min_col': "Minimum",
        'max_col': "Maximum",
        'median_col': "Median",
        'std_col': "Std. Dev.",
        'correlation_analysis': "Correlation Analysis (Result vs Position)",
        'correlation_r': "Correlation Coefficient (r):",
        'correlation_p': "P-value:",
        'correlation_desc_strong_neg': "Strong negative correlation: Higher results are associated with better positions (lower place number).",
        'correlation_desc_weak_neg': "Weak negative correlation: Higher results may be associated with better positions (lower place number).",
        'correlation_desc_no': "No correlation: Result is not related to position.",
        'correlation_desc_not_significant': "Correlation is not statistically significant (p > 0.05).",
        'medal_classification_title': "Position Classification",
        'position_col': "Position",
        'medals_col': "Medals",
        'total_medals_col': "Total Medals",
        'total_participations': "Total Participations",
        'user_details_header': "Detailed Participant Stats",
        'select_single_user': "Select a single participant from the filters to see their personal records.",
        'heatmap_title': "Position Heatmap",
        'heatmap_desc': "Visualization of participants' positions. Lighter color means a better (lower) position.",
        'medal_race_title': "Historical Medal Race",
        'medal_race_desc': "The chart shows the cumulative number of medals (places 1-3) for participants after each edition.",
        'cumulative_medals': "Cumulative Medals (Top {0})",
        'about_app': "About this app",
        'about_app_text': "This Streamlit app is used for interactive visualization, analysis of historical data, and management of the current step challenge edition.",
        'participants_per_edition': "Participants per Edition",
        'avg_result_pos_per_edition': "Average Result and Position per Edition",
        'avg_result_edition': "Average Result",
        'avg_position_edition': "Average Position",
        'select_medal_range': "Select medal range",
        'top_1': "Only 1st place",
        'top_3': "Top 3 (1-3)",
        'top_5': "Top 5 (1-5)",
        'top_10': "Top 10 (1-10)",
        'custom_range': "Custom Range",
        'min_medal_position': "Minimum medal position",
        'max_medal_position': "Maximum medal position",
        'scatter_plot_title': "Participant Results per Edition (with Positions)",
        'scatter_plot_desc': "Scatter plot showing each participant's results in successive editions. Point color indicates the position.",
        'position_legend': "Position",
        'participants_chart_title': "Number of Participants per Edition",
        'participants_chart_ylabel': "Number of Participants",
        'edition_ranking_title': "Game Edition Ranking",
        'edition_ranking_desc': "The table ranks editions from best to worst, based on average result and average position.",
        'overall_records_title': "Chronological Overall Game Records",
        'overall_records_desc': "The table shows the highest results achieved in the entire game after each edition.",
        'personal_records_timeline_title': "Chronological Personal Records Timeline",
        'personal_records_timeline_desc': "The table shows when individual participants broke their personal records.",
        'record_holder': "Record Holder",
        'record_value': "Record Value",
        'previous_record': "Previous Record",
        'record_broken_by': "Record Broken By",
        'new_record': "New Record",
        'old_record': "Old Record",
        'edition_winner': "Edition Winner",
        'medal_classification_classic_title': "Medal Classification (Top 3)",
        'survival_analysis_title': "Participant Survival Analysis",
        'survival_analysis_desc': "The chart shows how many participants remained in the game each day. A participant drops out 3 days after the last completed stage (e.g., result 10 means dropping out on day 13).",
        'survival_analysis_select_editions': "Select editions to compare",
        'survival_analysis_x_axis': "Day of competition",
        'survival_analysis_y_axis': "Number of active participants",
        'survival_analysis_legend': "Edition",
        'survival_analysis_no_selection': "Select at least one edition to see the survival analysis.",
    }
}


# === Funkcja Tłumacząca ===
def _t(key, lang, *args):
    """Simple translation function."""
    text = translations[lang].get(key, f"MISSING_KEY: {key}")
    return text.format(*args) if args else text


# === Połączenie z Google Sheets ===
@st.cache_resource(ttl=600) 
def connect_to_google_sheets():
    """Łączy się z Google Sheets używając st.secrets."""
    try:
        creds_json = {
            "type": st.secrets["type"],
            "project_id": st.secrets["project_id"],
            "private_key_id": st.secrets["private_key_id"],
            "private_key": st.secrets["private_key"].replace('\\n', '\n'),
            "client_email": st.secrets["client_email"],
            "client_id": st.secrets["client_id"],
            "auth_uri": st.secrets["auth_uri"],
            "token_uri": st.secrets["token_uri"],
            "auth_provider_x509_cert_url": st.secrets["auth_provider_x509_cert_url"],
            "client_x509_cert_url": st.secrets["client_x509_cert_url"]
        }
        
        scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
        client = gspread.authorize(creds)
        
        sheet = client.open(GOOGLE_SHEET_NAME)
        return sheet
    except Exception as e:
        if "No secrets found" in str(e):
             st.error(f"Błąd połączenia: Brak pliku secrets.toml. Uruchamiasz lokalnie? Upewnij się, że plik .streamlit/secrets.toml jest poprawnie skonfigurowany.")
        else:
            st.error(f"Błąd połączenia z Google Sheets: {e}. Sprawdź 'Secrets' w Streamlit Cloud lub lokalny plik secrets.toml.")
        return None

@st.cache_data(ttl=60) 
def load_google_sheet_data(_sheet, worksheet_name): 
    """Pobiera wszystkie dane z danej zakładki jako DataFrame."""
    try:
        worksheet = _sheet.worksheet(worksheet_name) 
        records = worksheet.get_all_records() 
        return pd.DataFrame(records)
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Błąd: Nie znaleziono zakładki o nazwie '{worksheet_name}' w Arkuszu Google.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Nie można wczytać danych z zakładki '{worksheet_name}': {e}")
        return pd.DataFrame()

# === Sekcja 1: Formularz Wprowadzania Danych ===

def show_submission_form(lang):
    """Wyświetla formularz do wprowadzania danych bieżącej edycji."""
    st.header(_t('form_header', lang))
    
    users_list = sorted(CURRENT_PARTICIPANTS)
    submitters_list_sorted = sorted(SUBMITTER_LIST)
    
    if 'last_submission' in st.session_state and st.session_state.last_submission:
        details = st.session_state.last_submission
        st.success(_t('form_success_message', lang, details['participant'], details['day'], details['status_translated']))
        
        with st.expander(_t('form_confirmation_header', lang), expanded=True):
            st.write(f"**{_t('form_confirmation_participant', lang)}:** {details['participant']}")
            st.write(f"**{_t('form_confirmation_day', lang)}:** {details['day']}")
            st.write(f"**{_t('form_confirmation_status', lang)}:** {details['status_translated']}")
            st.write(f"**{_t('form_confirmation_notes', lang)}:** {details['full_notes'] if details['full_notes'] else _t('form_confirmation_notes_empty', lang)}")
        st.info(_t('form_overwrite_info', lang))
        
        st.session_state.last_submission = None 
    
    
    participant, day, status, notes, uploaded_file = None, None, None, None, None
    
    with st.form("submission_form"):
        st.info(_t('form_info', lang))
        
        col1, col2 = st.columns(2)
        with col1:
            submitter = st.selectbox(
                _t('form_submitter_label', lang),
                options=[None] + submitters_list_sorted, 
                index=st.session_state.get('submitter_index_plus_one', 0), 
                format_func=lambda x: _t('form_submitter_placeholder', lang) if x is None else x
            )
            
            participant = st.selectbox(
                _t('form_participant_label', lang),
                options=[None] + users_list, 
                index=0, 
                format_func=lambda x: _t('form_participant_placeholder', lang) if x is None else x
            )
        with col2:
            day = st.number_input(
                _t('form_day_label', lang), 
                min_value=1, 
                max_value=31,
                value=st.session_state.get('last_day_entered', 1),
                step=1
            )
            status = st.radio(
                _t('form_status_label', lang),
                options=[
                    _t('form_status_pass', lang), 
                    _t('form_status_fail', lang), 
                    _t('form_status_no_report', lang)
                ],
                horizontal=True
            )
            st.caption(_t('form_status_info', lang))
        
        submitted = st.form_submit_button(_t('form_submit_button', lang))

        with st.expander(_t('form_converters_expander', lang)):
            st.warning(_t('form_converters_warning', lang))
            st.json({
                "HIKE_RATE (Wędrówka)": 1500,
                "PRIMARY_RATE (Bieg)": 1300,
                "GENERIC_DISTANCE_RATE (Spacer)": 800,
                "CYCLE_RATE (Rower)": 550,
                "EBIKE_RATE (E-Rower)": 400,
                "STEPS_PER_MINUTE_RATE (Inne)": 60
            })

        notes = st.text_area(
            _t('form_notes_label', lang),
            placeholder=_t('form_notes_placeholder', lang)
        )
        
        uploaded_file = st.file_uploader(
            _t('form_upload_label', lang), 
            type=["png", "jpg", "jpeg"]
        )
        
        st.markdown("---")
        st.markdown(_t('form_thanks_note', lang))


    if submitted:
        if not submitter or not participant:
            st.error(_t('form_error_no_participant', lang))
            st.rerun() 

        st.session_state.submitter_index_plus_one = ([None] + submitters_list_sorted).index(submitter)
        st.session_state.last_day_entered = day + 1 if day < 31 else 31 

        status_key = "Zaliczone"
        if status == _t('form_status_fail', lang):
            status_key = "Niezaliczone"
        elif status == _t('form_status_no_report', lang):
            status_key = "Brak raportu"
        
        file_info = f"Załączono plik: {uploaded_file.name}" if uploaded_file else ""
        full_notes = f"{notes} | {file_info}".strip(" | ")
        timestamp = datetime.now().isoformat()

        try:
            sheet = connect_to_google_sheets()
            if sheet:
                worksheet_data = sheet.worksheet("BiezacaEdycja")
                worksheet_data.append_row([participant, day, status_key, full_notes, timestamp])
                
                worksheet_log = sheet.worksheet("LogWpisow")
                worksheet_log.append_row([submitter, participant, day, status_key, timestamp])
                
                st.session_state.last_submission = {
                    'participant': participant,
                    'day': day,
                    'status_translated': status,
                    'full_notes': full_notes
                }
                
                st.cache_data.clear() 
            else:
                st.error(_t('form_error_message', lang, "Nie można połączyć się z arkuszem."))
        except Exception as e:
            st.error(_t('form_error_message', lang, e))
            
        st.rerun()

# === Sekcja 2: Ranking Bieżącej Edycji ===

def process_raw_data(df_raw, lang):
    """
    Przetwarza surowe dane (append-only) z Google Sheets w strukturę "najnowszy wpis wygrywa".
    Zwraca słownik: {participant: {day: status}} oraz max_day
    """
    if df_raw.empty:
        return {}, 0, True 
        
    REQUIRED_COLS = ['Participant', 'Day', 'Status', 'Timestamp', 'Notes']
    if not all(col in df_raw.columns for col in REQUIRED_COLS):
        st.error(_t('current_header_check_error', lang))
        st.json({
            _t('current_header_check_expected', lang): REQUIRED_COLS,
            _t('current_header_check_found', lang): df_raw.columns.tolist()
        })
        return {}, 0, False 
        
    df_raw['Day'] = pd.to_numeric(df_raw['Day'], errors='coerce')
    df_raw = df_raw.dropna(subset=['Day'])
    if df_raw.empty:
        return {}, 0, True
        
    df_raw = df_raw.sort_values(by="Timestamp")
    
    processed_data = {}
    for _, row in df_raw.iterrows():
        participant = row['Participant']
        day = int(row['Day'])
        
        if participant not in processed_data:
            processed_data[participant] = {}
            
        processed_data[participant][day] = {
            "status": row['Status'],
            "notes": row['Notes']
        }
        
    max_day = int(df_raw['Day'].max())
    return processed_data, max_day, True


def calculate_ranking(data, max_day_reported, lang):
    """Oblicza ranking na podstawie zasad gry."""
    ranking_data = []
    elimination_map = {} 

    for participant in CURRENT_PARTICIPANTS:
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
        
        # <<< POPRAWKA 1 (Logika Klasyfikacji): Nowy klucz sortowania (failure_tuple) >>>
        def get_failure_tuple(p_failures, p_highest):
            # 0 = Zaliczone (lepiej), 1 = Niezaliczone (gorzej)
            # Sprawdzamy od najwyższego zaliczonego dnia w dół
            # Użyj max_day_reported, aby zapewnić, że gracze w grze są porównywani do tego samego punktu
            start_day = max(p_highest, max_day_reported) if not eliminated_on_day else p_highest
            # Jeśli gracz odpadł, liczy się tylko jego historia do odpadnięcia
            if eliminated_on_day:
                start_day = eliminated_on_day

            return tuple(1 if d in p_failures else 0 for d in range(start_day, 0, -1))

        ranking_data.append({
            _t('ranking_col_participant', lang): participant,
            _t('ranking_col_highest_pass', lang): highest_completed,
            "sort_key_failure_tuple": get_failure_tuple(failed_stages, highest_completed),
            _t('ranking_col_status', lang): status_text,
            _t('ranking_col_failed_list', lang): ", ".join(map(str, sorted(failed_stages)[:10])) + ("..." if len(failed_stages) > 10 else "")
        })
        elimination_map[participant] = eliminated_on_day 
    
    # <<< POPRAWKA 1 (Logika Klasyfikacji): Nowe sortowanie >>>
    def sort_key(entry):
        return (
            -entry[_t('ranking_col_highest_pass', lang)], # 1. Najwyższy zaliczony (malejąco)
            entry["sort_key_failure_tuple"]               # 2. Krotka porażek (rosnąco)
        )

    ranking_data.sort(key=sort_key)
    
    df_ranking = pd.DataFrame(ranking_data)
    df_ranking.index = df_ranking.index + 1 
    
    return df_ranking[[
        _t('ranking_col_participant', lang), 
        _t('ranking_col_highest_pass', lang), 
        _t('ranking_col_status', lang), 
        _t('ranking_col_failed_list', lang)
    ]], elimination_map


# <<< POPRAWKA 2 (Błąd logiki serii): Przebudowana funkcja >>>
def calculate_current_stats(data, max_day, lang, elimination_map):
    streaks = []
    for participant in CURRENT_PARTICIPANTS:
        # Pomiń, jeśli uczestnik odpadł
        if elimination_map.get(participant) is not None:
            continue

        days_data = data.get(participant, {})
        current_streak = 0
        
        # Licz wstecz od ostatniego zaraportowanego dnia
        for day in range(max_day, 0, -1):
            if day in days_data and days_data[day]["status"] == "Zaliczone":
                current_streak += 1
            else:
                # Seria przerwana (przez porażkę lub brak danych)
                break 
        
        streaks.append({"Uczestnik": participant, "Seria": current_streak})

    df_streaks = pd.DataFrame(streaks).sort_values(by="Seria", ascending=False)
    return df_streaks[df_streaks["Seria"] > 0] # Pokaż tylko aktywne serie > 0


def show_current_edition_dashboard(lang):
    """Wyświetla dashboard dla bieżącej edycji."""
    st.header(_t('current_header', lang))
    
    sheet = connect_to_google_sheets()
    if not sheet:
        return 

    df_raw_data = load_google_sheet_data(sheet, "BiezacaEdycja")
    df_raw_logs = load_google_sheet_data(sheet, "LogWpisow")
    
    if df_raw_data.empty:
        st.info(_t('current_no_data', lang))
        return

    current_data, max_day_reported, success = process_raw_data(df_raw_data, lang)
    if not success:
        return

    st.subheader(_t('current_ranking_header', lang))
    st.markdown(_t('current_ranking_rules', lang))
    
    try:
        ranking_df, elimination_map = calculate_ranking(current_data, max_day_reported, lang)
        st.dataframe(ranking_df, use_container_width=True)
    except Exception as e:
        st.error(_t('current_ranking_error', lang, e))
        elimination_map = {} 

    
    days_to_show_count = 15
    st.subheader(_t('current_completeness_header', lang, days_to_show_count))
    
    pivot_data = []
    
    for participant in CURRENT_PARTICIPANTS:
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
                _t('completeness_col_participant', lang): participant,
                _t('completeness_col_day', lang): day,
                "Status": status_icon
            })
            
    if not pivot_data:
        st.info(_t('current_completeness_no_data', lang))
        return

    df_pivot = pd.DataFrame(pivot_data)
    
    start_day = max(1, max_day_reported - (days_to_show_count - 1))
    days_to_show = [day for day in range(start_day, max_day_reported + 1)]
    
    completeness_pivot = df_pivot.pivot(
        index=_t('completeness_col_participant', lang),
        columns=_t('completeness_col_day', lang),
        values="Status"
    ).reindex(columns=days_to_show, fill_value="").reindex(index=sorted(CURRENT_PARTICIPANTS))
    
    st.dataframe(completeness_pivot, use_container_width=True)

    # --- NOWA SEKCJA: Statystyki Bieżącej Edycji ---
    st.subheader(_t('current_stats_header', lang))
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"**{_t('current_stats_top_submitters', lang)}**")
        st.caption(_t('current_stats_top_submitters_desc', lang))
        if not df_raw_logs.empty and 'Submitter' in df_raw_logs.columns:
            top_submitters = df_raw_logs['Submitter'].value_counts().nlargest(3)
            for name, count in top_submitters.items():
                # <<< POPRAWKA 3 (Błąd 'mention'): Dodano url=None >>>
                mention(label=f"**{name}** ({count} wpisów)", icon="🏆", url=None)
        else:
            st.info("Brak danych w logach wpisów.")

    with col2:
        st.markdown(f"**{_t('current_stats_streaks', lang)}**")
        st.caption(_t('current_stats_streaks_desc', lang))
        # <<< POPRAWKA 2: Przekazanie mapy eliminacji do funkcji >>>
        df_streaks = calculate_current_stats(current_data, max_day_reported, lang, elimination_map)
        if not df_streaks.empty:
            for _, row in df_streaks.iterrows():
                # <<< POPRAWKA 3 (Błąd 'mention'): Dodano url=None >>>
                mention(label=f"**{row['Uczestnik']}** ({row['Seria']} {_t('current_stats_streaks_days', lang)})", icon="🔥", url=None)
        else:
            st.info("Brak aktywnych serii.")
            
    st.markdown("---")

    st.subheader(_t('current_stats_race_header', lang))
    st.write(_t('current_stats_race_desc', lang))
    
    if st.button(_t('current_stats_race_button', lang)):
        chart_placeholder = st.empty()
        scores = {p: 0 for p in CURRENT_PARTICIPANTS}
        
        for day in range(1, max_day_reported + 1):
            
            for p in CURRENT_PARTICIPANTS:
                if p in current_data and day in current_data[p] and current_data[p][day]["status"] == "Zaliczone":
                    scores[p] += 1
            
            df_race = pd.DataFrame.from_dict(
                scores, 
                orient='index', 
                columns=[_t('current_stats_race_total', lang)]
            ).sort_values(by=_t('current_stats_race_total', lang), ascending=True)
            
            with chart_placeholder.container():
                st.subheader(f"{_t('current_stats_race_day', lang)}: {day}")
                st.bar_chart(df_race, horizontal=True)
            
            time.sleep(0.2) 


    if st.checkbox(_t('current_log_expander', lang)):
        if not df_raw_logs.empty:
            df_log_sorted = df_raw_logs.sort_values("Timestamp", ascending=False)
            st.dataframe(df_log_sorted, use_container_width=True)
        else:
            st.info(_t('current_log_empty', lang))


# === Sekcja 3: Statystyki Historyczne (Twój istniejący kod) ===

@st.cache_data
def load_historical_data_from_json():
    """Wczytuje historyczne dane z lokalnego pliku JSON."""
    if not os.path.exists(FILE_HISTORICAL):
        st.error(f"Plik `{FILE_HISTORICAL}` nie został znaleziony w repozytorium!")
        return pd.DataFrame()
        
    try:
        with open(FILE_HISTORICAL, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        st.error(f"Błąd odczytu pliku JSON `{FILE_HISTORICAL}`: {e}")
        return pd.DataFrame()

    if not data:
        return pd.DataFrame()

    records = []
    for user, editions in data.items():
        for edition, details in editions.items():
            if details.get("status") == "PAUZA":
                continue
            
            rezultat_str = details.get("rezultat_uczestnika")
            miejsce_val = details.get("miejsce")
            rezultat_numeric = pd.to_numeric(rezultat_str, errors='coerce')
            
            if pd.isna(miejsce_val) or pd.isna(rezultat_numeric):
                continue
            
            records.append({
                'uczestnik': user,
                'miesiac_rok_str': edition,
                'miesiac': datetime.strptime(edition, '%m.%Y'),
                'rezultat_raw': rezultat_str,
                'rezultat_numeric': rezultat_numeric,
                'miejsce': pd.to_numeric(miejsce_val, errors='coerce')
            })
    
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df = df.sort_values(by='miesiac').reset_index(drop=True)
    df['edycja_nr'] = df['miesiac'].rank(method='dense').astype(int)

    return df

def show_historical_stats(lang):
    """Cały Twój istniejący kod do wyświetlania statystyk historycznych."""
    
    st.header(_t('title', lang))
    
    df = load_historical_data_from_json() 

    if df.empty:
        st.info("Brak danych historycznych do wyświetlenia.")
        st.stop()

    st.sidebar.markdown("---")
    st.sidebar.header(_t('sidebar_header', lang))

    min_editions_count = st.sidebar.slider(
        _t('min_editions', lang),
        min_value=1,
        max_value=int(df['uczestnik'].value_counts().max()),
        value=1,
        key="hist_min_editions"
    )

    user_counts = df['uczestnik'].value_counts()
    eligible_users = user_counts[user_counts >= min_editions_count].index.tolist()
    eligible_df = df[df['uczestnik'].isin(eligible_users)]

    if eligible_df.empty:
        st.warning(_t('no_data_selected', lang))
        st.stop()

    all_users_sorted = sorted(eligible_df['uczestnik'].unique())
    selected_users_all = st.sidebar.checkbox(_t('select_all_users', lang), value=True, key="hist_all_users")
    if selected_users_all:
        selected_users = all_users_sorted
    else:
        selected_users = st.sidebar.multiselect(
            _t('select_users', lang),
            all_users_sorted,
            default=all_users_sorted[:5],
            key="hist_select_users"
        )

    period_option_labels = [
        _t('all_editions', lang), 
        _t('last_n_editions', lang, ''), 
        _t('manual_select', lang)
    ]
    period_option = st.sidebar.radio(
        _t('select_period', lang),
        options=period_option_labels,
        index=0,
        key="hist_period"
    )

    filtered_df = eligible_df[eligible_df['uczestnik'].isin(selected_users)].copy()

    if period_option == _t('last_n_editions', lang, ''):
        n_val = min(12, filtered_df['edycja_nr'].max()) if not filtered_df.empty else 1
        n_max = filtered_df['edycja_nr'].max() if not filtered_df.empty else 1
        n_editions = st.sidebar.slider(
            _t('last_n_editions', lang, n_val), 
            min_value=1, 
            max_value=n_max, 
            value=n_val, 
            key="hist_n_editions"
        )
        if not filtered_df.empty:
            max_edycja_nr = filtered_df['edycja_nr'].max()
            min_edycja_nr = max_edycja_nr - n_editions + 1
            filtered_df = filtered_df[filtered_df['edycja_nr'] >= min_edycja_nr]

    elif period_option == _t('manual_select', lang):
        if not filtered_df.empty:
            unique_months = filtered_df['miesiac'].dt.to_period('M').unique().to_timestamp()
            start_date, end_date = st.sidebar.select_slider(
                _t('manual_select', lang),
                options=sorted(unique_months),
                value=(unique_months.min(), unique_months.max()),
                format_func=lambda x: x.strftime('%Y-%m'),
                key="hist_slider"
            )
            filtered_df = filtered_df[(filtered_df['miesiac'] >= pd.to_datetime(start_date)) & (filtered_df['miesiac'] <= pd.to_datetime(end_date))]
        else:
            st.sidebar.warning(_t('no_data_selected', lang))

    if filtered_df.empty or not selected_users:
        st.warning(_t('no_data_selected', lang))
        st.stop()

    chart_type_labels = [_t('results', lang), _t('positions', lang)]
    chart_type = st.sidebar.radio(_t('chart_type', lang), chart_type_labels, key="hist_chart_type")

    st.subheader(_t('user_details_header', lang))
    if len(selected_users) == 1:
        user = selected_users[0]
        user_df = filtered_df[filtered_df['uczestnik'] == user]
        col1, col2, col3, col4 = st.columns(4)
        best_result_row = user_df.loc[user_df['rezultat_numeric'].idxmax()] if not user_df['rezultat_numeric'].isnull().all() else None
        col1.metric(label=_t('best_result', lang), value=f"{best_result_row['rezultat_raw']} ({best_result_row['miesiac_rok_str']})" if best_result_row is not None else "N/A")
        worst_result_row = user_df.loc[user_df['rezultat_numeric'].idxmin()] if not user_df['rezultat_numeric'].isnull().all() else None
        col2.metric(label=_t('worst_result', lang), value=f"{worst_result_row['rezultat_raw']} ({worst_result_row['miesiac_rok_str']})" if worst_result_row is not None else "N/A")
        best_position_row = user_df.loc[user_df['miejsce'].idxmin()] if not user_df['miejsce'].isnull().all() else None
        col3.metric(label=_t('best_position', lang), value=f"{int(best_position_row['miejsce'])} ({best_position_row['miesiac_rok_str']})" if best_position_row is not None else "N/A")
        worst_position_row = user_df.loc[user_df['miejsce'].idxmax()] if not user_df['miejsce'].isnull().all() else None
        col4.metric(label=_t('worst_position', lang), value=f"{int(worst_position_row['miejsce'])} ({worst_position_row['miesiac_rok_str']})" if worst_position_row is not None else "N/A")
    else:
        st.info(_t('select_single_user', lang))

    st.subheader(_t('comparison_chart_title_results', lang) if chart_type == _t('results', lang) else _t('comparison_chart_title_positions', lang))

    if chart_type == _t('results', lang):
        plot_df = filtered_df.copy()
        y_col, y_label = 'rezultat_numeric', _t('y_axis_results', lang)
        invert_yaxis = False
    else: 
        plot_df = filtered_df.copy()
        y_col, y_label = 'miejsce', _t('y_axis_positions', lang)
        invert_yaxis = True 

    if not plot_df.empty:
        fig, ax = plt.subplots(figsize=(16, 8))
        plt.style.use('dark_background')
        ax.set_facecolor('#0e1117')
        fig.patch.set_facecolor('#0e1117')

        for user in selected_users:
            user_data = plot_df[plot_df['uczestnik'] == user].sort_values('miesiac')
            user_data_for_plot = user_data.dropna(subset=[y_col])
            if not user_data_for_plot.empty:
                ax.plot(user_data_for_plot['miesiac'], user_data_for_plot[y_col], marker='o', linestyle='-', label=user)
                
                last_point = user_data_for_plot.iloc[-1]
                ax.text(last_point['miesiac'], last_point[y_col], f" {user}", verticalalignment='center', fontsize=9, color=ax.get_lines()[-1].get_color())

        ax.set_xlabel(_t('x_axis_month', lang))
        ax.set_ylabel(y_label)
        ax.legend().set_visible(False)
        ax.grid(True, which='both', linestyle='--', linewidth=0.3)
        plt.xticks(rotation=45, ha="right")
        
        if invert_yaxis:
            ax.invert_yaxis() 

        plt.tight_layout()
        st.pyplot(fig) 
    else:
        st.info(_t('no_data_selected', lang))

    st.subheader(_t('monthly_summary', lang))
    st.write(_t('monthly_summary_desc', lang))

    summary_data = filtered_df.copy()
    if not summary_data.empty:
        sorted_columns = filtered_df['miesiac'].sort_values().dt.strftime('%m.%Y').unique()
        
        st.subheader(_t('monthly_summary_results', lang))
        monthly_results_pivot = summary_data.pivot_table(
            index='uczestnik',
            columns='miesiac_rok_str',
            values='rezultat_raw', 
            aggfunc='first'
        ).fillna('—')
        monthly_results_pivot = monthly_results_pivot.reindex(columns=sorted_columns)
        
        avg_result_sort = summary_data.groupby('uczestnik')['rezultat_numeric'].mean().sort_values(ascending=False)
        monthly_results_pivot = monthly_results_pivot.reindex(index=avg_result_sort.index)
        st.dataframe(monthly_results_pivot)

        st.subheader(_t('monthly_summary_positions', lang))
        monthly_positions_pivot = summary_data.pivot_table(
            index='uczestnik',
            columns='miesiac_rok_str',
            values='miejsce',
            aggfunc=lambda x: f"{int(x.iloc[0])}" if pd.notna(x.iloc[0]) else '—'
        ).fillna('—')
        monthly_positions_pivot = monthly_positions_pivot.reindex(columns=sorted_columns)
        
        avg_pos_sort = summary_data.groupby('uczestnik')['miejsce'].mean().sort_values()
        monthly_positions_pivot = monthly_positions_pivot.reindex(index=avg_pos_sort.index)
        st.dataframe(monthly_positions_pivot)
    else:
        st.info(_t('no_data_selected', lang))

    st.subheader(_t('medal_race_title', lang))
    st.write(_t('medal_race_desc', lang))

    medal_range_labels = [
        _t('top_1', lang), _t('top_3', lang), _t('top_5', lang), 
        _t('top_10', lang), _t('custom_range', lang)
    ]
    medal_range_option = st.selectbox(
        _t('select_medal_range', lang),
        medal_range_labels,
        key="hist_medal_range"
    )

    min_medal_pos = 1
    max_medal_pos = 0

    if medal_range_option == _t('top_1', lang):
        max_medal_pos = 1
    elif medal_range_option == _t('top_3', lang):
        max_medal_pos = 3
    elif medal_range_option == _t('top_5', lang):
        max_medal_pos = 5
    elif medal_range_option == _t('top_10', lang):
        max_medal_pos = 10
    elif medal_range_option == _t('custom_range', lang):
        col_min, col_max = st.columns(2)
        with col_min:
            min_medal_pos = st.number_input(_t('min_medal_position', lang), min_value=1, value=1, step=1, key="hist_min_medal")
        with col_max:
            max_possible_pos = int(df['miejsce'].max()) if not df['miejsce'].isnull().all() else 10
            max_medal_pos = st.number_input(_t('max_medal_position', lang), min_value=min_medal_pos, value=max(min_medal_pos, 3), max_value=max_possible_pos, step=1, key="hist_max_medal")

    medals_history_df = df.dropna(subset=['miejsce'])

    if max_medal_pos > 0:
        medals_history_df = medals_history_df[
            (medals_history_df['miejsce'] >= min_medal_pos) & 
            (medals_history_df['miejsce'] <= max_medal_pos)
        ]

    if not medals_history_df.empty:
        medals_history_df = medals_history_df.sort_values('edycja_nr')
        medals_history_df['medal_count'] = 1
        
        medals_per_edition_per_participant = medals_history_df.groupby(['uczestnik', 'edycja_nr'])['medal_count'].sum().reset_index()

        race_pivot = medals_per_edition_per_participant.pivot_table(
            index='edycja_nr', 
            columns='uczestnik', 
            values='medal_count'
        )
        
        all_editions_idx = range(1, df['edycja_nr'].max() + 1)
        race_pivot = race_pivot.reindex(all_editions_idx).fillna(0) 

        race_pivot = race_pivot.cumsum()
        
        race_long = race_pivot.melt(
            var_name='uczestnik', 
            value_name='laczna_liczba_medali', 
            ignore_index=False
        ).reset_index()

        race_long_filtered = race_long[race_long['uczestnik'].isin(selected_users)]

        if not race_long_filtered.empty:
            fig_race, ax_race = plt.subplots(figsize=(16, 8))
            plt.style.use('dark_background')
            ax_race.set_facecolor('#0e1117')
            fig_race.patch.set_facecolor('#0e1117')

            for user in race_long_filtered['uczestnik'].unique():
                user_data = race_long_filtered[race_long_filtered['uczestnik'] == user].sort_values('edycja_nr')
                ax_race.plot(
                    user_data['edycja_nr'],
                    user_data['laczna_liczba_medali'],
                    marker='o',
                    linestyle='-',
                    label=user
                )
                if not user_data.empty:
                    last_point = user_data.iloc[-1]
                    ax_race.text(
                        last_point['edycja_nr'],
                        last_point['laczna_liczba_medali'],
                        f" {user}",
                        verticalalignment='center',
                        fontsize=9,
                        color=ax_race.get_lines()[-1].get_color()
                    )

            medal_title_text = ""
            if max_medal_pos == 1:
                medal_title_text = _t('cumulative_medals', lang, 1)
            elif medal_range_option == _t('custom_range', lang):
                medal_title_text = f"{_t('cumulative_medals', lang, '')} ({min_medal_pos}-{max_medal_pos})"
            else:
                medal_title_text = _t('cumulative_medals', lang, max_medal_pos)

            ax_race.set_title(_t('medal_race_title', lang))
            ax_race.set_xlabel(_t('x_axis_edition', lang))
            ax_race.set_ylabel(medal_title_text)
            ax_race.legend().set_visible(False)
            ax_race.grid(True, which='both', linestyle='--', linewidth=0.3)
            st.pyplot(fig_race)
        else:
            st.info(_t('no_data_selected', lang))
    else:
        st.info(_t('no_data_selected', lang))

    st.subheader(_t('heatmap_title', lang))
    st.write(_t('heatmap_desc', lang))
    heatmap_df = filtered_df.dropna(subset=['miejsce'])
    if not heatmap_df.empty:
        heatmap_pivot = heatmap_df.pivot_table(
            index='uczestnik', 
            columns='miesiac_rok_str', 
            values='miejsce'
        )
        sorted_cols = filtered_df['miesiac'].sort_values().dt.strftime('%m.%Y').unique()
        heatmap_pivot = heatmap_pivot.reindex(columns=sorted_cols)
        avg_pos_hm = heatmap_df.groupby('uczestnik')['miejsce'].mean().sort_values().index
        heatmap_pivot = heatmap_pivot.reindex(index=avg_pos_hm)

        fig_heatmap, ax_heatmap = plt.subplots(figsize=(18, max(6, len(heatmap_pivot.index) * 0.5)))
        sns.heatmap(
            heatmap_pivot, 
            annot=True, 
            fmt=".0f", 
            cmap="viridis_r", 
            linewidths=.5, 
            ax=ax_heatmap,
            cbar_kws={'label': _t('position', lang)}
        )
        ax_heatmap.set_title(_t('heatmap_title', lang))
        ax_heatmap.set_xlabel(_t('edition', lang))
        ax_heatmap.set_ylabel(_t('participant', lang))
        plt.xticks(rotation=45)
        st.pyplot(fig_heatmap)
    else:
        st.info(_t('no_data_selected', lang))

    st.subheader(_t('scatter_plot_title', lang))
    st.write(_t('scatter_plot_desc', lang))

    scatter_df = filtered_df.dropna(subset=['rezultat_numeric', 'miejsce'])
    if not scatter_df.empty:
        fig_scatter, ax_scatter = plt.subplots(figsize=(16, 8))
        plt.style.use('dark_background')
        ax_scatter.set_facecolor('#0e1117')
        fig_scatter.patch.set_facecolor('#0e1117')

        unique_positions = sorted(scatter_df['miejsce'].dropna().unique())
        
        custom_palette = {}
        for pos in unique_positions:
            if pos == 1:
                custom_palette[pos] = 'red'
            elif pos == 2:
                custom_palette[pos] = 'orange'
            elif pos == 3:
                custom_palette[pos] = 'yellow'
            else:
                if len(unique_positions) > 3:
                    viridis_idx = int(np.interp(pos, [unique_positions[3], unique_positions[-1]], [0, len(sns.color_palette("viridis", n_colors=max(1, len(unique_positions) - 3))) - 1]))
                    custom_palette[pos] = sns.color_palette("viridis", n_colors=max(1, len(unique_positions) - 3))[viridis_idx]
                else:
                    custom_palette[pos] = 'gray'

        sns.scatterplot(
            data=scatter_df,
            x='miesiac',
            y='rezultat_numeric',
            hue='miejsce', 
            palette=custom_palette, 
            size='miejsce', 
            sizes=(50, 400), 
            alpha=0.7,
            ax=ax_scatter,
            legend='full'
        )
        
        for user in selected_users:
            user_data = scatter_df[scatter_df['uczestnik'] == user].sort_values('miesiac')
            if not user_data.empty:
                for i, row in user_data.iterrows():
                    ax_scatter.text(row['miesiac'], row['rezultat_numeric'], f" {user}", 
                                    verticalalignment='bottom', horizontalalignment='left', 
                                    fontsize=7, color='white', alpha=0.8)

        ax_scatter.set_xlabel(_t('x_axis_month', lang))
        ax_scatter.set_ylabel(_t('y_axis_results', lang))
        ax_scatter.set_title(_t('scatter_plot_title', lang))
        ax_scatter.grid(True, which='both', linestyle='--', linewidth=0.3)
        plt.xticks(rotation=45, ha="right")
        
        handles, labels = ax_scatter.get_legend_handles_labels()
        
        numeric_labels_with_handles = []
        for i, label_str in enumerate(labels[1:]): 
            try:
                numeric_labels_with_handles.append((int(float(label_str)), handles[i+1]))
            except ValueError:
                pass
        
        numeric_labels_with_handles.sort(key=lambda x: x[0])
        sorted_handles = [h for _, h in numeric_labels_with_handles]
        sorted_labels = [str(l) for l, _ in numeric_labels_with_handles]

        sorted_handles.insert(0, handles[0])
        sorted_labels.insert(0, labels[0])

        ax_scatter.legend(sorted_handles, sorted_labels, title=_t('position_legend', lang), bbox_to_anchor=(1.05, 1), loc='upper left')

        plt.tight_layout()
        st.pyplot(fig_scatter)
    else:
        st.info(_t('no_data_selected', lang))

    col1, col2 = st.columns(2)

    with col1:
        st.subheader(_t('medal_classification_title', lang))
        all_positions_df = filtered_df.dropna(subset=['miejsce'])
        if not all_positions_df.empty:
            position_counts = pd.crosstab(all_positions_df['uczestnik'], all_positions_df['miejsce'])
            
            all_possible_positions = range(1, int(all_positions_df['miejsce'].max()) + 1)
            for pos in all_possible_positions:
                if pos not in position_counts.columns:
                    position_counts[pos] = 0
            
            position_counts = position_counts.reindex(columns=sorted(position_counts.columns), fill_value=0)
            
            participation_count = filtered_df['uczestnik'].value_counts().rename(_t('total_participations', lang))
            position_counts = position_counts.join(participation_count)
            
            sort_cols = [col for col in position_counts.columns if isinstance(col, (int, np.integer))]
            position_counts = position_counts.sort_values(by=sort_cols, ascending=[False]*len(sort_cols))
            
            st.dataframe(position_counts)
        else:
            st.info(_t('no_data_selected', lang))

    with col2:
        st.subheader(_t('medal_classification_classic_title', lang))
        if not all_positions_df.empty:
            top3_positions_df = all_positions_df[all_positions_df['miejsce'].isin([1, 2, 3])]
            
            if not top3_positions_df.empty:
                medal_counts = pd.crosstab(top3_positions_df['uczestnik'], top3_positions_df['miejsce'])
                
                for pos in [1, 2, 3]:
                    if pos not in medal_counts.columns:
                        medal_counts[pos] = 0
                
                medal_counts = medal_counts[[1, 2, 3]]
                medal_counts.columns = ['1. miejsce', '2. miejsce', '3. miejsce']
                
                medal_counts[_t('total_medals_col', lang)] = medal_counts['1. miejsce'] + medal_counts['2. miejsce'] + medal_counts['3. miejsce']
                
                medal_counts = medal_counts.sort_values(by=['1. miejsce', '2. miejsce', '3. miejsce'], ascending=[False, False, False])
                
                st.dataframe(medal_counts)
            else:
                st.info(_t('no_data_selected', lang))
        else:
            st.info(_t('no_data_selected', lang))

    st.subheader(_t('player_stats', lang))
    stats_df = df[df['uczestnik'].isin(eligible_users)].copy()
    if not stats_df.empty:
        agg_funcs = {
            'count': ('rezultat_numeric', 'count'),
            'mean_result': ('rezultat_numeric', 'mean'),
            'median_result': ('rezultat_numeric', 'median'),
            'min_result': ('rezultat_numeric', 'min'),
            'max_result': ('rezultat_numeric', 'max'),
            'mean_pos': ('miejsce', 'mean'),
            'median_pos': ('miejsce', 'median'),
            'best_pos': ('miejsce', 'min'),
        }
        player_stats = stats_df.groupby('uczestnik').agg(**agg_funcs).reset_index()
        player_stats.columns = [
            _t('participant', lang), _t('count_col', lang), 
            f"{_t('mean_col', lang)} ({_t('results', lang)})", f"{_t('median_col', lang)} ({_t('results', lang)})", f"{_t('min_col', lang)} ({_t('results', lang)})", f"{_t('max_col', lang)} ({_t('results', lang)})",
            f"{_t('mean_col', lang)} ({_t('positions', lang)})", f"{_t('median_col', lang)} ({_t('positions', lang)})", f"{_t('best_position', lang)}"
        ]
        
        col_mean_res = f"{_t('mean_col', lang)} ({_t('results', lang)})"
        col_median_res = f"{_t('median_col', lang)} ({_t('results', lang)})"
        col_mean_pos = f"{_t('mean_col', lang)} ({_t('positions', lang)})"
        col_median_pos = f"{_t('median_col', lang)} ({_t('positions', lang)})"
        
        player_stats[col_mean_res] = player_stats[col_mean_res].round(1)
        player_stats[col_median_res] = player_stats[col_median_res].round(1)
        player_stats[col_mean_pos] = player_stats[col_mean_pos].round(1)
        player_stats[col_median_pos] = player_stats[col_median_pos].round(1)

        st.dataframe(player_stats.set_index(_t('participant', lang)).sort_values(by=col_mean_pos))
    else:
        st.info(_t('no_data_selected', lang))

    st.subheader(_t('participants_per_edition', lang))
    if not df.empty:
        participants_per_edition = df.groupby('miesiac_rok_str')['uczestnik'].nunique().reset_index()
        participants_per_edition.columns = ['miesiac_rok_str', _t('count_col', lang)] 
        participants_per_edition['miesiac'] = participants_per_edition['miesiac_rok_str'].apply(lambda x: datetime.strptime(x, '%m.%Y'))
        participants_per_edition = participants_per_edition.sort_values('miesiac').drop(columns='miesiac')
        
        st.dataframe(participants_per_edition.set_index('miesiac_rok_str')) 

        fig_participants, ax_participants = plt.subplots(figsize=(16, 6))
        plt.style.use('dark_background')
        ax_participants.set_facecolor('#0e1117')
        fig_participants.patch.set_facecolor('#0e1117')

        ax_participants.plot(
            participants_per_edition['miesiac_rok_str'],
            participants_per_edition[_t('count_col', lang)],
            marker='o',
            linestyle='-',
            color='skyblue'
        )
        ax_participants.set_title(_t('participants_chart_title', lang))
        ax_participants.set_xlabel(_t('edition', lang))
        ax_participants.set_ylabel(_t('participants_chart_ylabel', lang))
        ax_participants.grid(True, which='both', linestyle='--', linewidth=0.3)
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        st.pyplot(fig_participants)
    else:
        st.info(_t('no_data_selected', lang))

    st.subheader(_t('avg_result_pos_per_edition', lang))
    if not df.empty:
        avg_edition_stats = df.groupby('miesiac_rok_str').agg(
            avg_result=('rezultat_numeric', 'mean'),
        ).reset_index()
        avg_edition_stats.columns = ['miesiac_rok_str', _t('avg_result_edition', lang)] 
        
        avg_edition_stats[_t('avg_result_edition', lang)] = avg_edition_stats[_t('avg_result_edition', lang)].round(1)

        avg_edition_stats['miesiac'] = avg_edition_stats['miesiac_rok_str'].apply(lambda x: datetime.strptime(x, '%m.%Y'))
        avg_edition_stats = avg_edition_stats.sort_values('miesiac').drop(columns='miesiac')
        st.dataframe(avg_edition_stats.set_index('miesiac_rok_str'))

        fig_avg_stats, ax_avg_stats = plt.subplots(figsize=(16, 6))
        plt.style.use('dark_background')
        ax_avg_stats.set_facecolor('#0e1117')
        fig_avg_stats.patch.set_facecolor('#0e1117')

        ax_avg_stats.plot(
            avg_edition_stats['miesiac_rok_str'],
            avg_edition_stats[_t('avg_result_edition', lang)],
            marker='o',
            linestyle='-',
            color='lightgreen'
        )
        ax_avg_stats.set_title(f"{_t('avg_result_edition', lang)} w poszczególnych edycjach")
        ax_avg_stats.set_xlabel(_t('edition', lang))
        ax_avg_stats.set_ylabel(_t('avg_result_edition', lang))
        ax_avg_stats.grid(True, which='both', linestyle='--', linewidth=0.3)

        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        st.pyplot(fig_avg_stats)
    else:
        st.info(_t('no_data_selected', lang))

    st.subheader(_t('edition_ranking_title', lang))
    st.write(_t('edition_ranking_desc', lang))
    if not df.empty:
        edition_ranking_data = []
        
        df_sorted_by_edition_full = df.sort_values(by='edycja_nr').copy()

        for ed_nr in sorted(df_sorted_by_edition_full['edycja_nr'].unique()):
            edition_data = df_sorted_by_edition_full[df_sorted_by_edition_full['edycja_nr'] == ed_nr]
            
            avg_result_ed = edition_data['rezultat_numeric'].mean()

            winner = "N/A"
            if not edition_data['miejsce'].isnull().all():
                best_place_in_edition = edition_data['miejsce'].min()
                winners_in_edition = edition_data[edition_data['miejsce'] == best_place_in_edition]['uczestnik'].unique()
                winner = ", ".join(winners_in_edition)

            edition_ranking_data.append({
                'Miesiąc/Rok': edition_data['miesiac_rok_str'].iloc[0],
                _t('avg_result_edition', lang): avg_result_ed.round(1) if pd.notna(avg_result_ed) else 'N/A',
                _t('participants_chart_ylabel', lang): edition_data['uczestnik'].nunique(),
                _t('edition_winner', lang): winner
            })
        
        edition_ranking = pd.DataFrame(edition_ranking_data)
        
        edition_ranking['miesiac_sort'] = edition_ranking['Miesiąc/Rok'].apply(lambda x: datetime.strptime(x, '%m.%Y'))
        edition_ranking = edition_ranking.sort_values('miesiac_sort').drop(columns='miesiac_sort')

        st.dataframe(edition_ranking.set_index('Miesiąc/Rok'))
    else:
        st.info(_t('no_data_selected', lang))

    st.subheader(_t('overall_records_title', lang))
    st.write(_t('overall_records_desc', lang))

    if not df.empty:
        overall_records = []
        current_best_result = -np.inf 
        
        df_sorted_by_edition = df.sort_values(by='edycja_nr').copy()

        for ed_nr in sorted(df_sorted_by_edition['edycja_nr'].unique()):
            edition_data = df_sorted_by_edition[df_sorted_by_edition['edycja_nr'] == ed_nr]
            
            best_result_in_edition = edition_data['rezultat_numeric'].max()
            
            if pd.notna(best_result_in_edition) and best_result_in_edition > current_best_result:
                record_holders_in_edition = edition_data[edition_data['rezultat_numeric'] == best_result_in_edition]['uczestnik'].unique()
                
                overall_records.append({
                    _t('edition', lang): edition_data['miesiac_rok_str'].iloc[0],
                    _t('record_holder', lang): ", ".join(record_holders_in_edition),
                    _t('record_value', lang): f"{best_result_in_edition:.1f}",
                    _t('previous_record', lang): f"{current_best_result:.1f}" if current_best_result != -np.inf else "N/A"
                })
                current_best_result = best_result_in_edition
        
        if overall_records:
            st.dataframe(pd.DataFrame(overall_records))
        else:
            st.info(_t('no_data_selected', lang))
    else:
        st.info(_t('no_data_selected', lang))

    st.subheader(_t('personal_records_timeline_title', lang))
    st.write(_t('personal_records_timeline_desc', lang))

    if not df.empty:
        personal_records_timeline = []
        
        for user in df['uczestnik'].unique():
            user_df = df[df['uczestnik'] == user].sort_values(by='edycja_nr').copy()
            
            current_personal_best = -np.inf 
            
            for index, row in user_df.iterrows():
                if pd.notna(row['rezultat_numeric']) and row['rezultat_numeric'] > current_personal_best:
                    personal_records_timeline.append({
                        _t('participant', lang): user,
                        _t('edition', lang): row['miesiac_rok_str'],
                        _t('new_record', lang): f"{row['rezultat_numeric']:.1f}",
                        _t('old_record', lang): f"{current_personal_best:.1f}" if current_personal_best != -np.inf else "Brak"
                    })
                    current_personal_best = row['rezultat_numeric']
        
        if personal_records_timeline:
            personal_records_df = pd.DataFrame(personal_records_timeline)
            personal_records_df['miesiac_sort'] = personal_records_df[_t('edition', lang)].apply(lambda x: datetime.strptime(x, '%m.%Y'))
            personal_records_df = personal_records_df.sort_values(by='miesiac_sort').drop(columns='miesiac_sort')
            st.dataframe(personal_records_df)
        else:
            st.info(_t('no_data_selected', lang))
    else:
        st.info(_t('no_data_selected', lang))

    st.subheader(_t('survival_analysis_title', lang))
    st.write(_t('survival_analysis_desc', lang))

    all_editions_sorted = sorted(df['miesiac_rok_str'].unique(), key=lambda x: datetime.strptime(x, '%m.%Y'), reverse=True)

    selected_editions_survival = st.multiselect(
        _t('survival_analysis_select_editions', lang),
        options=all_editions_sorted,
        default=all_editions_sorted[:min(3, len(all_editions_sorted))],
        key="hist_survival_select"
    )

    if not selected_editions_survival:
        st.info(_t('survival_analysis_no_selection', lang))
    else:
        fig_survival, ax_survival = plt.subplots(figsize=(16, 8))
        plt.style.use('dark_background')
        ax_survival.set_facecolor('#0e1117')
        fig_survival.patch.set_facecolor('#0e1117')

        max_day_overall = 0 

        for edition_str in selected_editions_survival:
            edition_df = df[df['miesiac_rok_str'] == edition_str].copy()
            
            if not edition_df.empty:
                edition_df['dropout_day'] = edition_df['rezultat_numeric'] + 3
                
                max_dropout_day_in_edition = int(edition_df['dropout_day'].max()) if not edition_df['dropout_day'].isnull().all() else 3
                
                competition_days = np.arange(1, max_dropout_day_in_edition + 2) 

                active_participants_count = []
                for day in competition_days:
                    active_count = (edition_df['dropout_day'] > day).sum()
                    active_participants_count.append(active_count)
                
                last_active_day_index = next((i for i, count in reversed(list(enumerate(active_participants_count))) if count > 0), 0)
                
                if active_participants_count and active_participants_count[last_active_day_index] > 0:
                    current_max_day = competition_days[last_active_day_index] + 1 
                elif competition_days.any():
                    current_max_day = competition_days[last_active_day_index]
                else:
                    current_max_day = 1

                max_day_overall = max(max_day_overall, current_max_day)

                ax_survival.plot(competition_days, active_participants_count, marker='.', linestyle='-', label=edition_str)

        ax_survival.set_title(_t('survival_analysis_title', lang))
        ax_survival.set_xlabel(_t('survival_analysis_x_axis', lang))
        ax_survival.set_ylabel(_t('survival_analysis_y_axis', lang))
        ax_survival.legend(title=_t('survival_analysis_legend', lang))
        ax_survival.grid(True, which='both', linestyle='--', linewidth=0.3)
        
        ax_survival.yaxis.get_major_locator().set_params(integer=True)
        
        if max_day_overall > 0:
            ax_survival.set_xlim(1, max_day_overall)
        
        plt.tight_layout()
        st.pyplot(fig_survival)

# === Główna funkcja sterująca aplikacją ===

def main():
    """Główna funkcja renderująca aplikację Streamlit."""
    
    st.sidebar.title(_t('nav_header', 'pl')) # Nagłówek jest stały
    
    lang = st.sidebar.selectbox("Język / Language", ["pl", "en"])
    
    # Inicjalizacja pamięci sesji
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
