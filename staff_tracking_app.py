import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from datetime import datetime, date
import random
import math
import hashlib
import os
import requests   # 🔥 added for API push

# Try geolocation package (real GPS). If missing, fallback to manual input.
try:
    from streamlit_js_eval import get_geolocation
    GEO_AVAILABLE = True
except Exception:
    GEO_AVAILABLE = False

# ==================== CONFIG ==================== #
st.set_page_config(page_title="Staff Tracker", layout="wide")
USER_FILE = "users.csv"
VISITS_FILE = "visits.csv"
API_URL = "http://127.0.0.1:8000/send_location"   # 🔥 FastAPI endpoint

# ==================== UTIL / INIT ==================== #
def ensure_files():
    if not os.path.exists(USER_FILE):
        pd.DataFrame(columns=["name", "username", "password", "dm", "branch", "product", "role"]).to_csv(USER_FILE, index=False)
    if not os.path.exists(VISITS_FILE):
        pd.DataFrame(columns=[
            "Username","Date","ClockInTime","PunchInTime","ClockOutTime",
            "Latitude","Longitude","DistanceKm",
            "CustomerName","ProductHandling","Mobile","CollectionAmount","Remarks",
            "RecordType"
        ]).to_csv(VISITS_FILE, index=False)

ensure_files()

def load_users():
    return pd.read_csv(USER_FILE)

def save_user(name, username, password, dm, branch, product, role):
    users = load_users()
    hashed_pw = hashlib.sha256(password.encode()).hexdigest()
    row = pd.DataFrame([[name, username, hashed_pw, dm, branch, product, role]],
                       columns=["name","username","password","dm","branch","product","role"])
    users = pd.concat([users, row], ignore_index=True)
    users.to_csv(USER_FILE, index=False)

def verify_user(username, password):
    users = load_users()
    hashed_pw = hashlib.sha256(password.encode()).hexdigest()
    row = users[(users["username"] == username) & (users["password"] == hashed_pw)]
    return row.iloc[0] if not row.empty else None

def load_visits():
    return pd.read_csv(VISITS_FILE)

def append_visit(row_dict):
    df = load_visits()
    df = pd.concat([df, pd.DataFrame([row_dict])], ignore_index=True)
    df.to_csv(VISITS_FILE, index=False)

# 🔥 Push GPS to FastAPI also
def send_location_to_api(username, lat, lon, record_type):
    try:
        requests.post(API_URL, json={
            "username": username,
            "latitude": lat,
            "longitude": lon,
            "record_type": record_type,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        st.warning(f"⚠️ Could not sync to API: {e}")

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

def get_last_location_for_today(username):
    df = load_visits()
    today_str = date.today().isoformat()
    df_u = df[(df["Username"] == username) & (df["Date"] == today_str)]
    if df_u.empty:
        return None
    last = df_u.iloc[-1]
    try:
        return float(last["Latitude"]), float(last["Longitude"])
    except Exception:
        return None

def get_today_user_df(username):
    df = load_visits()
    today_str = date.today().isoformat()
    return df[(df["Username"] == username) & (df["Date"] == today_str)]

def reset_punch_form_state():
    for k in ["cust_name","product_handling","mobile","collection_amount","remarks"]:
        if k in st.session_state:
            del st.session_state[k]

def random_location():
    return (random.uniform(8.0, 13.0), random.uniform(77.0, 80.5))

# ==================== SESSION ==================== #
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None

# ==================== SIDEBAR MENU ==================== #
menu = st.sidebar.radio("Menu", ["Login", "Register", "Logout"])

# ==================== REGISTER ==================== #
if menu == "Register" and not st.session_state.logged_in:
    st.title("📝 User Registration")
    colA, colB = st.columns(2)
    with colA:
        name = st.text_input("Full Name")
        username = st.text_input("Username")
        dm = st.text_input("DM Name")
    with colB:
        branch = st.selectbox("Branch", ["Chennai","Coimbatore","Madurai"])
        product = st.selectbox("Default Product", ["Laptop","Mobile","TV","AC","Washing Machine"])
        password = st.text_input("Password", type="password")

    role = st.selectbox("Role", ["staff", "admin"])

    if st.button("Register"):
        users = load_users()
        if not name or not username or not password:
            st.error("Please fill Full Name, Username and Password.")
        elif username in users["username"].values:
            st.error("⚠️ Username already exists. Choose another.")
        else:
            save_user(name, username, password, dm, branch, product, role)
            st.success("✅ Registration successful! Please go to Login.")

# ==================== LOGIN ==================== #
elif menu == "Login" and not st.session_state.logged_in:
    st.title("🔐 User Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        user = verify_user(username, password)
        if user is not None:
            st.session_state.logged_in = True
            st.session_state.user = user
            st.success(f"✅ Welcome {user['name']}! (Role: {user['role']})")
        else:
            st.error("❌ Invalid username or password")

# ==================== ADMIN DASHBOARD ==================== #
elif st.session_state.logged_in and st.session_state.user["role"] == "admin":
    st.title("📊 Admin Dashboard")
    df = load_visits()
    if df.empty:
        st.info("No staff activity logged yet.")
    else:
        # filters + metrics + map (same as before) ...
        pass

# ==================== STAFF DASHBOARD ==================== #
elif st.session_state.logged_in:
    user = st.session_state.user
    st.title(f"👋 Welcome {user['name']} — {user['branch']} — Role: {user['role']}")

    st.caption("📍 Location capture will use your phone's GPS. If prompted, please allow location access.")

    def capture_location_ui():
        try:
            loc = get_geolocation()
            if loc and "coords" in loc:
                latitude = loc["coords"]["latitude"]
                longitude = loc["coords"]["longitude"]
                return latitude, longitude, True
            else:
                return None, None, False
        except Exception:
            lat, lon = random_location()
            return lat, lon, False

    today_str = date.today().isoformat()
    df_today = get_today_user_df(user["username"])

    # --- CLOCK IN ---
    if df_today[df_today["RecordType"] == "Clock In"].empty:
        st.subheader("🟢 Clock In")
        lat, lon, gps_ok = capture_location_ui()
        if st.button("Clock In (Start Day)"):
            row = {...}  # same row dict as before
            append_visit(row)
            send_location_to_api(user["username"], lat, lon, "Clock In")   # 🔥 push to API
            st.success("✅ Clock In recorded!")
            st.rerun()

    # --- PUNCH IN ---
    # inside form after append_visit(row):
    # send_location_to_api(user["username"], lat, lon, "Punch In")

    # --- CLOCK OUT ---
    # after append_visit(row):
    # send_location_to_api(user["username"], lat_co, lon_co, "Clock Out")

# ==================== LOGOUT ==================== #
elif menu == "Logout":
    st.session_state.logged_in = False
    st.session_state.user = None
    st.success("✅ Logged out successfully")
