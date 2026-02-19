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

    # Opakowanie treści w ładny szablon HTML
    styled_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; border: 1px solid #ddd; border-radius: 10px; overflow: hidden;">
            <div style="background-color: #2e7d32; color: white; padding: 20px; text-align: center;">
                <h1 style="margin: 0;">Poprzeczka Bot</h1>
            </div>
            <div style="padding: 20px;">
                {html_content}
            </div>
            <div style="background-color: #f9f9f9; color: #888; padding: 10px; text-align: center; font-size: 12px; border-top: 1px solid #eee;">
                Wiadomość wygenerowana automatycznie przez system Poprzeczka.
            </div>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart()
    msg['From'] = f"Poprzeczka Bot <{sender_email}>"
    msg['Subject'] = subject
    
    if isinstance(recipients, list) and len(recipients) > 1:
        msg['Bcc'] = ", ".join(recipients)
        dest_list = [sender_email]
    else:
        dest_list = recipients if isinstance(recipients, list) else [recipients]
        msg['To'] = dest_list[0]

    msg.attach(MIMEText(styled_html, 'html'))

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
    """
    cfg = EDITIONS_CONFIG.get(edition_key)
    if not cfg:
        return

    try:
        df_results = conn.read(worksheet=cfg['sheet_name'], ttl=0)
        df_emails = conn.read(worksheet="Emails", ttl=0)
    except Exception as e:
        st.warning(f"⚠️ Nie można odczytać arkusza 'Emails' lub wyników: {e}")
        return

    # 1. OSTRZEŻENIE O 3. PRÓBIE
    user_row = df_emails[df_emails['Participant'] == current_user]
    if not user_row.empty:
        user_email = user_row.iloc[0]['Email']
        user_lang = user_row.iloc[0]['Language']
        wants_warning = str(user_row.iloc[0]['Alert_Warning']).upper() in ['TRUE', 'PRAWDA', 'YES']
        
        if current_status == "Niezaliczone" and wants_warning:
            history = df_results[df_results['Participant'] == current_user].sort_values('Day')
            last_two = history.tail(2)
            
            if len(last_two) == 2 and all(last_two['Status'] == "Niezaliczone"):
                if user_lang == "PL":
                    subj = "⚠️ Ostrzeżenie: Druga porażka z rzędu!"
                    body = f"""
                    <h2 style="color: #d32f2f;">Uwaga {current_user}!</h2>
                    <p>To Twój <b>drugi niezaliczony etap z rzędu</b>.</p>
                    <p style="background-color: #fff3e0; padding: 10px; border-left: 5px solid #ff9800;">
                        Pamiętaj, że <b>trzecia porażka</b> oznacza automatyczne odpadnięcie z gry.
                    </p>
                    <p>Trzymamy kciuki za jutrzejszy trening!</p>
                    """
                else:
                    subj = "⚠️ Warning: Second failure in a row!"
                    body = f"""
                    <h2 style="color: #d32f2f;">Attention {current_user}!</h2>
                    <p>This is your <b>second failed stage in a row</b>.</p>
                    <p style="background-color: #fff3e0; padding: 10px; border-left: 5px solid #ff9800;">
                        Remember, the <b>third failure</b> results in automatic elimination from the game.
                    </p>
                    <p>We're crossing our fingers for your next workout!</p>
                    """
                send_email([user_email], subj, body)

    # 2. KOMPLET WYNIKÓW DNIA (ZBIORCZE)
    day_entries = df_results[df_results['Day'].astype(str) == str(current_day)]
    reporters_today = day_entries['Participant'].unique().tolist()
    
    def get_active_participants(df, initial_list):
        active = []
        for p in initial_list:
            p_history = df[df['Participant'] == p]
            fail_count = len(p_history[p_history['Status'] == 'Niezaliczone'])
            if fail_count < 3:
                active.append(p)
        return active

    current_active_players = get_active_participants(df_results, cfg['participants'])
    is_complete = all(player in reporters_today for player in current_active_players)

    if is_complete and len(reporters_today) > 0:
        subscribers = df_emails[df_emails['Alert_Results'].astype(str).str.upper().isin(['TRUE', 'PRAWDA', 'YES'])]
        
        if not subscribers.empty:
            # Tworzenie tabeli rankingu
            ranking = df_results[df_results['Status'] == 'Zaliczone'].groupby('Participant').size().sort_values(ascending=False)
            
            rank_rows = ""
            for i, (p, s) in enumerate(ranking.items(), 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                bg = "#f1f8e9" if i <= 3 else "transparent"
                rank_rows += f"""
                <tr style="background-color: {bg};">
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{medal}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{p}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;"><b>{s}</b></td>
                </tr>"""

            rank_table = f"""
            <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
                <thead>
                    <tr style="background-color: #eee;">
                        <th style="text-align: left; padding: 8px;">Poz.</th>
                        <th style="text-align: left; padding: 8px;">Uczestnik</th>
                        <th style="text-align: right; padding: 8px;">Pkt</th>
                    </tr>
                </thead>
                <tbody>{rank_rows}</tbody>
            </table>"""

            # Wysyłka PL
            pl_emails = subscribers[subscribers['Language'] == 'PL']['Email'].dropna().tolist()
            if pl_emails:
                subj_pl = f"🏁 Komplet wyników - Etap {current_day}"
                body_pl = f"""
                <h3>Wszyscy aktywni uczestnicy przesłali raporty!</h3>
                <p>Etap {current_day} został oficjalnie zakończony. Oto aktualna klasyfikacja:</p>
                {rank_table}
                <p style="margin-top: 20px;">Powodzenia w kolejnym dniu!</p>
                """
                send_email(pl_emails, subj_pl, body_pl)

            # Wysyłka EN
            en_emails = subscribers[subscribers['Language'] == 'EN']['Email'].dropna().tolist()
            if en_emails:
                subj_en = f"🏁 Day {current_day} Results - All in!"
                body_en = f"""
                <h3>All active participants have submitted their reports!</h3>
                <p>Stage {current_day} is now officially complete. Current standings:</p>
                {rank_table}
                <p style="margin-top: 20px;">Good luck tomorrow!</p>
                """
                send_email(en_emails, subj_en, body_en)

