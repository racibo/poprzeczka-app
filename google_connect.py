import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
from config import GOOGLE_SHEET_NAME
from translations import _t

# === Połączenie z Google ===
@st.cache_resource(ttl=600)
def get_google_credentials():
    """Pobiera i autoryzuje poświadczenia Google."""
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
        return creds
    except Exception as e:
        if "No secrets found" in str(e):
             st.error(f"Błąd połączenia: Brak pliku secrets.toml. Uruchamiasz lokalnie? Upewnij się, że plik .streamlit/secrets.toml jest poprawnie skonfigurowany.")
        else:
            st.error(f"Błąd połączenia z Google: {e}. Sprawdź 'Secrets' w Streamlit Cloud lub lokalny plik secrets.toml.")
        return None

@st.cache_resource(ttl=600) 
def connect_to_google_sheets():
    """Łączy się z Google Sheets."""
    creds = get_google_credentials()
    if creds:
        try:
            client = gspread.authorize(creds)
            sheet = client.open(GOOGLE_SHEET_NAME)
            return sheet
        except Exception as e:
            st.error(f"Błąd otwierania Arkusza Google: {e}")
    return None

@st.cache_resource(ttl=600)
def connect_to_google_drive():
    """Łączy się z Google Drive API."""
    creds = get_google_credentials()
    if creds:
        try:
            service = build('drive', 'v3', credentials=creds)
            return service
        except Exception as e:
            st.error(f"Błąd łączenia z Google Drive API: {e}")
    return None

def upload_file_to_drive(service, file_obj, folder_id, lang):
    """Przesyła plik (file_obj) do folderu Google Drive (folder_id) i zwraca link."""
    try:
        file_metadata = {
            'name': file_obj.name,
            'parents': [folder_id]
        }
        file_buffer = io.BytesIO(file_obj.getvalue())
        media = MediaIoBaseUpload(file_buffer, mimetype=file_obj.type, resumable=True)
        
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink' 
        ).execute()
        
        file_id = file.get('id')
        service.permissions().create(
            fileId=file_id,
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()
        
        return file.get('webViewLink') 
    except Exception as e:
        st.error(_t('form_error_uploading_file', lang, file_obj.name, e))
        return None