import pandas as pd
import streamlit as st
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Authenticate and connect to Google Sheets
def authenticate_gsheet(sheet_name):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(credentials)
    return client.open(sheet_name)

# Initialize default data for Rankings and Match History
def initialize_data(sheet):
    players = ["Marinkovic", "Joseto", "Hernan", "Pavez", "Bozzo", "Bishara", "Hederra", "Poch", "Juande", "Hans"]
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
        match_history_df = pd.DataFrame(columns=["Date", "Winner", "Loser", "Points Exchanged"])
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

    return rankings, match_history

# Save data to Google Sheets
def save_data(sheet, rankings, match_history):
    rankings_sheet = sheet.worksheet("Rankings")
    match_history_sheet = sheet.worksheet("Match History")

    # Save Rankings
    rankings_sheet.clear()
    rankings_sheet.update([rankings.columns.values.tolist()] + rankings.values.tolist())

    # Save Match History
    match_history_sheet.clear()
    match_history_sheet.update([match_history.columns.values.tolist()] + match_history.values.tolist())

# Connect to Google Sheets
sheet_name = "Tennis Rankings and Match History"  # Replace with the name of your Google Sheet
sheet = authenticate_gsheet(sheet_name)

# Initialize data if sheets are empty
initialize_data(sheet)

# Load data from Google Sheets
rankings, match_history = load_data(sheet)

# Initialize session state with data from Google Sheets
if "rankings" not in st.session_state:
    st.session_state.rankings = rankings

if "match_history" not in st.session_state:
    st.session_state.match_history = match_history

# Function to record a match and update rankings
def record_match(winner, loser, base_points=50, upset_multiplier=1.5):
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
    }
    st.session_state.match_history = pd.concat([match_history, pd.DataFrame([new_match])], ignore_index=True)

    # Save updated data to Google Sheets
    save_data(sheet, st.session_state.rankings, st.session_state.match_history)

# Streamlit App
st.title("🎾 Ranking Shishi de Tenis")

menu = st.sidebar.selectbox("Menu", ["Ver Ranking", "Ver Historial de Partidos", "Anotar Resultado"])

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
        st.table(st.session_state.match_history)

elif menu == "Anotar Resultado":
    st.header("🏅 Anotar Resultado")
    st.write("Enter the winner and loser from the dropdown options below.")
    with st.form("match_form"):
        winner = st.selectbox("Winner", options=st.session_state.rankings["Player"].to_list())
        loser = st.selectbox("Loser", options=st.session_state.rankings["Player"].to_list())
        submit = st.form_submit_button("Record Match")
        if submit:
            if winner == loser:
                st.error("Winner and loser cannot be the same person.")
            else:
                record_match(winner, loser)
                st.success(f"Match recorded: {winner} defeated {loser}.")
                st.header("Updated Rankings")
                # Display updated rankings with correct rank numbers
                updated_rankings = st.session_state.rankings.copy()
                updated_rankings.insert(0, "Rank", range(1, len(updated_rankings) + 1))
                st.dataframe(updated_rankings.set_index("Rank"))  # Use Rank as the index to remove the unnamed index column
