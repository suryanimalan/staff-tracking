import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from datetime import datetime
import os

# Try to get real GPS location
try:
    from streamlit_js_eval import get_geolocation
    GEO_AVAILABLE = True
except:
    GEO_AVAILABLE = False

DATA_FILE = "staff_locations.csv"

# ------------------ DATA HANDLING ------------------
def load_data():
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        return df
    else:
        return pd.DataFrame(columns=["username", "role", "action", "lat", "lon", "timestamp","Totalkm travelled"])

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

# ------------------ LOGIN SYSTEM ------------------
USERS = {
    "admin": {"password": "admin123", "role": "admin"},
    "staff1": {"password": "staff123", "role": "staff"},
    "staff2": {"password": "staff456", "role": "staff"}
}

def login():
    st.title("🔐 Staff Tracking Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username in USERS and USERS[username]["password"] == password:
            st.session_state["username"] = username
            st.session_state["role"] = USERS[username]["role"]
            st.success("Login successful ✅")
            st.rerun()
        else:
            st.error("Invalid username or password ❌")

# ------------------ STAFF DASHBOARD ------------------
def staff_dashboard(username):
    st.sidebar.title(f"👤 Staff: {username}")
    st.title("🧑‍💼 Staff Dashboard")

    df = load_data()

    if GEO_AVAILABLE:
        loc = get_geolocation()
        lat, lon = None, None
        if loc and "coords" in loc:
            lat = loc["coords"]["latitude"]
            lon = loc["coords"]["longitude"]
    else:
        lat = st.number_input("Latitude", value=0.0)
        lon = st.number_input("Longitude", value=0.0)

    if st.button("📍 Punch In"):
        new_row = pd.DataFrame([[username, "staff", "punch_in", lat, lon, datetime.now()]],
                               columns=df.columns)
        df = pd.concat([df, new_row], ignore_index=True)
        save_data(df)
        st.success("Punched In successfully ✅")

    if st.button("⏰ Clock In"):
        new_row = pd.DataFrame([[username, "staff", "clock_in", lat, lon, datetime.now()]],
                               columns=df.columns)
        df = pd.concat([df, new_row], ignore_index=True)
        save_data(df)
        st.success("Clocked In successfully ✅")

    if st.button("🛑 Clock Out"):
        new_row = pd.DataFrame([[username, "staff", "clock_out", lat, lon, datetime.now()]],
                               columns=df.columns)
        df = pd.concat([df, new_row], ignore_index=True)
        save_data(df)
        st.success("Clocked Out successfully ✅")

    st.subheader("📌 Today's Travel Map")
    today_data = df[(df["username"] == username) &
                    (df["timestamp"].dt.date == datetime.now().date())]

    if today_data.empty:
        st.warning("No location data for today yet.")
    else:
        m = folium.Map(location=[today_data.iloc[-1]["lat"], today_data.iloc[-1]["lon"]], zoom_start=12)
        marker_cluster = MarkerCluster().add_to(m)
        for _, row in today_data.iterrows():
            folium.Marker([row["lat"], row["lon"]],
                          popup=f"{row['action']} @ {row['timestamp']}").add_to(marker_cluster)
        st_folium(m, width=700, height=500)

# ------------------ ADMIN DASHBOARD ------------------
def admin_dashboard():
    st.sidebar.title("🛠️ Admin Panel")
    st.title("📊 Admin Dashboard")

    df = load_data()

    if df.empty:
        st.warning("No staff data available yet.")
        return

    st.subheader("📋 Staff Records")
    st.dataframe(df)

    st.subheader("🌍 Staff Travel Map")
    m = folium.Map(location=[20.5937, 78.9629], zoom_start=5)  # India center
    marker_cluster = MarkerCluster().add_to(m)
    for _, row in df.iterrows():
        folium.Marker([row["lat"], row["lon"]],
                      popup=f"{row['username']} - {row['action']} @ {row['timestamp']}").add_to(marker_cluster)
    st_folium(m, width=700, height=500)

# ------------------ MAIN ------------------
def main():
    if "username" not in st.session_state:
        login()
    else:
        role = st.session_state["role"]
        username = st.session_state["username"]

        st.sidebar.write(f"Logged in as: {username} ({role})")
        if st.sidebar.button("🚪 Logout"):
            del st.session_state["username"]
            del st.session_state["role"]
            st.rerun()

        if role == "staff":
            staff_dashboard(username)
        elif role == "admin":
            admin_dashboard()

if __name__ == "__main__":
    main()
