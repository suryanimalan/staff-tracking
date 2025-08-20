import streamlit as st
import pandas as pd
import os
import csv
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2
from streamlit_js_eval import get_geolocation

USERS_FILE = "users.csv"
ATTENDANCE_FILE = "attendance.csv"

# ---------------- Utility functions ----------------
def load_users():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["username", "password", "name", "role"])
            writer.writerow(["admin", "admin123", "Administrator", "admin"])
    return pd.read_csv(USERS_FILE)

def save_attendance(data):
    file_exists = os.path.isfile(ATTENDANCE_FILE)
    with open(ATTENDANCE_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "username", "name", "date", "action", "time",
                "latitude", "longitude", "customer", "product",
                "collection", "remarks"
            ])
        writer.writerow(data)

def load_attendance():
    if not os.path.exists(ATTENDANCE_FILE):
        return pd.DataFrame(columns=[
            "username","name","date","action","time",
            "latitude","longitude","customer","product",
            "collection","remarks"
        ])
    return pd.read_csv(ATTENDANCE_FILE)

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0  # km
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    return R * (2 * atan2(sqrt(a), sqrt(1-a)))

# ---------------- Streamlit UI ----------------
st.set_page_config(page_title="Staff Tracking", layout="wide")

st.title("📍 Staff Tracking Dashboard")

users = load_users()

# --- Login Form ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.subheader("🔑 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        user = users[(users["username"] == username) & (users["password"] == password)]
        if not user.empty:
            st.session_state.logged_in = True
            st.session_state.user = user.iloc[0].to_dict()
            st.success(f"✅ Welcome {st.session_state.user['name']} ({st.session_state.user['role']})")
        else:
            st.error("❌ Invalid credentials")

else:
    user = st.session_state.user
    st.sidebar.write(f"👋 Hello, {user['name']} ({user['role']})")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    # ============== Staff Panel =================
    if user["role"] == "staff":
        st.subheader("🕒 Attendance Actions")

        # Live GPS fetch
        loc = get_geolocation()
        if loc:
            latitude = loc["coords"]["latitude"]
            longitude = loc["coords"]["longitude"]
            st.success(f"📍 Live GPS captured: {latitude}, {longitude}")
        else:
            latitude = None
            longitude = None
            st.warning("⚠️ Location not available. Please allow GPS in your browser.")

        action = st.selectbox("Action", ["Clock In", "Customer Visit", "Clock Out"])
        customer = product = collection = remarks = ""

        if action == "Customer Visit":
            customer = st.text_input("Customer Name")
            product = st.text_input("Product")
            collection = st.number_input("Collection Amount", min_value=0, step=1)
            remarks = st.text_area("Remarks")

        if st.button("Submit"):
            if latitude and longitude:
                save_attendance([
                    user["username"], user["name"], datetime.now().date(),
                    action, datetime.now().strftime("%H:%M:%S"),
                    latitude, longitude, customer, product, collection, remarks
                ])
                st.success("✅ Data saved successfully")
            else:
                st.error("❌ GPS not available. Cannot save record.")

    # ============== Admin Panel =================
    elif user["role"] == "admin":
        st.subheader("📊 Admin Dashboard")

        df = load_attendance()
        if df.empty:
            st.info("No attendance data yet.")
        else:
            st.dataframe(df)

            # Distance Calculation
            st.write("### 🚗 Distance Travelled by Staff")
            staff_list = df["username"].unique()
            report = []
            for staff in staff_list:
                sdf = df[df["username"] == staff].sort_values(["date", "time"])
                km = 0
                prev_lat = prev_lon = None
                for _, row in sdf.iterrows():
                    if pd.notnull(row["latitude"]) and pd.notnull(row["longitude"]):
                        if prev_lat is not None:
                            km += haversine(prev_lat, prev_lon, row["latitude"], row["longitude"])
                        prev_lat, prev_lon = row["latitude"], row["longitude"]
                report.append([staff, sdf.iloc[0]["name"], round(km, 2)])
            st.dataframe(pd.DataFrame(report, columns=["Username", "Name", "Total KM"]))
