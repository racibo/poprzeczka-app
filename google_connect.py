import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# Funkcja cache'owana do łączenia z arkuszem
@st.cache_resource
def connect_to_google_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(st.secrets["public_gsheets_url"]) 
        return sheet
    except Exception as e:
        st.error(f"Błąd połączenia z Google Sheets: {e}")
        return None

@st.cache_resource
def connect_to_google_drive():
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            st.secrets["gcp_service_account"], 
            ["https://www.googleapis.com/auth/drive"]
        )
        service = build('drive', 'v3', credentials=creds)
        return service
    except Exception as e:
        st.error(f"Błąd połączenia z Google Drive: {e}")
        return None

def upload_file_to_drive(service, uploaded_file, folder_id, lang):
    try:
        file_metadata = {'name': uploaded_file.name, 'parents': [folder_id]}
        media = MediaIoBaseUpload(uploaded_file, mimetype=uploaded_file.type)
        file = service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
        return file.get('webViewLink')
    except Exception as e:
        st.error(f"Błąd przesyłania: {e}")
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
            # Opcjonalnie: Logujemy też wpis grudniowy
            # sheet.worksheet("LogWpisow").append_row(data_new['log_row']) 
        except Exception as e:
            st.error(f"Błąd zapisu (Nowa Edycja): {e}. Czy arkusz '{data_new['sheet_name']}' istnieje?")
            success = False
            
    return success
