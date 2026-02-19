import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import streamlit as st
import pandas as pd
from config import EDITIONS_CONFIG

# --- FUNKCJA WYSYŁAJĄCA EMAIL ---
def send_email(recipients, subject, html_content):
    if not recipients:
        return
        
    sender_email = st.secrets["email"]["sender"]
    sender_password = st.secrets["email"]["password"]
    smtp_server = st.secrets["email"]["smtp_server"]
    smtp_port = st.secrets["email"]["smtp_port"]

    msg = MIMEMultipart()
    msg['From'] = f"Poprzeczka Bot <{sender_email}>"
    msg['Subject'] = subject
    # Ukrywamy odbiorców (BCC)
    msg['Bcc'] = ", ".join(recipients) 
    
    msg.attach(MIMEText(html_content, 'html'))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipients, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Błąd wysyłania emaila: {e}")
        return False

# --- GŁÓWNA LOGIKA POWIADOMIEŃ ---
def check_and_send_notifications(conn, edition_key, current_user, current_day, current_status):
    """
    Ta funkcja jest wywoływana PO zapisaniu wyniku do bazy.
    Sprawdza dwa warunki:
    1. Czy użytkownik ma 2 niezaliczone pod rząd -> Alert Warning
    2. Czy wpłynął komplet wyników -> Alert Results
    """
    
    # 1. Pobieramy konfigurację i dane
    edition_config = EDITIONS_CONFIG[edition_key]
    sheet_name = edition_config['sheet_name']
    participants_list = edition_config['participants']
    
    # Pobieramy aktualne wyniki i bazę maili
    # Używamy ttl=0, żeby mieć najświeższe dane
    df_results = conn.read(worksheet=sheet_name, ttl=0) 
    try:
        df_emails = conn.read(worksheet="Emails", ttl=0)
    except:
        return # Brak zakładki Emails

    # Jeśli użytkownik nie ma maila w bazie, to nic nie robimy dla niego indywidualnie
    user_prefs = df_emails[df_emails['Participant'] == current_user]
    user_email = user_prefs['Email'].iloc[0] if not user_prefs.empty else None
    user_lang = user_prefs['Language'].iloc[0] if not user_prefs.empty else "PL"
    wants_warning = user_prefs['Alert_Warning'].iloc[0] if not user_prefs.empty else False

    # === SCENARIUSZ 1: OSTRZEŻENIE O 3. PRÓBIE ===
    if current_status == "Niezaliczone" and user_email and wants_warning:
        # Sprawdzamy historię tego użytkownika
        user_history = df_results[df_results['Participant'] == current_user].sort_values('Day')
        # Bierzemy ostatnie 2 wpisy
        last_two = user_history.tail(2)
        
        # Jeśli są dokładnie 2 wpisy i oba są "Niezaliczone"
        if len(last_two) == 2 and all(last_two['Status'] == "Niezaliczone"):
            send_warning_email(user_email, user_lang)

    # === SCENARIUSZ 2: KOMPLET WYNIKÓW ===
    # Sprawdzamy ile osób już zaraportowało ten dzień
    results_today = df_results[df_results['Day'] == current_day]
    unique_reporters = results_today['Participant'].nunique()
    total_participants = len(participants_list)

    if unique_reporters >= total_participants:
        # Mamy komplet! Wysyłamy do wszystkich subskrybentów
        send_results_email(df_emails, df_results, current_day, edition_key)


def send_warning_email(email, lang):
    if lang == "PL":
        subject = "⚠️ Uwaga! Przed Tobą trzecia próba"
        body = """
        <h3>Cześć!</h3>
        <p>Właśnie zanotowałeś drugi niezaliczony etap z rzędu.</p>
        <p style="color: red; font-weight: bold;">Pamiętaj: trzecia nieudana próba oznacza odpadnięcie z rywalizacji.</p>
        <p>Powodzenia jutro!</p>
        """
    else:
        subject = "⚠️ Warning! 3rd attempt ahead"
        body = """
        <h3>Hi!</h3>
        <p>You have just recorded your second failed stage in a row.</p>
        <p style="color: red; font-weight: bold;">Remember: a third failed attempt means elimination from the competition.</p>
        <p>Good luck tomorrow!</p>
        """
    send_email([email], subject, body)


def send_results_email(df_emails, df_results, day, edition):
    # Filtrujemy tylko tych, którzy chcą wyniki
    subscribers = df_emails[df_emails['Alert_Results'] == True] # lub "TRUE" zależnie od formatu w GSheets
    
    if subscribers.empty:
        return

    # Obliczamy ranking
    ranking = df_results[df_results['Status'] == 'Zaliczone'].groupby('Participant').size().sort_values(ascending=False)
    
    # Dzielimy odbiorców na języki
    pl_emails = subscribers[subscribers['Language'] == 'PL']['Email'].tolist()
    en_emails = subscribers[subscribers['Language'] == 'EN']['Email'].tolist()

    # Generujemy tabelę HTML
    table_html = "<ol>"
    for user, score in ranking.items():
        table_html += f"<li><b>{user}</b>: {score} pkt</li>"
    table_html += "</ol>"

    # Wysyłka PL
    if pl_emails:
        subj_pl = f"🏁 Komplet wyników: Etap {day}"
        body_pl = f"""
        <h2>Podsumowanie dnia {day}</h2>
        <p>Wszyscy uczestnicy przesłali swoje wyniki.</p>
        <h3>Aktualna klasyfikacja:</h3>
        {table_html}
        <p><a href="https://poprzeczka.streamlit.app">Zobacz w aplikacji</a></p>
        """
        send_email(pl_emails, subj_pl, body_pl)

    # Wysyłka EN
    if en_emails:
        subj_en = f"🏁 Full Results: Stage {day}"
        body_en = f"""
        <h2>Day {day} Summary</h2>
        <p>All participants have submitted their results.</p>
        <h3>Current Standing:</h3>
        {table_html}
        <p><a href="https://poprzeczka.streamlit.app">Open App</a></p>
        """
        send_email(en_emails, subj_en, body_en)