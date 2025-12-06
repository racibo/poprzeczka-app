import pandas as pd
import streamlit as st
import json
from translations import _t

# Zmiana nazwy argumentu 'sheet' na '_sheet' jest kluczowa dla st.cache_data!
# Zapobiega to błędowi "UnhashableParamError".
@st.cache_data(ttl=600, show_spinner="Pobieranie danych z Google Sheets...")
def load_google_sheet_data(_sheet, worksheet_name):
    """
    Ładuje dane z Google Sheets.
    Cache ustawiony na 10 minut (ttl=600 sekund).
    Argument '_sheet' ma podkreślenie, aby Streamlit nie próbował go hashować.
    """
    try:
        if _sheet is None:
            return pd.DataFrame()
        
        # Pobieranie danych
        worksheet = _sheet.worksheet(worksheet_name)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        # W razie błędu zwracamy pusty DataFrame, nie cachujemy błędu
        st.error(f"Błąd pobierania danych: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)  # Cache na 5 minut (rzadko się zmienia)
def load_historical_data_from_json():
    """
    Ładuje dane historyczne z JSON z cache'owaniem.
    """
    try:
        with open('historical_results.json', 'r') as f:
            data = json.load(f)
        
        rows = []
        for user, user_data in data.items():
            for period, stats in user_data.items():
                row = {'uczestnik': user, 'miesiac_rok_str': period}
                row.update(stats)
                rows.append(row)
        
        df = pd.DataFrame(rows)
        
        if not df.empty:
            df['miesiac'] = pd.to_datetime(df['miesiac_rok_str'], format='%m.%Y')
            df['rezultat_raw'] = df['rezultat_uczestnika'].astype(str)
            df['rezultat_numeric'] = pd.to_numeric(df['rezultat_uczestnika'], errors='coerce')
            
            unique_months = sorted(df['miesiac'].unique())
            month_to_edition = {m: i+1 for i, m in enumerate(unique_months)}
            df['edycja_nr'] = df['miesiac'].map(month_to_edition)
            
        return df
    except FileNotFoundError:
        return pd.DataFrame()

def process_raw_data(df_raw, lang, expected_cols, sheet_name_for_error_msg):
    """
    Przetwarza surowe dane - NIE cachujemy bo to operacja lokalna na danych z pamięci.
    """
    current_data = {}
    max_day_reported = 0
    
    if df_raw.empty:
         # Cicha obsługa pustego DF, żeby nie straszyć użytkownika na starcie
        return {}, 0, True

    if not all(col in df_raw.columns for col in expected_cols):
        # Sprawdzamy czy nagłówki się zgadzają tylko jeśli są dane
        st.error(_t('current_header_check_error', lang))
        return {}, 0, False

    df_raw['Day'] = pd.to_numeric(df_raw['Day'], errors='coerce')
    df_raw = df_raw.dropna(subset=['Day'])
    
    if df_raw.empty:
        return {}, 0, True

    max_day_reported = int(df_raw['Day'].max())

    for _, row in df_raw.iterrows():
        participant = row['Participant']
        day = int(row['Day'])
        status = row['Status']
        timestamp = row['Timestamp']
        
        if participant not in current_data:
            current_data[participant] = {}
        
        current_data[participant][day] = {
            "status": status,
            "timestamp": timestamp,
            "notes": row.get('Notes', '')
        }
        
    return current_data, max_day_reported, True
