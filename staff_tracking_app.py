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
menu = st.sidebar.radio("Menu", ["Login", "Register", "Home", "Logout"])

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
if "user" in st.session_state and st.session_state.user is not None:
    user = st.session_state.user
    role = user["role"]
else:
    role = None

if role == "admin":   # match how you saved role in registration
    st.title("📊 Admin Dashboard")
    st.info("View all staff visits with filters, summary, charts & map")

    # ---------------- LOAD DATA ----------------
    try:
        df = pd.read_csv("staff_tracking.csv")
    except FileNotFoundError:
        st.error("❌ staff_tracking.csv not found!")
        st.stop()

    # Clean column names (lowercase, strip spaces)
    df.rename(columns=lambda x: str(x).strip().lower(), inplace=True)

    # Ensure date column is datetime
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # ---------------- FILTERS ----------------
    dm_filter = st.selectbox("Select DM", ["All"] + sorted(df["dm"].dropna().unique().tolist() if "dm" in df else []))
    branch_filter = st.selectbox("Select Branch", ["All"] + sorted(df["branch"].dropna().unique().tolist() if "branch" in df else []))
    product_filter = st.selectbox("Select Product", ["All"] + sorted(df["product"].dropna().unique().tolist() if "product" in df else []))
    date_range = st.date_input("Select Date Range", [])

    filtered = df.copy()
    if dm_filter != "All" and "dm" in df:
        filtered = filtered[filtered["dm"] == dm_filter]
    if branch_filter != "All" and "branch" in df:
        filtered = filtered[filtered["branch"] == branch_filter]
    if product_filter != "All" and "product" in df:
        filtered = filtered[filtered["product"] == product_filter]
    if len(date_range) == 2:
        start, end = date_range
        filtered = filtered[(filtered["date"] >= pd.to_datetime(start)) & (filtered["date"] <= pd.to_datetime(end))]

    # ---------------- SUMMARY ----------------
    total_visits = len(filtered)

    if "collectionamount" in filtered:
        total_collection = filtered["collectionamount"].sum()
        avg_collection = filtered["collectionamount"].mean() if total_visits > 0 else 0
    else:
        total_collection = 0
        avg_collection = 0

    st.metric("Total Visits", total_visits)
    st.metric("Total Collection", f"₹{total_collection:,.2f}")
    st.metric("Avg Collection", f"₹{avg_collection:,.2f}")

    # ---------------- TABLE ----------------
    st.subheader("📋 Staff Visit Records")
    st.dataframe(filtered)

    # ---------------- CHARTS ----------------
    if not filtered.empty:
        st.subheader("📈 Charts")

        if "dm" in filtered and "collectionamount" in filtered:
            st.bar_chart(filtered.groupby("dm")["collectionamount"].sum())

        if "branch" in filtered and "collectionamount" in filtered:
            st.bar_chart(filtered.groupby("branch")["collectionamount"].sum())

        if "product" in filtered and "collectionamount" in filtered:
            st.bar_chart(filtered.groupby("product")["collectionamount"].sum())
    else:
        st.warning("⚠️ No data available for charts")

    # ---------------- MAP ----------------
    st.subheader("🗺️ Visit Map")

    if "latitude" in filtered and "longitude" in filtered:
        map_data = filtered.dropna(subset=["latitude", "longitude"])

        if not map_data.empty:
            lat_mean = map_data["latitude"].mean()
            lon_mean = map_data["longitude"].mean()

            if pd.isna(lat_mean) or pd.isna(lon_mean):
                lat_mean, lon_mean = 11.0, 78.0

            m = folium.Map(location=[lat_mean, lon_mean], zoom_start=7)

            for _, row in map_data.iterrows():
                popup_txt = []
                if "customername" in row:
                    popup_txt.append(str(row["customername"]))
                if "branch" in row:
                    popup_txt.append(f"({row['branch']})")
                if "product" in row and "collectionamount" in row:
                    popup_txt.append(f"{row['product']} - ₹{row['collectionamount']}")

                folium.Marker(
                    [row["latitude"], row["longitude"]],
                    popup="<br>".join(popup_txt)
                ).add_to(m)

            st_folium(m, width=700, height=500)
        else:
            st.warning("⚠️ No valid coordinates found for selected filters")
