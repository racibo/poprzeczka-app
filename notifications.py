import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import streamlit as st
import pandas as pd
from config import EDITIONS_CONFIG
# Importujemy oficjalną funkcję obliczania rankingu, aby dane były spójne
from page_current_ranking import calculate_ranking

def send_email(recipients, subject, html_content):
    """Wysyła wiadomość e-mail korzystając z danych w st.secrets["email"]."""
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
    msg['From'] = f"Poprzeczka App <{sender_email}>"
    msg['To'] = ", ".join(recipients) if isinstance(recipients, list) else recipients
    msg['Subject'] = subject

    # Stylizacja HTML dla ładnego wyglądu w skrzynce
    styled_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; border: 1px solid #ddd; border-radius: 10px; overflow: hidden;">
            <div style="background-color: #2e7d32; color: white; padding: 20px; text-align: center;">
                <h1 style="margin: 0;">Poprzeczka</h1>
            </div>
            <div style="padding: 20px;">
                {html_content}
            </div>
            <div style="background-color: #f9f9f9; padding: 10px; text-align: center; font-size: 12px; color: #777;">
                Wiadomość wygenerowana automatycznie przez system Poprzeczka.
            </div>
        </div>
    </body>
    </html>
    """
    
    msg.attach(MIMEText(styled_html, 'html'))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"❌ Błąd SMTP: {e}")
        return False

def check_and_send_notifications(conn, data, edition_key, lang='pl'):
    """
    Główna logika sprawdzająca, czy należy wysłać maile.
    Wywoływana po każdym nowym wpisie w page_form.py.
    """
    cfg = EDITIONS_CONFIG.get(edition_key)
    if not cfg:
        return

    # 1. Pobierz listę subskrybentów z arkusza "Emails"
    try:
        subscribers = conn.read(worksheet="Emails", ttl=0)
    except:
        return # Jeśli nie ma arkusza, po prostu wychodzimy

    # 2. Oblicz ranking korzystając z oficjalnej logiki
    participants = cfg['participants']
    # Znajdujemy ostatni zaraportowany dzień
    max_day = int(data['Day'].max()) if not data.empty else 0
    
    ranking_df, _ = calculate_ranking(data, max_day, lang, participants)
    
    # 3. Sprawdź kompletność dnia (czy wszyscy aktywni wysłali raport)
    # Aktywni to ci, którzy NIE mają statusu "Out" w Twoim rankingu
    active_players = ranking_df[ranking_df['Status'] != 'Out']['Participant'].tolist()
    
    current_day_data = data[data['Day'] == max_day]
    players_who_reported = current_day_data['Participant'].unique().tolist()
    
    is_complete = all(player in players_who_reported for player in active_players)

    # --- LOGIKA A: ALERT OSTRZEGAWCZY (2 porażki z rzędu) ---
    # Szukamy osób, które właśnie mają serię 2 i nie miały wysłanego ostrzeżenia dzisiaj
    for _, row in ranking_df.iterrows():
        # Zakładamy, że calculate_ranking zwraca kolumnę 'Consecutive_Fails' (seria)
        # Jeśli Twoja funkcja nazywa to inaczej, dostosuj nazwę poniżej:
        consecutive = row.get('Consecutive_Fails', 0)
        user = row['Participant']
        
        if consecutive == 2:
            user_mail_info = subscribers[subscribers['Participant'] == user]
            if not user_mail_info.empty and user_mail_info.iloc[0]['Alert_Warning'] in [True, 'TRUE', 'YES']:
                target_email = user_mail_info.iloc[0]['Email']
                subject = "⚠️ Ostrzeżenie: To Twoja druga porażka z rzędu!"
                content = f"""
                <p>Cześć <b>{user}</b>!</p>
                <p>Twoje ostatnie dwa etapy zakończyły się statusem innym niż 'Zaliczone'.</p>
                <p style="color: red; font-weight: bold;">Pamiętaj: trzecia porażka z rzędu oznacza eliminację z rywalizacji!</p>
                <p>Trzymamy kciuki za kolejny dzień!</p>
                """
                # Tutaj można dodać mechanizm (np. w st.session_state), żeby nie wysyłać tego co odświeżenie strony
                # Ale najprościej wysłać raz przy wykryciu
                send_email(target_email, subject, content)

    # --- LOGIKA B: NEWSLETTER (Ranking po zakończeniu dnia) ---
    if is_complete:
        # Sprawdzamy w cache/session_state czy już wysłaliśmy newsletter dla tego dnia
        sent_key = f"newsletter_sent_{edition_key}_{max_day}"
        if sent_key not in st.session_state:
            
            # Generowanie tabeli HTML
            rank_rows = ""
            for i, row in ranking_df.iterrows():
                medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}."
                bg = "#fff9c4" if i <= 2 else "transparent"
                
                # Ikony porażek z rzędu
                fails_icons = "❌" * int(row.get('Consecutive_Fails', 0))
                status_text = "Eliminacja" if row.get('Status') == 'Out' else fails_icons
                
                rank_rows += f"""
                <tr style="background-color: {bg};">
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{medal}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;"><b>{row['Participant']}</b></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: center;">{row['Total_Score']}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: center;">{status_text}</td>
                </tr>"""

            rank_table = f"""
            <h3>Podsumowanie Etapu {max_day}</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr style="background-color: #2e7d32; color: white;">
                        <th style="padding: 10px;">Poz.</th>
                        <th style="padding: 10px; text-align: left;">Uczestnik</th>
                        <th style="padding: 10px;">Pkt</th>
                        <th style="padding: 10px;">Seria porażek</th>
                    </tr>
                </thead>
                <tbody>{rank_rows}</tbody>
            </table>
            <p><a href="https://poprzeczka.streamlit.app" style="color: #2e7d32; font-weight: bold;">Zobacz pełny ranking w aplikacji</a></p>
            """

            # Wysyłka do subskrybentów 'Alert_Results'
            recipients = subscribers[subscribers['Alert_Results'] in [True, 'TRUE', 'YES']]['Email'].tolist()
            if recipients:
                if send_email(recipients, f"🏁 Poprzeczka: Wyniki Etapu {max_day}", rank_table):
                    st.session_state[sent_key] = True

