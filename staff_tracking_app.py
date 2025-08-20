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

# Try geolocation package (real GPS). If missing, fallback to manual input.
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

# Fallback random location (used only if GEO not available and user doesn’t enter coords)
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

    role = st.selectbox("Role", ["staff", "admin"])  # ✅ added role

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

# ==================== DASHBOARD (LOGGED IN) ==================== #
# ==================== ADMIN DASHBOARD ==================== #
elif st.session_state.logged_in and st.session_state.user["role"] == "admin":
    st.title("📊 Admin Dashboard")

    df = load_visits()
    if df.empty:
        st.info("No staff activity logged yet.")
    else:
        # Filters
        st.subheader("🔍 Filters")
        col1, col2, col3 = st.columns(3)
        with col1:
            user_filter = st.selectbox("Filter by User", ["All"] + sorted(df["Username"].unique().tolist()))
        with col2:
            date_filter = st.date_input("Filter by Date", value=date.today())
        with col3:
            record_filter = st.multiselect("Record Types", ["Clock In","Punch In","Clock Out"], default=["Punch In","Clock In","Clock Out"])

        df_view = df.copy()
        if user_filter != "All":
            df_view = df_view[df_view["Username"] == user_filter]
        if date_filter:
            df_view = df_view[df_view["Date"] == date_filter.isoformat()]
        if record_filter:
            df_view = df_view[df_view["RecordType"].isin(record_filter)]

        # Metrics
        st.subheader("📈 Metrics")
        total_km = round(df_view["DistanceKm"].astype(float).sum(), 2)
        total_visits = df_view[df_view["RecordType"] == "Punch In"].shape[0]
        total_collection = round(df_view["CollectionAmount"].astype(float).sum(), 2)
        c1, c2, c3 = st.columns(3)
        c1.metric("🚗 Total Distance (km)", total_km)
        c2.metric("👥 Visits", total_visits)
        c3.metric("💰 Collection", f"₹{total_collection}")

        # Data table
        st.subheader("📋 Records")
        st.dataframe(df_view, use_container_width=True)

        # Map
        if not df_view.empty:
            st.subheader("🗺️ Map View")
            try:
                lat_mean = df_view["Latitude"].astype(float).mean()
                lon_mean = df_view["Longitude"].astype(float).mean()
            except Exception:
                lat_mean, lon_mean = 12.9716, 77.5946

            m = folium.Map(location=[lat_mean, lon_mean], zoom_start=6)
            marker_cluster = MarkerCluster().add_to(m)

            for _, r in df_view.iterrows():
                popup = f"""
                <b>{r['Username']}</b><br>
                {r['RecordType']} at {r['ClockInTime'] or r['PunchInTime'] or r['ClockOutTime']}<br>
                Customer: {r['CustomerName'] or '-'}<br>
                Collection: ₹{r['CollectionAmount']}
                """
                folium.Marker(
                    location=[float(r["Latitude"]), float(r["Longitude"])],
                    popup=popup,
                    icon=folium.Icon(color="green" if r["RecordType"]=="Punch In" else "red")
                ).add_to(marker_cluster)

            st_folium(m, width=1000, height=520)

elif st.session_state.logged_in:
    user = st.session_state.user
    st.title(f"👋 Welcome {user['name']} — {user['branch']} — Role: {user['role']}")

    # (🚨 keep rest of your script exactly the same as before)
    # I didn’t change anything in Punch/ClockIn/ClockOut/Map/Visits logic
    # ⬆️ Just added role handling


    # ---------- GPS CAPTURE UI ---------- #
    st.caption("📍 Location capture will use your phone's GPS. If prompted, please allow location access.")

    def capture_location_ui():
        """Return (lat, lon, used_real_gps:bool)"""
        if GEO_AVAILABLE:
            loc = geolocation(key="geo_key")  # triggers browser location prompt
            if loc and "latitude" in loc and "longitude" in loc and loc["latitude"] and loc["longitude"]:
                return float(loc["latitude"]), float(loc["longitude"]), True
            else:
                st.info("Waiting for location... If it doesn't appear, you can use manual input below.")
        # Manual fallback
        with st.expander("Manual location (fallback)", expanded=not GEO_AVAILABLE):
            lat = st.number_input("Latitude", value=12.9716, format="%.6f")
            lon = st.number_input("Longitude", value=77.5946, format="%.6f")
            st.caption("Tip: Use Google Maps to copy your current coordinates if GPS is blocked.")
            return float(lat), float(lon), False

    # ---------- ACTIONS: CLOCK IN / PUNCH IN / CLOCK OUT ---------- #
    today_str = date.today().isoformat()
    df_today = get_today_user_df(user["username"])

    # --- CLOCK IN ---
    if df_today[df_today["RecordType"] == "Clock In"].empty:
        st.subheader("🟢 Clock In")
        lat, lon, gps_ok = capture_location_ui()
        if st.button("Clock In (Start Day)"):
            row = {
                "Username": user["username"],
                "Date": today_str,
                "ClockInTime": datetime.now().strftime("%H:%M:%S"),
                "PunchInTime": "",
                "ClockOutTime": "",
                "Latitude": lat,
                "Longitude": lon,
                "DistanceKm": 0.0,
                "CustomerName": "",
                "ProductHandling": "",
                "Mobile": "",
                "CollectionAmount": 0.0,
                "Remarks": "Day Started",
                "RecordType": "Clock In"
            }
            append_visit(row)
            st.success("✅ Clock In recorded!")
            st.rerun()

    else:
        # --- PUNCH IN (CUSTOMER VISIT) ---
        st.subheader("🔵 Punch In — Customer Visit")
        with st.form("punch_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                cust_name = st.text_input("Customer Name", key="cust_name")
                product_handling = st.text_input("Product Handling", value=user["product"], key="product_handling")
                mobile = st.text_input("Mobile", key="mobile")
            with c2:
                collection_amount = st.number_input("Collection Amount", min_value=0.0, step=100.0, key="collection_amount")
                remarks = st.text_input("Remarks", key="remarks")

            st.markdown("**Location Capture**")
            lat, lon, gps_ok = capture_location_ui()

            submitted = st.form_submit_button("Save Punch")
            if submitted:
                # distance from last punch/clock-in
                last_loc = get_last_location_for_today(user["username"])
                if last_loc:
                    dist = haversine(last_loc[0], last_loc[1], lat, lon)
                else:
                    dist = 0.0

                row = {
                    "Username": user["username"],
                    "Date": today_str,
                    "ClockInTime": "",
                    "PunchInTime": datetime.now().strftime("%H:%M:%S"),
                    "ClockOutTime": "",
                    "Latitude": lat,
                    "Longitude": lon,
                    "DistanceKm": round(dist, 2),
                    "CustomerName": cust_name,
                    "ProductHandling": product_handling,
                    "Mobile": mobile,
                    "CollectionAmount": float(collection_amount or 0.0),
                    "Remarks": remarks,
                    "RecordType": "Punch In"
                }
                append_visit(row)
                reset_punch_form_state()
                st.success("✅ Punch saved!")
                st.rerun()

        # --- CLOCK OUT ---
        st.subheader("🔴 Clock Out")
        lat_co, lon_co, gps_ok_co = capture_location_ui()
        if st.button("Clock Out (End Day)"):
            last_loc = get_last_location_for_today(user["username"])
            dist = haversine(last_loc[0], last_loc[1], lat_co, lon_co) if last_loc else 0.0

            # totals for the day
            df_today = get_today_user_df(user["username"])
            total_km = round(df_today["DistanceKm"].astype(float).sum() + dist, 2)
            total_visits = df_today[df_today["RecordType"] == "Punch In"].shape[0]
            total_collection = round(df_today["CollectionAmount"].astype(float).sum(), 2)

            row = {
                "Username": user["username"],
                "Date": today_str,
                "ClockInTime": "",
                "PunchInTime": "",
                "ClockOutTime": datetime.now().strftime("%H:%M:%S"),
                "Latitude": lat_co,
                "Longitude": lon_co,
                "DistanceKm": round(dist, 2),
                "CustomerName": "",
                "ProductHandling": "",
                "Mobile": "",
                "CollectionAmount": 0.0,
                "Remarks": f"Day Ended | TotalKM={total_km} | Visits={total_visits} | Collection={total_collection}",
                "RecordType": "Clock Out"
            }
            append_visit(row)
            st.success(f"✅ Clock Out recorded! Total KM: {total_km} | Visits: {total_visits} | Collection: ₹{total_collection}")
            st.rerun()

    # ---------- TODAY VIEW (MAP + TABLE + METRICS) ---------- #
    df_today = get_today_user_df(user["username"])
    if not df_today.empty:
        # Metrics
        total_km_today = round(df_today["DistanceKm"].astype(float).sum(), 2)
        total_visits_today = df_today[df_today["RecordType"] == "Punch In"].shape[0]
        total_collection_today = round(df_today["CollectionAmount"].astype(float).sum(), 2)
        c1, c2, c3 = st.columns(3)
        c1.metric("🚗 Total Distance (km)", total_km_today)
        c2.metric("👥 Customers Visited", total_visits_today)
        c3.metric("💰 Total Collection", f"₹{total_collection_today}")

        st.subheader("📋 Today's Log")
        st.dataframe(df_today, use_container_width=True)

        # Map
        st.subheader("🗺️ Route Map")
        try:
            lat_mean = df_today["Latitude"].astype(float).mean()
            lon_mean = df_today["Longitude"].astype(float).mean()
        except Exception:
            lat_mean, lon_mean = 12.9716, 77.5946

        m = folium.Map(location=[lat_mean, lon_mean], zoom_start=7)
        marker_cluster = MarkerCluster().add_to(m)

        # Build ordered path
        def row_time_key(r):
            # build sortable time from available fields
            t = ""
            if r["RecordType"] == "Clock In":
                t = r["ClockInTime"]
            elif r["RecordType"] == "Punch In":
                t = r["PunchInTime"]
            elif r["RecordType"] == "Clock Out":
                t = r["ClockOutTime"]
            return t

        df_plot = df_today.copy()
        df_plot["sort_time"] = df_plot.apply(row_time_key, axis=1)
        df_plot = df_plot.sort_values(by="sort_time")

        points = list(zip(df_plot["Latitude"].astype(float), df_plot["Longitude"].astype(float)))
        if len(points) > 1:
            folium.PolyLine(points, color="red", weight=3, opacity=0.7,
                            tooltip=f"Route of {user['name']}").add_to(m)

        for _, r in df_plot.iterrows():
            label = r["RecordType"]
            when = r["ClockInTime"] or r["PunchInTime"] or r["ClockOutTime"]
            popup = f"""
            <b>{label}</b><br>
            <b>Time:</b> {when}<br>
            <b>Customer:</b> {r['CustomerName'] or '-'}<br>
            <b>Product:</b> {r['ProductHandling'] or '-'}<br>
            <b>Mobile:</b> {r['Mobile'] or '-'}<br>
            <b>Collection:</b> ₹{r['CollectionAmount']}<br>
            <b>Distance:</b> {r['DistanceKm']} km<br>
            <b>Remarks:</b> {r['Remarks'] or '-'}
            """
            folium.Marker(
                location=[float(r["Latitude"]), float(r["Longitude"])],
                popup=popup,
                icon=folium.Icon(color="blue", icon="user")
            ).add_to(marker_cluster)

        st_folium(m, width=1000, height=520)

# ==================== LOGOUT ==================== #
elif menu == "Logout":
    st.session_state.logged_in = False
    st.session_state.user = None
    st.success("✅ You have been logged out.")
