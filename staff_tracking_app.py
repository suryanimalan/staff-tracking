import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from datetime import datetime
import os
from geopy.distance import geodesic

# ------------------ FILE ------------------
DATA_FILE = "staff_locations.csv"

# ------------------ DATA HANDLING ------------------
def load_data():
    required_cols = [
        "username", "role", "action", "lat", "lon", "timestamp",
        "km_travelled", "customer_name", "product", "collection_amount",
        "bm", "dm"
    ]
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        # Ensure all required columns exist
        for col in required_cols:
            if col not in df.columns:
                df[col] = "" if col in ["customer_name", "product", "bm", "dm"] else 0
        return df[required_cols]
    else:
        return pd.DataFrame(columns=required_cols)

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

# ------------------ USERS ------------------
USERS = {
    "admin": {"password": "admin123", "role": "admin", "bm": None, "dm": None},
    "surya": {"password": "surya1708", "role": "staff", "bm": "BM1", "dm": "DM1"},
    "staff2": {"password": "staff456", "role": "staff", "bm": "BM2", "dm": "DM1"},
    "staff3": {"password": "staff789", "role": "staff", "bm": "BM1", "dm": "DM2"},
}

# ------------------ LOGIN ------------------
def login():
    st.title("🔐 Staff Tracking Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username in USERS and USERS[username]["password"] == password:
            st.session_state["username"] = username
            st.session_state["role"] = USERS[username]["role"]
            st.session_state["bm"] = USERS[username].get("bm")
            st.session_state["dm"] = USERS[username].get("dm")
            st.success("Login successful ✅")
            st.rerun()
        else:
            st.error("Invalid username or password ❌")

# ------------------ STAFF DASHBOARD ------------------
def staff_dashboard(username):
    st.sidebar.title(f"👤 Staff: {username}")
    st.title("🧑‍💼 Staff Dashboard")

    df = load_data()

    # Manual GPS entry for demo (replace with real geolocation if needed)
    lat = st.number_input("Latitude", value=0.0)
    lon = st.number_input("Longitude", value=0.0)

    # Common inputs
    customer_name = st.text_input("Customer Name")
    product = st.text_input("Product")
    collection_amount = st.number_input("Collection Amount", min_value=0.0)

    # Determine last known point for KM calculation
    user_data = df[df["username"] == username].sort_values("timestamp")
    last_lat, last_lon = None, None
    if not user_data.empty:
        last_lat = user_data.iloc[-1]["lat"]
        last_lon = user_data.iloc[-1]["lon"]

    def log_action(action):
        nonlocal last_lat, last_lon
        km_travelled = 0.0
        if last_lat and last_lon and lat and lon:
            km_travelled = geodesic((last_lat, last_lon), (lat, lon)).km

        new_row = pd.DataFrame([[
            username, "staff", action, lat, lon, datetime.now(),
            km_travelled, customer_name, product, collection_amount,
            USERS[username].get("bm"), USERS[username].get("dm")
        ]], columns=df.columns)

        df2 = pd.concat([df, new_row], ignore_index=True)
        save_data(df2)
        st.success(f"{action} recorded ✅")

    if st.button("📍 Punch In"):
        log_action("punch_in")

    if st.button("⏰ Clock In"):
        log_action("clock_in")

    if st.button("🛑 Clock Out"):
        log_action("clock_out")

    # Travel Map
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
                          popup=f"{row['action']} @ {row['timestamp']} | {row['km_travelled']:.2f} km | {row['customer_name']} | {row['product']} | Collection: {row['collection_amount']}").add_to(marker_cluster)
        st_folium(m, width=700, height=500)

    # Daily Summary
    if not today_data.empty:
        total_km = today_data["km_travelled"].sum()
        total_collection = today_data["collection_amount"].sum()
        st.subheader("📊 Daily Summary")
        st.write(f"**Total KM Travelled:** {total_km:.2f} km")
        st.write(f"**Total Collection:** ₹{total_collection:.2f}")

# ------------------ ADMIN DASHBOARD ------------------
def admin_dashboard():
    st.sidebar.title("🛠️ Admin Panel")
    st.title("📊 Admin Dashboard")

    df = load_data()
    if df.empty:
        st.warning("No staff data available yet.")
        return

    # ---------------- Filters ----------------
    st.sidebar.subheader("🔎 Filters")
    staff_filter = st.sidebar.multiselect("Select Staff", options=df["username"].unique())
    bm_filter = st.sidebar.multiselect("Select BM", options=df["bm"].dropna().unique())
    dm_filter = st.sidebar.multiselect("Select DM", options=df["dm"].dropna().unique())
    date_filter = st.sidebar.date_input("Select Date", value=datetime.now().date())

    filtered_df = df.copy()
    if staff_filter:
        filtered_df = filtered_df[filtered_df["username"].isin(staff_filter)]
    if bm_filter:
        filtered_df = filtered_df[filtered_df["bm"].isin(bm_filter)]
    if dm_filter:
        filtered_df = filtered_df[filtered_df["dm"].isin(dm_filter)]
    if date_filter:
        filtered_df = filtered_df[filtered_df["timestamp"].dt.date == date_filter]

    # ---------------- Table ----------------
    st.subheader("📋 Staff Records")
    st.dataframe(filtered_df)

    # ---------------- Map ----------------
    st.subheader("🌍 Staff Travel Map")
    if not filtered_df.empty:
        m = folium.Map(location=[20.5937, 78.9629], zoom_start=5)  # India center
        marker_cluster = MarkerCluster().add_to(m)
        for _, row in filtered_df.iterrows():
            folium.Marker([row["lat"], row["lon"]],
                          popup=f"{row['username']} - {row['action']} @ {row['timestamp']} | {row['km_travelled']:.2f} km | {row['customer_name']} | {row['product']} | Collection: {row['collection_amount']}").add_to(marker_cluster)
        st_folium(m, width=700, height=500)
    else:
        st.warning("No data for selected filters.")

    # ---------------- Daily Summary ----------------
    if not filtered_df.empty:
        summary = filtered_df.groupby("username").agg(
            total_km=("km_travelled", "sum"),
            total_collection=("collection_amount", "sum")
        ).reset_index()
        st.subheader("📊 Daily Summary per Staff")
        st.dataframe(summary)

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
