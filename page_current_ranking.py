import pandas as pd
import streamlit as st
import json
from translations import _t

def load_google_sheet_data(sheet, worksheet_name):
    """
    Ładuje dane z Google Sheets.
    Cache'owanie zostało wyłączone - szukamy zawsze świeżych danych.
    """
    try:
        if sheet is None:
            return pd.DataFrame()
        
        worksheet = sheet.worksheet(worksheet_name)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        # Nie cachujemy błędy - zawsze zwracamy pusty DataFrame
        return pd.DataFrame()

@st.cache_data(ttl=300)  # Cache na 5 minut (rzadko się zmienia)
def load_historical_data_from_json():
    """
    Ładuje dane historyczne z JSON z cache'owaniem.
    Cache'uje na 5 minut bo zmienia się rzadko.
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
            # POPRAWKA: Upewniamy się, że 'rezultat_raw' istnieje
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
    Przetwarza surowe dane - NIE cachujemy bo muszą być na bieżąco.
    """
    current_data = {}
    max_day_reported = 0
    
    if not all(col in df_raw.columns for col in expected_cols):
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
