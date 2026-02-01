import streamlit as st
import ee
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw
from google.oauth2 import service_account
import pandas as pd
from datetime import datetime, timedelta

# --- Page Config ---
st.set_page_config(layout="wide", page_title="GEE Auto-Clip & Coordinates")
st.title("🛰️ GEE Polygon Clipper & Coordinate Table")

# --- EE Initialization ---
def initialize_ee():
    if "ee_initialized" not in st.session_state:
        try:
            info = dict(st.secrets["GCP_SERVICE_ACCOUNT_JSON"])
            creds = service_account.Credentials.from_service_account_info(
                info, scopes=['https://www.googleapis.com/auth/earthengine.readonly']
            )
            ee.Initialize(creds)
            st.session_state.ee_initialized = True
            return True
        except Exception as e:
            st.error(f"Init Error: {e}")
            return False
    return True

if initialize_ee():
    # --- Sidebar ---
    with st.sidebar:
        st.header("1. Map Settings")
        satellite = st.selectbox("Satellite Source", ["Sentinel-2", "Landsat-8"])
        start_date = st.date_input("Start Date", datetime.now() - timedelta(days=180))
        end_date = st.date_input("End Date", datetime.now())
        st.divider()
        st.info("Step 1: Draw a polygon on the map.\nStep 2: See the clipped image and the Latitude/Longitude list below.")

    # --- Main Drawing Map ---
    m = folium.Map(location=[22.0, 68.5], zoom_start=6)
    Draw(export=False, position='topleft').add_to(m)
    
    st.subheader("Draw Area of Interest")
    map_output = st_folium(m, width=1300, height=500, key="input_map")

    # --- Results Logic ---
    if map_output and map_output.get("last_active_drawing"):
        st.divider()
        
        # 1. Extract Geometry
        roi_data = map_output["last_active_drawing"]["geometry"]
        roi = ee.Geometry(roi_data)
        coords = roi_data["coordinates"]

        # 2. Display Lat/Lon Table
        st.subheader("📍 Polygon Coordinates")
        
        # Flattening the nested lists for the table
        # Polygons are usually [[[lon, lat], [lon, lat]...]]
        raw_points = coords[0] if roi_data["type"] == "Polygon" else coords[0][0]
        
        # Create DataFrame: Note GEE/GeoJSON is [Lon, Lat], so we swap for the table
        df = pd.DataFrame(raw_points, columns=["Longitude", "Latitude"])
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.write("**Point List**")
            st.dataframe(df, use_container_width=True)
            
            # Calculate Center
            center_lat = df["Latitude"].mean()
            center_lon = df["Longitude"].mean()
            st.metric("Center Latitude", f"{center_lat:.6f}")
            st.metric("Center Longitude", f"{center_lon:.6f}")

        with col2:
            st.write("**Clipped Satellite View**")
            
            # Process GEE Image
            if satellite == "Sentinel-2":
                col_id, vis = "COPERNICUS/S2_SR_HARMONIZED", {"bands": ["B4", "B3", "B2"], "min": 0, "max": 3000}
            else:
                col_id, vis = "LANDSAT/LC08/C02/T1_L2", {"bands": ["SR_B4", "SR_B3", "SR_B2"], "min": 0, "max": 30000}

            img = ee.ImageCollection(col_id)\
                    .filterBounds(roi)\
                    .filterDate(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))\
                    .median().clip(roi)

            map_id = ee.Image(img).getMapId(vis)
            
            # Result Map
            res_map = folium.Map(location=[center_lat, center_lon], zoom_start=
