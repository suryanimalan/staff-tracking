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

try:
    from streamlit_geolocation import geolocation
    GEO_AVAILABLE = True
except Exception:
    GEO_AVAILABLE = False

# ==================== CONFIG ==================== #
st.set_page_config(page_title="Staff Tracker", layout="wide")
USER_FILE = "users.csv"
VISITS_FILE = "visits.csv"

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

def save_user(name, username, password, dm, branch, product, role="user"):
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
    role = st.selectbox("Role", ["user","admin"])

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
            st.success(f"✅ Welcome {user['name']} ({user['role']})!")
        else:
            st.error("❌ Invalid username or password")

# ==================== DASHBOARD ==================== #
elif st.session_state.logged_in:
    user = st.session_state.user

    # ------------------ ADMIN ------------------ #
    if user["role"] == "admin":
        st.title(f"🛠️ Admin Dashboard — {user['name']}")
        df = load_visits()
        users = load_users()

        st.subheader("📊 Filter Reports")
        col1, col2, col3 = st.columns(3)
        with col1:
            branch_filter = st.selectbox("Branch", ["All"] + users["branch"].dropna().unique().tolist())
        with col2:
            user_filter = st.selectbox("User", ["All"] + users["username"].dropna().unique().tolist())
        with col3:
            date_filter = st.date_input("Date", value=None)

        df_filtered = df.copy()
        if branch_filter != "All":
            u_in_branch = users[users["branch"]==branch_filter]["username"].tolist()
            df_filtered = df_filtered[df_filtered["Username"].isin(u_in_branch)]
        if user_filter != "All":
            df_filtered = df_filtered[df_filtered["Username"]==user_filter]
        if date_filter:
            df_filtered = df_filtered[df_filtered["Date"]==date_filter.isoformat()]

        st.dataframe(df_filtered, use_container_width=True)

        if st.button("📥 Export to Excel"):
            fname = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            df_filtered.to_excel(fname, index=False)
            st.success(f"Report saved as {fname}")

    # ------------------ USER ------------------ #
    else:
        # [KEEP your existing Clock In / Punch In / Clock Out dashboard code here…]
        st.info("User dashboard same as before (Clock In / Punch / Clock Out / Map / Metrics).")

# ==================== LOGOUT ==================== #
elif menu == "Logout":
    st.session_state.logged_in = False
    st.session_state.user = None
    st.success("✅ You have been logged out.")
	