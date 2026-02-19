import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import streamlit as st
import pandas as pd
from config import EDITIONS_CONFIG

def send_email(recipients, subject, html_content):
    """
    Wysyła wiadomość e-mail korzystając z danych w st.secrets["email"].
    Obsługuje wielu odbiorców naraz przy użyciu pola BCC.
    """
    if not recipients:
        return False
        
    try:
        conf = st.secrets["email"]
        sender_email = conf["sender"]
        sender_password = conf["password"]
        smtp_server = conf["smtp_server"]
        smtp_port = conf["smtp_port"]
    except Exception as e:
        st.error(f"❌ Błąd konfiguracji secrets [email]: {e}")
        return False

    msg = MIMEMultipart()
    msg['From'] = f"Poprzeczka Bot <{sender_email}>"
    msg['Subject'] = subject
    
    # Obsługa wielu odbiorców (BCC - ukryta kopia), aby chronić prywatność
    if isinstance(recipients, list) and len(recipients) > 1:
        msg['Bcc'] = ", ".join(recipients)
        dest_list = [sender_email] # Technicznie wysyłamy do siebie, reszta widzi tylko ukrytą kopię
    else:
        dest_list = recipients if isinstance(recipients, list) else [recipients]
        msg['To'] = dest_list[0]

    msg.attach(MIMEText(html_content, 'html'))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.set_debuglevel(0)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, dest_list, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"❌ Błąd serwera poczty (SMTP): {e}")
        return False

def check_and_send_notifications(conn, edition_key, current_user, current_day, current_status):
    """
    Główna funkcja sprawdzająca warunki wysyłki po dodaniu nowego wpisu.
    Uwzględnia tylko graczy, którzy nie zostali jeszcze wyeliminowani.
    """
    cfg = EDITIONS_CONFIG.get(edition_key)
    if not cfg:
        return

    try:
        # Odczyt danych z arkuszy (używamy conn.read dla Streamlit GSheets Connection)
        # ttl=0 jest kluczowe, aby widzieć właśnie dodany wiersz
        df_results = conn.read(worksheet=cfg['sheet_name'], ttl=0)
        df_emails = conn.read(worksheet="Emails", ttl=0)
    except Exception as e:
        st.warning(f"⚠️ Nie można odczytać arkusza 'Emails' lub wyników: {e}")
        return

    # 1. OSTRZEŻENIE O 3. PRÓBIE (INDYWIDUALNE)
    user_row = df_emails[df_emails['Participant'] == current_user]
    if not user_row.empty:
        user_email = user_row.iloc[0]['Email']
        user_lang = user_row.iloc[0]['Language']
        wants_warning = str(user_row.iloc[0]['Alert_Warning']).upper() in ['TRUE', 'PRAWDA', 'YES']
        
        if current_status == "Niezaliczone" and wants_warning:
            # Pobieramy historię tego konkretnego użytkownika
            history = df_results[df_results['Participant'] == current_user].sort_values('Day')
            last_two = history.tail(2)
            
            # Jeśli dwa ostatnie statusy to porażki
            if len(last_two) == 2 and all(last_two['Status'] == "Niezaliczone"):
                if user_lang == "PL":
                    subj = "⚠️ Ostrzeżenie: Druga porażka z rzędu!"
                    body = f"Cześć <b>{current_user}</b>!<br><br>To Twój drugi niezaliczony etap z rzędu. Pamiętaj, że trzeci oznacza automatyczne odpadnięcie z gry!"
                else:
                    subj = "⚠️ Warning: Second failure in a row!"
                    body = f"Hi <b>{current_user}</b>!<br><br>This is your second failed stage in a row. Remember, the third one means automatic elimination from the game!"
                
                send_email([user_email], subj, body)

    # 2. KOMPLET WYNIKÓW DNIA (ZBIORCZE)
    
    # Sprawdzamy, kto już wysłał raport dzisiaj
    day_entries = df_results[df_results['Day'].astype(str) == str(current_day)]
    reporters_today = day_entries['Participant'].unique().tolist()
    
    # Funkcja wyliczająca aktywnych graczy (tych, którzy mają mniej niż 3 porażki)
    def get_active_participants(df, initial_list):
        active = []
        for p in initial_list:
            p_history = df[df['Participant'] == p]
            fail_count = len(p_history[p_history['Status'] == 'Niezaliczone'])
            if fail_count < 3:
                active.append(p)
        return active

    current_active_players = get_active_participants(df_results, cfg['participants'])
    
    # Sprawdzamy czy wszyscy aktywni gracze przesłali już raport za ten dzień
    is_complete = all(player in reporters_today for player in current_active_players)

    # Jeśli jest komplet i są jacykolwiek raportujący
    if is_complete and len(reporters_today) > 0:
        # Filtrujemy tylko tych, którzy chcą dostawać raporty zbiorcze
        subscribers = df_emails[df_emails['Alert_Results'].astype(str).str.upper().isin(['TRUE', 'PRAWDA', 'YES'])]
        
        if not subscribers.empty:
            # Tworzymy uproszczony ranking na podstawie liczby zaliczonych dni
            ranking = df_results[df_results['Status'] == 'Zaliczone'].groupby('Participant').size().sort_values(ascending=False)
            rank_html = "<ul>"
            for p, s in ranking.items():
                rank_html += f"<li>{p}: {s} pkt</li>"
            rank_html += "</ul>"

            # --- WYSYŁKA PL ---
            pl_emails = subscribers[subscribers['Language'] == 'PL']['Email'].dropna().tolist()
            if pl_emails:
                subj_pl = f"🏁 Wyniki dnia {current_day} - Komplet!"
                body_pl = (
                    f"Wszyscy aktywni uczestnicy ({len(current_active_players)} osób) przesłali już swoje raporty za dzień {current_day}.<br><br>"
                    f"<b>Aktualna punktacja:</b><br>{rank_html}"
                )
                send_email(pl_emails, subj_pl, body_pl)

            # --- WYSYŁKA EN ---
            en_emails = subscribers[subscribers['Language'] == 'EN']['Email'].dropna().tolist()
            if en_emails:
                subj_en = f"🏁 Results for day {current_day} - All in!"
                body_en = (
                    f"All active participants ({len(current_active_players)} people) have submitted their reports for day {current_day}.<br><br>"
                    f"<b>Current standings:</b><br>{rank_html}"
                )
                send_email(en_emails, subj_en, body_en)
