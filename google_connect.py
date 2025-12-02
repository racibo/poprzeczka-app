import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import requests

# Definicja zakresów tylko dla Arkuszy (Dysk nie jest już potrzebny)
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

@st.cache_resource
def get_credentials():
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=SCOPES
        )
        return creds
    except Exception as e:
        st.error(f"Błąd tworzenia poświadczeń: {e}")
        return None

@st.cache_resource
def connect_to_google_sheets():
    try:
        creds = get_credentials()
        if not creds: return None
        client = gspread.authorize(creds)
        sheet = client.open_by_key(st.secrets["public_gsheets_url"]) 
        return sheet
    except Exception as e:
        st.error(f"Błąd połączenia z Google Sheets: {e}")
        return None

def upload_file_to_hosting(uploaded_file):
    """
    Wysyła plik do darmowego hostingu (Catbox.moe) i zwraca link.
    Nie wymaga kluczy API ani konta Google Drive.
    """
    try:
        # Przygotowanie pliku do wysyłki
        files = {
            'reqtype': (None, 'fileupload'),
            'fileToUpload': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)
        }
        
        # Wysyłanie zapytania do API
        response = requests.post("https://catbox.moe/user/api.php", files=files)
        
        if response.status_code == 200:
            # Sukces - API zwraca bezpośredni link jako tekst
            return response.text.strip()
        else:
            st.error(f"Hosting zwrócił błąd: {response.status_code}")
            return None
            
    except Exception as e:
        st.error(f"Błąd przesyłania pliku: {e}")
        return None

def append_to_sheet_dual(sheet, data_old, data_new):
    """Zapisuje dane do jednej lub dwóch edycji naraz."""
    success = True
    
    if data_old:
        try:
            ws_old = sheet.worksheet(data_old['sheet_name'])
            ws_old.append_row(data_old['row'])
            sheet.worksheet("LogWpisow").append_row(data_old['log_row'])
        except Exception as e:
            st.error(f"Błąd zapisu (Stara Edycja): {e}")
            success = False

    if data_new:
        try:
            ws_new = sheet.worksheet(data_new['sheet_name'])
            ws_new.append_row(data_new['row'])
        except Exception as e:
            st.error(f"Błąd zapisu (Nowa Edycja): {e}. Czy arkusz '{data_new['sheet_name']}' istnieje?")
            success = False
            
    return success
