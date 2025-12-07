import pandas as pd
import streamlit as st
import json
from datetime import datetime
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

# W pliku data_loader.py
@st.cache_data(ttl=300)  # Cache na 5 minut (rzadko się zmienia)
def load_historical_data_from_json():
    """
    Ładuje dane historyczne z JSON z cache'owaniem.
    """
    try:
        with open('historical_results.json', 'r', encoding='utf-8') as f:
            data = json.load(f)

        df = pd.DataFrame()
        records = []
        
        # Przetwarzanie danych
        for participant, editions in data.items():
            for edition_str, values in editions.items():
                try:
                    month, year = map(int, edition_str.split('.'))
                    # Używamy zaimportowanej klasy datetime
                    date_obj = datetime(year, month, 1)
                except ValueError:
                    # Pomijamy błędne daty
                    continue
                
                # Dodajemy rekord
                record = {
                    'uczestnik': participant,
                    'miesiac_rok_str': edition_str,
                    'miesiac': date_obj,
                    'rok': year,
                    # Zmienne wyniki
                    'miejsce': values.get('miejsce'),
                    'rezultat_uczestnika': values.get('rezultat_uczestnika'),
                    'status': values.get('status', 'Brak')
                }
                records.append(record)

        if records:
            df = pd.DataFrame(records)

            # Poprawka na ostrzeżenie o mixed type
            df.columns = df.columns.astype(str)
            
            # Konwersja kolumn
            df['miesiac'] = pd.to_datetime(df['miesiac'])
            df['miejsce'] = pd.to_numeric(df['miejsce'], errors='coerce').astype('Int64')
            df['rezultat_numeric'] = pd.to_numeric(df['rezultat_uczestnika'], errors='coerce')
            
            # Wstawienie numeru edycji
            all_months = df['miesiac'].sort_values().unique()
            month_to_edition = {month: i + 1 for i, month in enumerate(all_months)}
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
