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

# ==================== CONFIG ====================
# st.set_page_config(page_title="Staff Tracker", layout="wide")
USER_FILE = "users.csv"
VISITS_FILE = "visits.csv"
API_URL = "http://127.0.0.1:8000/send_location"   # 🔥 FastAPI endpoint

# ==================== UTIL / INIT ====================
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

# ==================== SESSION ====================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.show_dashboard = False

# ==================== SIDEBAR MENU ====================
menu = st.sidebar.radio("Menu", ["Login", "Register", "Home", "Logout"])

# ==================== REGISTER / EDIT USER ====================
if menu == "Register" and not st.session_state.logged_in:
    st.title("📝 User Registration / Edit")

    users = load_users()
    usernames = users["username"].dropna().tolist()  # drop NaN usernames
    selected_user = st.selectbox("Select User to Edit (or 'New' for registration)", ["New"] + usernames, key="reg_select_user")

    if selected_user != "New":
        user_row = users[users["username"] == selected_user].iloc[0]

        # Safe defaults for NaN values
        name_value = user_row["name"] if pd.notna(user_row["name"]) else ""
        username_value = user_row["username"] if pd.notna(user_row["username"]) else ""
        dm_value = user_row["dm"] if pd.notna(user_row["dm"]) else ""
        branch_value = user_row["branch"] if pd.notna(user_row["branch"]) else "Chennai"
        product_value = user_row["product"] if pd.notna(user_row["product"]) else "Laptop"
        role_value = user_row["role"] if pd.notna(user_row["role"]) else "staff"

        # Input fields with unique keys
        name = st.text_input("Full Name", value=name_value, key="reg_name")
        username = st.text_input("Username", value=username_value, key="reg_username")
        dm = st.text_input("DM Name", value=dm_value, key="reg_dm")
        branch = st.selectbox("Branch", ["Chennai","Coimbatore","Madurai"],
                              index=["Chennai","Coimbatore","Madurai"].index(branch_value), key="reg_branch")
        product = st.selectbox("Default Product", ["Laptop","Mobile","TV","AC","Washing Machine"],
                               index=["Laptop","Mobile","TV","AC","Washing Machine"].index(product_value), key="reg_product")
        role = st.selectbox("Role", ["staff", "admin"], index=["staff","admin"].index(role_value), key="reg_role")
    else:
        # New user registration
        name = st.text_input("Full Name", key="reg_name_new")
        username = st.text_input("Username", key="reg_username_new")
        dm = st.text_input("DM Name", key="reg_dm_new")
        branch = st.selectbox("Branch", ["Chennai","Coimbatore","Madurai"], key="reg_branch_new")
        product = st.selectbox("Default Product", ["Laptop","Mobile","TV","AC","Washing Machine"], key="reg_product_new")
        role = st.selectbox("Role", ["staff", "admin"], key="reg_role_new")

    password = st.text_input("Password (leave blank to keep current)", type="password", key="reg_password")

    if st.button("Save User", key="reg_save_btn"):
        if selected_user != "New":
            # Update existing user
            if password:
                hashed_pw = hashlib.sha256(password.encode()).hexdigest()
                users.loc[users["username"] == selected_user, "password"] = hashed_pw
            users.loc[users["username"] == selected_user, ["name","dm","branch","product","role","username"]] = [name, dm, branch, product, role, username]
            users.to_csv(USER_FILE, index=False)
            st.success("✅ User updated successfully!")
        else:
            # New registration
            if username in users["username"].values:
                st.error("⚠️ Username already exists.")
            elif not password:
                st.error("⚠️ Please enter a password for new user")
            else:
                hashed_pw = hashlib.sha256(password.encode()).hexdigest()
                new_row = pd.DataFrame([[name, username, hashed_pw, dm, branch, product, role]], columns=users.columns)
                users = pd.concat([users, new_row], ignore_index=True)
                users.to_csv(USER_FILE, index=False)
                st.success("✅ New user registered successfully!")

# ==================== LOGIN ====================
elif menu == "Login" and not st.session_state.logged_in:
    st.title("🔐 User Login")
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")

    if st.button("Login", key="login_btn"):
        user = verify_user(username, password)
        if user is not None:
            st.session_state.logged_in = True
            st.session_state.user = user
            st.session_state.show_dashboard = True
            st.success(f"✅ Welcome {user['name']}! (Role: {user['role']})")
        else:
            st.error("❌ Invalid username or password")

# ==================== LOGOUT ====================
elif menu == "Logout":
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.show_dashboard = False
    st.success("Logged out successfully. Please refresh the page.")


# ==================== ADMIN DASHBOARD ==================== #
filtered = pd.DataFrame()  # initialize filtered to avoid Pylance warning
if "user" in st.session_state and st.session_state.user is not None:
    user = st.session_state.user
    role = user["role"]
else:
    role = None

if role == "admin":
    st.title("📊 Admin Dashboard")
    st.info("View all staff visits with filters, summary, charts & map")

    # ---------------- LOAD DATA ----------------
    try:
        df = pd.read_csv(VISITS_FILE)   # Make sure df is loaded here
    except FileNotFoundError:
        st.error("❌ visits.csv not found!")
        st.stop()

    # Clean column names
    df.rename(columns=lambda x: str(x).strip().lower(), inplace=True)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # ---------------- FILTERS ----------------
    dm_values = sorted(df["dm"].dropna().unique()) if "dm" in df else []
    branch_values = sorted(df["branch"].dropna().unique()) if "branch" in df else []
    product_values = sorted(df["product"].dropna().unique()) if "product" in df else []
    user_values = sorted(df["username"].dropna().unique()) if "username" in df else []

    dm_filter = st.selectbox("Select DM", ["All"] + dm_values)
    branch_filter = st.selectbox("Select Branch", ["All"] + branch_values)
    product_filter = st.selectbox("Select Product", ["All"] + product_values)
    user_filter = st.selectbox("Select User", ["All"] + user_values)
    date_range = st.date_input("Select Date Range", [])

    # Apply filters
    filtered = df.copy()
    if dm_filter != "All" and "dm" in df:
        filtered = filtered[filtered["dm"] == dm_filter]
    if branch_filter != "All" and "branch" in df:
        filtered = filtered[filtered["branch"] == branch_filter]
    if product_filter != "All" and "product" in df:
        filtered = filtered[filtered["product"] == product_filter]
    if user_filter != "All" and "username" in df:
        filtered = filtered[filtered["username"] == user_filter]
    if len(date_range) == 2:
        start, end = date_range
        filtered = filtered[(filtered["date"] >= pd.to_datetime(start)) & (filtered["date"] <= pd.to_datetime(end))]

    # ---------------- SUMMARY ----------------
    st.metric("Total Visits", len(filtered))
    st.metric("Total Collection", filtered["collectionamount"].sum() if "collectionamount" in filtered else 0)
    st.metric("Avg Collection", filtered["collectionamount"].mean() if "collectionamount" in filtered else 0)

    st.subheader("📋 Staff Visit Records")
    st.dataframe(filtered)

    # ---------------- MAP ----------------
    st.subheader("🗺️ Visit Map with Route Lines")
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
                folium.CircleMarker(
                    location=[row["latitude"], row["longitude"]],
                    radius=5,
                    color="blue",
                    fill=True,
                    fill_color="blue",
                    popup="<br>".join(popup_txt)
                ).add_to(m)

            for uname in map_data["username"].unique():
                user_data = map_data[map_data["username"] == uname].sort_values("date")
                coords = list(zip(user_data["latitude"], user_data["longitude"]))
                if len(coords) > 1:
                    folium.PolyLine(coords, color="red", weight=3, opacity=0.7, tooltip=uname).add_to(m)

            st_folium(m, width=700, height=500)
        else:
            st.warning("⚠️ No valid coordinates found for selected filters")



# ==================== STAFF DASHBOARD ====================
if st.session_state.get("logged_in") and st.session_state.get("user") is not None:
    user = st.session_state.user
    role = user["role"]

    if role == "staff":
        st.title("🧑‍💼 Staff Dashboard")
        st.info(f"Welcome {user['name']}!")

        username = user["username"]
        today_str = date.today().isoformat()
        today_df = get_today_user_df(username)

        # ---------------- LOCATION FUNCTION ----------------
        def get_current_location():
            if GEO_AVAILABLE:
                try:
                    loc = get_geolocation()
                    if loc and "lat" in loc and "lon" in loc:
                        return loc["lat"], loc["lon"]
                    else:
                        st.warning("⚠️ GPS data not available, using fallback location.")
                except Exception as e:
                    st.warning(f"⚠️ Error getting GPS: {e}")
            return random_location()  # fallback

        # ---------------- CLOCK IN ----------------
        if st.button("Clock In", key="staff_clockin"):
            if not today_df.empty and today_df.iloc[-1]["ClockInTime"]:
                st.warning("⏰ Already Clocked In today")
            else:
                lat, lon = get_current_location()
                row = {
                    "Username": username,
                    "Date": today_str,
                    "ClockInTime": datetime.now().strftime("%H:%M:%S"),
                    "PunchInTime": "",
                    "ClockOutTime": "",
                    "Latitude": lat,
                    "Longitude": lon,
                    "DistanceKm": 0,
                    "CustomerName": "",
                    "ProductHandling": "",
                    "Mobile": "",
                    "CollectionAmount": 0,
                    "Remarks": "",
                    "RecordType": "ClockIn"
                }
                append_visit(row)
                send_location_to_api(username, lat, lon, "ClockIn")
                st.success("✅ Clocked In Successfully")
                today_df = get_today_user_df(username)  # refresh

        # ---------------- PUNCH IN ----------------
        st.subheader("Punch In / Customer Visit")
        cust_name = st.text_input("Customer Name", key="staff_cust_name")
        product_handling = st.text_input("Product Handling", key="staff_product")
        mobile = st.text_input("Mobile", key="staff_mobile")
        collection_amount = st.number_input("Collection Amount", key="staff_collection", min_value=0)
        remarks = st.text_area("Remarks", key="staff_remarks")

        if st.button("Punch In Visit", key="staff_punchin"):
            lat, lon = get_current_location()
            row = {
                "Username": username,
                "Date": today_str,
                "ClockInTime": today_df.iloc[-1]["ClockInTime"] if not today_df.empty else "",
                "PunchInTime": datetime.now().strftime("%H:%M:%S"),
                "ClockOutTime": "",
                "Latitude": lat,
                "Longitude": lon,
                "DistanceKm": 0,
                "CustomerName": cust_name,
                "ProductHandling": product_handling,
                "Mobile": mobile,
                "CollectionAmount": collection_amount,
                "Remarks": remarks,
                "RecordType": "PunchIn"
            }
            append_visit(row)
            send_location_to_api(username, lat, lon, "PunchIn")
            st.success("✅ Punch In Recorded")
            # Reset input fields
            for k in ["staff_cust_name", "staff_product", "staff_mobile", "staff_collection", "staff_remarks"]:
                if k in st.session_state:
                    del st.session_state[k]
            today_df = get_today_user_df(username)  # refresh

        # ---------------- CLOCK OUT ----------------
        if st.button("Clock Out", key="staff_clockout"):
            if today_df.empty or today_df.iloc[-1]["ClockOutTime"]:
                st.warning("⏰ Already Clocked Out today")
            else:
                lat, lon = get_current_location()
                row = {
                    "Username": username,
                    "Date": today_str,
                    "ClockInTime": today_df.iloc[-1]["ClockInTime"] if not today_df.empty else "",
                    "PunchInTime": today_df.iloc[-1]["PunchInTime"] if not today_df.empty else "",
                    "ClockOutTime": datetime.now().strftime("%H:%M:%S"),
                    "Latitude": lat,
                    "Longitude": lon,
                    "DistanceKm": 0,
                    "CustomerName": "",
                    "ProductHandling": "",
                    "Mobile": "",
                    "CollectionAmount": 0,
                    "Remarks": "",
                    "RecordType": "ClockOut"
                }
                append_visit(row)
                send_location_to_api(username, lat, lon, "ClockOut")
                st.success("✅ Clocked Out Successfully")
                today_df = get_today_user_df(username)  # refresh

        # ---------------- TODAY'S TRAVEL MAP ----------------
        st.subheader("🗺️ Today's Travel Map")
        today_map_df = get_today_user_df(username).dropna(subset=["Latitude","Longitude"])
        if not today_map_df.empty:
            lat_mean = today_map_df["Latitude"].mean()
            lon_mean = today_map_df["Longitude"].mean()
            m = folium.Map(location=[lat_mean, lon_mean], zoom_start=12)

            coords = list(zip(today_map_df["Latitude"], today_map_df["Longitude"]))
            for _, row in today_map_df.iterrows():
                popup_txt = []
                if "CustomerName" in row and row["CustomerName"]:
                    popup_txt.append(str(row["CustomerName"]))
                folium.CircleMarker(
                    location=[row["Latitude"], row["Longitude"]],
                    radius=5, color="blue", fill=True, fill_color="blue",
                    popup="<br>".join(popup_txt)
                ).add_to(m)

            if len(coords) > 1:
                folium.PolyLine(coords, color="red", weight=3, opacity=0.7).add_to(m)

            st_folium(m, width=700, height=500)
        else:
            st.warning("⚠️ No location data for today yet")