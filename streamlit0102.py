import streamlit as st
import ee
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw
from google.oauth2 import service_account
import pandas as pd
from datetime import datetime, timedelta

# --- Page Config ---
st.set_page_config(layout="wide", page_title="GEE Auto-Clip Tool")
st.title("🖼️ GEE Live Polygon Clipper")

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
    # 1. Sidebar Setup
    with st.sidebar:
        st.header("Settings")
        satellite = st.selectbox("Satellite", ["Sentinel-2", "Landsat-8"])
        start_date = st.date_input("Start Date", datetime.now() - timedelta(days=180))
        end_date = st.date_input("End Date", datetime.now())
        st.write("---")
        st.info("💡 Draw a polygon on the map. The satellite imagery will automatically clip to your shape.")

    # 2. Initialize Map
    m = folium.Map(location=[22.0, 68.5], zoom_start=6, tiles="OpenStreetMap")
    
    # 3. Add Drawing Tools
    draw_tool = Draw(export=False, position='topleft')
    draw_tool.add_to(m)

    # 4. Handle Drawing Logic
    # We use a key to track the map state
    map_output = st_folium(m, width=1200, height=600, key="map_clipper")

    # 5. Check if a polygon was drawn
    if map_output and map_output.get("last_active_drawing"):
        roi_data = map_output["last_active_drawing"]["geometry"]
        roi = ee.Geometry(roi_data)
        
        # Center map on the polygon
        # (Note: st_folium might reset view, so we just process the image)
        
        # Select Dataset
        if satellite == "Sentinel-2":
            col_id = "COPERNICUS/S2_SR_HARMONIZED"
            vis = {"bands": ["B4", "B3", "B2"], "min": 0, "max": 3000}
        else:
            col_id = "LANDSAT/LC08/C02/T1_L2"
            vis = {"bands": ["SR_B4", "SR_B3", "SR_B2"], "min": 0, "max": 30000}

        # Fetch and Clip Image
        img = ee.ImageCollection(col_id)\
                .filterBounds(roi)\
                .filterDate(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))\
                .median()\
                .clip(roi) # <--- This is the magic part

        # Generate Map ID for Leaflet
        map_id_dict = ee.Image(img).getMapId(vis)
        
        # We need to re-render or add the layer. 
        # Since st_folium is reactive, we can display the results below or
        # trigger a notification that the image is processed.
        
        st.success(f"Successfully clipped {satellite} imagery to your polygon!")
        
        # Displaying the "Result" Map
        st.subheader("Clipped Satellite Result")
        res_map = folium.Map(location=[22.0, 68.5], zoom_start=10)
        
        # Add the clipped layer
        folium.TileLayer(
            tiles=map_id_dict['tile_fetcher'].url_format,
            attr='Google Earth Engine',
            name='Clipped Image',
            overlay=False
        ).add_to(res_map)
        
        # Zoom to the drawn area
        res_map.fit_bounds(roi.bounds().getInfo()['coordinates'][0])
        st_folium(res_map, width=1200, height=500, key="result_map")

    else:
        st.info("Waiting for you to draw a polygon on the main map above...")
