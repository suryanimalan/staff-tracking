import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from datetime import datetime
import random
import math

# -------------------- Haversine Formula -------------------- #
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

# -------------------- Dummy Data -------------------- #
branches = ["Chennai", "Coimbatore", "Madurai"]
dms = {"Chennai": "Arun", "Coimbatore": "Bala", "Madurai": "Karthik"}
staff_names = ["Ravi", "Priya", "Kumar", "Meena", "Suresh"]
products = ["Laptop", "Mobile", "TV", "AC", "Washing Machine"]
brands = ["Samsung", "LG", "Sony", "Whirlpool", "Dell"]

random.seed(42)
data = []
for i in range(50):
    branch = random.choice(branches)
    dm = dms[branch]
    staff = random.choice(staff_names)
    lat = random.uniform(8.0, 13.0)
    lon = random.uniform(77.0, 80.5)
    timestamp = datetime(2025, 8, 6, random.randint(8, 18), random.randint(0, 59))
    customer_name = f"Customer {i+1}"
    product = random.choice(products)
    brand = random.choice(brands)
    data.append([branch, dm, staff, lat, lon, timestamp, customer_name, product, brand])

df = pd.DataFrame(data, columns=[
    "Branch", "DM Name", "Staff Name", "Latitude", "Longitude", "Timestamp",
    "Customer Name", "Product", "Brand"
])

# -------------------- Streamlit UI -------------------- #
st.set_page_config(page_title="Staff Location Tracker", layout="wide")
st.title("📍 Staff Live & Travel Location Tracker")

# Filters
col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
with col1:
    branch_filter = st.selectbox("Select Branch", ["All"] + branches)
with col2:
    dm_filter = st.selectbox("Select DM Name", ["All"] + sorted(df["DM Name"].unique()))
with col3:
    staff_filter = st.selectbox("Select Staff Name", ["All"] + sorted(df["Staff Name"].unique()))
with col4:
    product_filter = st.selectbox("Select Product", ["All"] + sorted(df["Product"].unique()))
with col5:
    brand_filter = st.selectbox("Select Brand", ["All"] + sorted(df["Brand"].unique()))
with col6:
    from_date = st.date_input("From Date", datetime(2025, 8, 6).date())
with col7:
    to_date = st.date_input("To Date", datetime(2025, 8, 6).date())

# Apply filters
filtered_df = df.copy()
if branch_filter != "All":
    filtered_df = filtered_df[filtered_df["Branch"] == branch_filter]
if dm_filter != "All":
    filtered_df = filtered_df[filtered_df["DM Name"] == dm_filter]
if staff_filter != "All":
    filtered_df = filtered_df[filtered_df["Staff Name"] == staff_filter]
if product_filter != "All":
    filtered_df = filtered_df[filtered_df["Product"] == product_filter]
if brand_filter != "All":
    filtered_df = filtered_df[filtered_df["Brand"] == brand_filter]

filtered_df = filtered_df[
    (filtered_df["Timestamp"].dt.date >= from_date) &
    (filtered_df["Timestamp"].dt.date <= to_date)
]

# -------------------- Calculate Distance & Time -------------------- #
filtered_df = filtered_df.sort_values(by=["Staff Name", "Timestamp"])
filtered_df["Distance from Prev (km)"] = 0.0
filtered_df["Time Spent at Prev (mins)"] = None

for staff in filtered_df["Staff Name"].unique():
    staff_data = filtered_df[filtered_df["Staff Name"] == staff]
    prev_lat, prev_lon, prev_time = None, None, None
    for idx, row in staff_data.iterrows():
        if prev_lat is not None:
            dist = haversine(prev_lat, prev_lon, row["Latitude"], row["Longitude"])
            time_diff = (row["Timestamp"] - prev_time).total_seconds() / 60
            filtered_df.loc[idx, "Distance from Prev (km)"] = round(dist, 2)
            filtered_df.loc[idx, "Time Spent at Prev (mins)"] = round(time_diff, 1)
        prev_lat, prev_lon, prev_time = row["Latitude"], row["Longitude"], row["Timestamp"]

# -------------------- Map Display -------------------- #
m = folium.Map(location=[10.5, 78.5], zoom_start=6)
marker_cluster = MarkerCluster().add_to(m)

for staff in filtered_df["Staff Name"].unique():
    staff_data = filtered_df[filtered_df["Staff Name"] == staff]
    points = list(zip(staff_data["Latitude"], staff_data["Longitude"]))
    if len(points) > 1:
        folium.PolyLine(points, color="red", weight=3, opacity=0.7, tooltip=f"Route: {staff}").add_to(m)
    for _, row in staff_data.iterrows():
        popup_text = f"""
        <b>Branch:</b> {row['Branch']}<br>
        <b>DM:</b> {row['DM Name']}<br>
        <b>Staff:</b> {row['Staff Name']}<br>
        <b>Customer:</b> {row['Customer Name']}<br>
        <b>Product:</b> {row['Product']}<br>
        <b>Brand:</b> {row['Brand']}<br>
        <b>Time:</b> {row['Timestamp'].strftime('%Y-%m-%d %H:%M')}<br>
        <b>Distance from Prev:</b> {row['Distance from Prev (km)']} km<br>
        <b>Time Spent at Prev:</b> {row['Time Spent at Prev (mins)']} mins
        """
        folium.Marker(
            location=[row["Latitude"], row["Longitude"]],
            popup=popup_text,
            icon=folium.Icon(color="blue", icon="user")
        ).add_to(marker_cluster)

# Show map
st.subheader("🗺️ Map View with Travel Path")
st_folium(m, width=1000, height=500)

# -------------------- Table Display -------------------- #
st.subheader("📋 Full Filtered Travel Data")
st.dataframe(filtered_df, use_container_width=True)
