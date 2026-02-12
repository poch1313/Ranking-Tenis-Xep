import pandas as pd
import streamlit as st
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart





# Authenticate and connect to Google Sheets
def authenticate_gsheet(sheet_name):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(credentials)
    return client.open(sheet_name)

# Initialize default data for Rankings and Match History
def initialize_data(sheet):
    players = ["Marinkovic", "Joseto", "Hernan", "Pavez", "Bozzo", "Hederra", "Poch", "Gonzalo Bezanilla"]
    points = [1000 for _ in players]

    # Initialize Rankings
    rankings_sheet = sheet.worksheet("Rankings")
    if len(rankings_sheet.get_all_records()) == 0:
        rankings_df = pd.DataFrame({
            "Player": players,
            "Points": points,
            "Matches Played": [0 for _ in players],
            "Wins": [0 for _ in players],
            "Losses": [0 for _ in players],
        })
        rankings_sheet.update([rankings_df.columns.values.tolist()] + rankings_df.values.tolist())

    # Initialize Match History
    match_history_sheet = sheet.worksheet("Match History")
    if len(match_history_sheet.get_all_records()) == 0:
        match_history_df = pd.DataFrame(columns=["Date","Winner","Loser","Points Exchanged","W_Set1","W_Set2","W_Set3","W_Set4","W_Set5",    "L_Set1","L_Set2","L_Set3","L_Set4","L_Set5"])
        match_history_sheet.update([match_history_df.columns.values.tolist()])

# Load data from Google Sheets
def load_data(sheet):
    rankings_sheet = sheet.worksheet("Rankings")
    match_history_sheet = sheet.worksheet("Match History")

    # Load Rankings
    rankings_data = rankings_sheet.get_all_records()
    rankings = pd.DataFrame(rankings_data)

    # Load Match History
    match_history_data = match_history_sheet.get_all_records()
    match_history = pd.DataFrame(match_history_data)

    #Load Invitations
    invitations_sheet = sheet.worksheet("Invitations")
    invitations_data = invitations_sheet.get_all_records()
    invitations = pd.DataFrame(invitations_data)

    return rankings, match_history, invitations

# Save data to Google Sheets
def save_data(sheet, rankings, match_history, invitations):

    rankings_sheet = sheet.worksheet("Rankings")
    match_history_sheet = sheet.worksheet("Match History")
    invitations_sheet = sheet.worksheet("Invitations")

    def clean_df(df):
        # Replace NaN with empty string
        df = df.fillna("")
        # Convert everything to native Python types
        return df.astype(object)

    # Save Rankings
    rankings_sheet.clear()
    clean_rankings = clean_df(rankings)
    rankings_sheet.update(
        [clean_rankings.columns.values.tolist()] +
        clean_rankings.values.tolist()
    )

    # Save Match History
    match_history_sheet.clear()
    clean_history = clean_df(match_history)
    match_history_sheet.update(
        [clean_history.columns.values.tolist()] +
        clean_history.values.tolist()
    )

    # Save Invitations
    invitations_sheet.clear()
    clean_invitations = clean_df(invitations)
    invitations_sheet.update(
        [clean_invitations.columns.values.tolist()] +
        clean_invitations.values.tolist()
    )

def format_score(row):
    score_parts = []

    for i in range(1, 6):
        winner_col = f"W_Set{i}"
        loser_col = f"L_Set{i}"

        if winner_col in row and loser_col in row:
            w = row[winner_col]
            l = row[loser_col]

            # Only include sets that were actually played
            if (
                pd.notna(w) and pd.notna(l) and
                w != "" and l != "" and
                (int(w) > 0 or int(l) > 0)
            ):
                score_parts.append(f"{int(w)}-{int(l)}")

    return " ".join(score_parts)

# Connect to Google Sheets
sheet_name = "Tennis Rankings and Match History Xep"
sheet = authenticate_gsheet(sheet_name)

# Initialize data if sheets are empty
initialize_data(sheet)

# Load data once
rankings, match_history, invitations = load_data(sheet)

# Initialize session state independently
if "rankings" not in st.session_state:
    st.session_state.rankings = rankings

if "match_history" not in st.session_state:
    st.session_state.match_history = match_history

if "invitations" not in st.session_state:
    st.session_state.invitations = invitations
   

players_emails = {
    "Marinkovic": "nimarinkovic@uc.cl1",
    "Joseto": "jtvergara1@uc.cl1",
    "Hernan": "hfyanez@uc.cl1",
    "Pavez": "Srpavez@uc.cl1",
    "Bozzo": "aabozzo@uc.cl1",
    "Hederra": "nahederra@uc.cl1",
    "Poch": "poch_javier@hotmail.com",
    "Gonzalo Bezanilla": "gonzalo.bezanilla@xepelin.com1",
}

# Function to record a match and update rankings
def record_match(winner, loser, winner_sets, loser_sets, base_points=50, upset_multiplier=1.5):
    rankings = st.session_state.rankings
    match_history = st.session_state.match_history

    # Get winner and loser points
    winner_points = rankings.loc[rankings['Player'] == winner, 'Points'].values[0]
    loser_points = rankings.loc[rankings['Player'] == loser, 'Points'].values[0]

    # Calculate points exchanged
    points_exchanged = base_points + (0.05 * loser_points)
    if winner_points < loser_points:
        points_exchanged *= upset_multiplier

    # Update rankings
    rankings.loc[rankings['Player'] == winner, 'Points'] += points_exchanged
    rankings.loc[rankings['Player'] == loser, 'Points'] -= points_exchanged
    rankings['Points'] = rankings['Points'].clip(lower=0)
    rankings.sort_values(by="Points", ascending=False, inplace=True, ignore_index=True)

    # Update matches played, wins, and losses
    rankings.loc[rankings['Player'] == winner, 'Matches Played'] += 1
    rankings.loc[rankings['Player'] == loser, 'Matches Played'] += 1
    rankings.loc[rankings['Player'] == winner, 'Wins'] += 1
    rankings.loc[rankings['Player'] == loser, 'Losses'] += 1

    # Add match to history
    new_match = {
    "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "Winner": winner,
    "Loser": loser,
    "Points Exchanged": round(points_exchanged, 2),
        "W_Set1": winner_sets[0],"W_Set2": winner_sets[1],"W_Set3": winner_sets[2],"W_Set4": winner_sets[3],"W_Set5": winner_sets[4],
        "L_Set1": loser_sets[0],"L_Set2": loser_sets[1],"L_Set3": loser_sets[2],"L_Set4": loser_sets[3],"L_Set5": loser_sets[4],}
    st.session_state.match_history = pd.concat([match_history, pd.DataFrame([new_match])], ignore_index=True)

    # Save updated data to Google Sheets
    save_data(sheet,st.session_state.rankings,st.session_state.match_history,st.session_state.invitations)


def send_invitation_email(match_date, match_time, location, created_by):
    sender = st.secrets["email"]["sender"]
    password = st.secrets["email"]["password"]

    recipient_list = list(players_emails.values())

    subject = "🎾 Open Tennis Match Invitation"

    body = f"""
🎾 OPEN MATCH INVITATION

{created_by} is looking for a match.

📅 Date: {match_date}
⏰ Time: {match_time}
📍 Location: {location}

Open the Ranking App to accept this invitation.

https://ranking-tenis-xep.streamlit.app/

First come, first served.
"""

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = sender
    msg["Subject"] = subject
    msg["Bcc"] = ", ".join(recipient_list)

    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)


def create_invitation(created_by, match_date, match_time, location):

    invitations = st.session_state.invitations

    new_id = 1 if invitations.empty else invitations["ID"].max() + 1

    new_invite = {
        "ID": new_id,
        "Created By": created_by,
        "Created At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Match Date": str(match_date),
        "Match Time": match_time,
        "Location": location,
        "Status": "Open",
        "Claimed By": ""
    }

    st.session_state.invitations = pd.concat(
        [invitations, pd.DataFrame([new_invite])],
        ignore_index=True
    )

    save_data(
        sheet,
        st.session_state.rankings,
        st.session_state.match_history,
        st.session_state.invitations
    )



def send_invitation_claimed_email(invite_row, claimer):

    sender = st.secrets["email"]["sender"]
    password = st.secrets["email"]["password"]

    recipient_list = list(players_emails.values())

    subject = "🎾 Match Confirmed – Invitation Closed"

    body = f"""
🎾 MATCH CONFIRMED

The open invitation has been accepted.

👤 {invite_row['Created By']} will play against {claimer}

📅 Date: {invite_row['Match Date']}
⏰ Time: {invite_row['Match Time']}
📍 Location: {invite_row['Location']}

The invitation is now closed.
"""

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = sender
    msg["Subject"] = subject
    msg["Bcc"] = ", ".join(recipient_list)

    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)


# Streamlit App
st.title("🎾 Ranking Shishi de Tenis")

menu = st.sidebar.selectbox("Menu", ["Ver Ranking", "Ver Historial de Partidos", "Anotar Resultado","Invitación Abierta"])

if menu == "Ver Ranking":
    st.header("📊 Ranking Actual")
    # Add a rank column based on the updated ranking order
    rankings = st.session_state.rankings.copy()
    rankings.insert(0, "Rank", range(1, len(rankings) + 1))
    st.dataframe(rankings.set_index("Rank"))  # Use Rank as the index to remove the unnamed index column

elif menu == "Ver Historial de Partidos":
    st.header("📜 Historial de Partidos")

    if st.session_state.match_history.empty:
        st.write("No matches have been recorded yet.")

    else:
        display_history = st.session_state.match_history.copy()

        # Create clean tennis-style score column
        display_history["Score"] = display_history.apply(format_score, axis=1)

        # Columns we want to display
        columns_to_show = [
            "Date",
            "Winner",
            "Loser",
            "Score",
            "Points Exchanged"
        ]

        # Keep only columns that exist (prevents errors on older matches)
        columns_to_show = [
            col for col in columns_to_show
            if col in display_history.columns
        ]

        st.table(display_history[columns_to_show])

elif menu == "Anotar Resultado":
    st.header("🏅 Anotar Resultado")
    st.write("Enter the winner and loser from the dropdown options below.")

    with st.form("match_form"):

        winner = st.selectbox(
            "Winner",
            options=st.session_state.rankings["Player"].to_list()
        )

        loser = st.selectbox(
            "Loser",
            options=st.session_state.rankings["Player"].to_list()
        )

        # -------------------------
        # NEW: SET SCORE INPUT
        # -------------------------
        st.subheader("Resultado por Sets (máx 5)")

        cols = st.columns(5)

        winner_sets = []
        loser_sets = []

        for i in range(5):
            with cols[i]:
                st.markdown(f"**Set {i+1}**")

                w_games = st.number_input(
                    "W",
                    min_value=0,
                    max_value=7,
                    step=1,
                    key=f"w_set_{i}"
                )

                l_games = st.number_input(
                    "L",
                    min_value=0,
                    max_value=7,
                    step=1,
                    key=f"l_set_{i}"
                )

                winner_sets.append(w_games)
                loser_sets.append(l_games)

        # -------------------------

        submit = st.form_submit_button("Record Match")

        if submit:
            if winner == loser:
                st.error("Winner and loser cannot be the same person.")
            else:
                record_match(winner, loser, winner_sets, loser_sets)

                st.success(f"Match recorded: {winner} defeated {loser}.")

                st.header("Updated Rankings")

                updated_rankings = st.session_state.rankings.copy()
                updated_rankings.insert(0, "Rank", range(1, len(updated_rankings) + 1))

                st.dataframe(updated_rankings.set_index("Rank"))

elif menu == "Invitación Abierta":
    st.header("📣 Crear Invitación Abierta")

    # ---- CREATE INVITATION FORM ----
    with st.form("invitation_form"):
        created_by = st.selectbox("Soy:", list(players_emails.keys()))
        match_date = st.date_input("Fecha")
        match_time = st.text_input("Hora", placeholder="Ejemplo: 19:30").strip()
        location = st.text_input("Lugar")
        submit = st.form_submit_button("Enviar Invitación")

        if submit:
            try:
                create_invitation(created_by, match_date, match_time, location)
                send_invitation_email(match_date, match_time, location, created_by)
                st.success("Invitación enviada y guardada correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    # ---- SHOW OPEN INVITATIONS ----
    st.subheader("📬 Invitaciones Abiertas")

    open_invites = st.session_state.invitations[
        st.session_state.invitations["Status"] == "Open"
    ]

    if open_invites.empty:
        st.info("No hay invitaciones abiertas.")
    else:
        for index, row in open_invites.iterrows():

            st.markdown(f"""
            ### 🎾 Invitación #{row['ID']}
            - **Creado por:** {row['Created By']}
            - **Fecha:** {row['Match Date']}
            - **Hora:** {row['Match Time']}
            - **Lugar:** {row['Location']}
            """)

            claimer = st.selectbox(
                "Quién acepta esta invitación?",
                list(players_emails.keys()),
                key=f"claimer_{row['ID']}"
            )

            if st.button("Aceptar Invitación", key=f"accept_{row['ID']}"):

                # 1️⃣ Update status
                st.session_state.invitations.loc[index, "Status"] = "Claimed"
                st.session_state.invitations.loc[index, "Claimed By"] = claimer

                # 2️⃣ Save to Google Sheets
                save_data(
                    sheet,
                    st.session_state.rankings,
                    st.session_state.match_history,
                    st.session_state.invitations
                )

                # 3️⃣ Send confirmation email (NEW)
                send_invitation_claimed_email(row, claimer)

                # 4️⃣ Feedback + refresh
                st.success(f"{claimer} aceptó la invitación.")
                st.rerun()
            
