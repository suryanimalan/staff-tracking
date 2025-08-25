import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from datetime import datetime, date
from geopy.distance import geodesic
import os

# Try to get real GPS location for mobile staff
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
        # Ensure numeric columns exist
        for col in ["lat","lon","km_travelled","collection_amount"]:
            if col not in df.columns:
                df[col] = 0.0
        # Ensure text columns exist
        for col in ["customer_name","product"]:
            if col not in df.columns:
                df[col] = ""
        return df
    else:
        return pd.DataFrame(columns=[
            "username","role","action","lat","lon","timestamp",
            "km_travelled","collection_amount","customer_name","product"
        ])

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

# ------------------ LOGIN SYSTEM ------------------
USERS = {
    "admin": {"password": "admin123", "role": "admin"},
    "surya": {"password": "surya1708", "role": "staff"},
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
    
    # --- Get GPS automatically ---
    lat, lon = 0.0, 0.0
    if GEO_AVAILABLE:
        try:
            loc = get_geolocation()
            if loc and "coords" in loc:
                lat = loc["coords"].get("latitude", 0.0)
                lon = loc["coords"].get("longitude", 0.0)
            else:
                st.warning("Could not get GPS automatically yet. Please allow location access in your browser.")
        except Exception as e:
            st.warning(f"Automatic GPS failed: {e}")
    else:
        st.warning("GPS not available. Please open on a supported mobile browser.")

    # Helper to calculate KM travelled
    def calculate_km(df, username, lat, lon):
        user_data = df[df["username"] == username]
        if user_data.empty:
            return 0.0
        last_row = user_data.iloc[-1]
        if pd.isna(last_row["lat"]) or pd.isna(last_row["lon"]):
            return 0.0
        return geodesic((last_row["lat"], last_row["lon"]), (lat, lon)).km

    # Today's Data
    today_data = df[(df["username"] == username) &
                    (df["timestamp"].dt.date == datetime.now().date())]

    # Daily Summary
    if not today_data.empty:
        total_km = today_data["km_travelled"].sum()
        total_collection = today_data["collection_amount"].sum()
        st.subheader("📊 Daily Summary")
        st.write(f"**Total KM Travelled:** {total_km:.2f} km")
        st.write(f"**Total Collection:** ₹{total_collection:.2f}")

    # Punch In
    if st.button("📍 Punch In"):
        km = calculate_km(df, username, lat, lon)
        new_row = pd.DataFrame([[username, "staff", "punch_in", lat, lon, datetime.now(), km, 0.0, "", ""]],
                               columns=df.columns)
        df = pd.concat([df, new_row], ignore_index=True)
        save_data(df)
        st.success("Punched In successfully ✅")

    # Clock In / Collection
    st.subheader("💰 Collection Entry")
    customer_name = st.text_input("Customer Name")
    product = st.text_input("Product")
    collection = st.number_input("Enter Collection Amount (₹)", value=0.0)

    if st.button("⏰ Clock In"):
        km = calculate_km(df, username, lat, lon)
        new_row = pd.DataFrame([[username, "staff", "clock_in", lat, lon, datetime.now(), km, collection, customer_name, product]],
                               columns=df.columns)
        df = pd.concat([df, new_row], ignore_index=True)
        save_data(df)
        st.success(f"Clocked In ✅ | KM: {km:.2f} | Customer: {customer_name} | Product: {product} | Collection: ₹{collection}")

    # Clock Out
    if st.button("🛑 Clock Out"):
        km = calculate_km(df, username, lat, lon)
        new_row = pd.DataFrame([[username, "staff", "clock_out", lat, lon, datetime.now(), km, 0.0, "", ""]],
                               columns=df.columns)
        df = pd.concat([df, new_row], ignore_index=True)
        save_data(df)
        st.success("Clocked Out successfully ✅")

    # Map
    st.subheader("📌 Today's Travel Map")
    if today_data.empty:
        st.warning("No location data for today yet.")
    else:
        # Filter valid coordinates
        map_data = today_data.dropna(subset=["lat","lon"])
        map_data = map_data[(map_data["lat"]!=0) & (map_data["lon"]!=0)]
        if not map_data.empty:
            m = folium.Map(location=[map_data.iloc[-1]["lat"], map_data.iloc[-1]["lon"]], zoom_start=12)
            marker_cluster = MarkerCluster().add_to(m)
            for _, row in map_data.iterrows():
                popup_text = (f"{row['action']} @ {row['timestamp']} | "
                              f"KM: {row['km_travelled']:.2f} | "
                              f"Customer: {row['customer_name']} | "
                              f"Product: {row['product']} | "
                              f"Collection: ₹{row['collection_amount']}")
                folium.Marker([row["lat"], row["lon"]], popup=popup_text).add_to(marker_cluster)
            st_folium(m, width=350, height=500)  # mobile-friendly
        else:
            st.warning("No valid location data to display on map.")

# ------------------ ADMIN DASHBOARD ------------------
def admin_dashboard():
    st.sidebar.title("🛠️ Admin Panel")
    st.title("📊 Admin Dashboard")
    
    df = load_data()
    if df.empty:
        st.warning("No staff data available yet.")
        return

    # Ensure numeric lat/lon
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")

    # Filters
    selected_date = st.date_input("Select Date", value=date.today())
    staff_list = ["All"] + sorted(df["username"].unique().tolist())
    selected_staff = st.selectbox("Select Staff", staff_list)

    filtered_df = df[df["timestamp"].dt.date == selected_date]
    if selected_staff != "All":
        filtered_df = filtered_df[filtered_df["username"] == selected_staff]

    if filtered_df.empty:
        st.warning("No data available for selected filters.")
        return

    # Daily Totals
    summary = filtered_df.groupby("username").agg(
        Total_KM=("km_travelled", "sum"),
        Total_Collection=("collection_amount", "sum")
    ).reset_index()
    st.subheader("📊 Daily Totals per Staff")
    st.dataframe(summary)

    # Records Table
    st.subheader("📋 Staff Records")
    st.dataframe(filtered_df)

    # Map
    st.subheader("🌍 Staff Travel Map")
    valid_data = filtered_df.dropna(subset=["lat","lon"])
    valid_data = valid_data[(valid_data["lat"]!=0) & (valid_data["lon"]!=0)]
    if not valid_data.empty:
        m = folium.Map(location=[valid_data.iloc[-1]["lat"], valid_data.iloc[-1]["lon"]], zoom_start=5)
        marker_cluster = MarkerCluster().add_to(m)
        for _, row in valid_data.iterrows():
            popup_text = (f"{row['username']} - {row['action']} @ {row['timestamp']} | "
                          f"KM: {row['km_travelled']:.2f} | "
                          f"Customer: {row['customer_name']} | "
                          f"Product: {row['product']} | "
                          f"Collection: ₹{row['collection_amount']}")
            folium.Marker([row["lat"], row["lon"]], popup=popup_text).add_to(marker_cluster)
        st_folium(m, width=350, height=500)  # mobile-friendly
    else:
        st.warning("No valid location data to display on map.")

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
