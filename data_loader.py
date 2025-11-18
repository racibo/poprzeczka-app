import streamlit as st
import pandas as pd
import gspread
import json
import os
from datetime import datetime
from translations import _t
from config import CURRENT_PARTICIPANTS, FILE_HISTORICAL

@st.cache_data(ttl=60) 
def load_google_sheet_data(_sheet, worksheet_name): 
    """Pobiera wszystkie dane z danej zakładki jako DataFrame."""
    try:
        worksheet = _sheet.worksheet(worksheet_name) 
        all_data = worksheet.get_all_values()
        
        if len(all_data) <= 1:
             return pd.DataFrame() # Tylko nagłówki lub pusty

        headers = all_data[0]
        data = all_data[1:]
        
        df = pd.DataFrame(data, columns=headers)
        if 'Day' in df.columns:
            df['Day'] = pd.to_numeric(df['Day'], errors='coerce')
        return df
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Błąd: Nie znaleziono zakładki o nazwie '{worksheet_name}' w Arkuszu Google.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Nie można wczytać danych z zakładki '{worksheet_name}': {e}")
        return pd.DataFrame()

def process_raw_data(df_raw, lang, expected_cols, worksheet_name):
    """
    Przetwarza surowe dane (append-only) z Google Sheets w strukturę "najnowszy wpis wygrywa".
    Zwraca słownik: {participant: {day: status}} oraz max_day
    """
    if df_raw.empty:
        return {}, 0, True 
        
    if not all(col in df_raw.columns for col in expected_cols):
        st.error(_t('current_header_check_error', lang))
        st.json({
            _t('current_header_check_details', lang, worksheet_name): "",
            _t('current_header_check_expected', lang): expected_cols,
            _t('current_header_check_found', lang): df_raw.columns.tolist()
        })
        return {}, 0, False 
        
    if 'Day' not in df_raw.columns or 'Timestamp' not in df_raw.columns:
        return {}, 0, False 
        
    df_raw['Day'] = pd.to_numeric(df_raw['Day'], errors='coerce')
    df_raw = df_raw.dropna(subset=['Day'])
    if df_raw.empty:
        return {}, 0, True
        
    df_raw = df_raw.sort_values(by="Timestamp")
    
    processed_data = {}
    for _, row in df_raw.iterrows():
        participant = row['Participant']
        if participant not in CURRENT_PARTICIPANTS:
            continue
            
        day = int(row['Day'])
        
        if participant not in processed_data:
            processed_data[participant] = {}
            
        processed_data[participant][day] = {
            "status": row['Status'],
            "notes": row['Notes']
        }
    
    max_day = 0
    for p_data in processed_data.values():
        if p_data:
            max_day = max(max_day, max(p_data.keys()))

    return processed_data, max_day, True

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