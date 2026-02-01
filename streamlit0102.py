import streamlit as st
import ee
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw
from google.oauth2 import service_account
import pandas as pd
from datetime import datetime, timedelta

# --- Page Config ---
st.set_page_config(layout="wide", page_title="GEE Polygon Tool")
st.title("🗺️ GEE Image & Coordinate Extractor")

# --- EE Initialization ---
def initialize_ee():
    try:
        if "GCP_SERVICE_ACCOUNT_JSON" not in st.secrets:
            st.error("Secrets not found in .streamlit/secrets.toml")
            return False
        info = dict(st.secrets["GCP_SERVICE_ACCOUNT_JSON"])
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=['https://www.googleapis.com/auth/earthengine.readonly']
        )
        ee.Initialize(creds)
        return True
    except Exception as e:
        st.error(f"Init Error: {e}")
        return False

# --- Sidebar UI ---
with st.sidebar:
    st.header("1. Configure Image")
    satellite = st.selectbox("Satellite", ["Sentinel-2", "Landsat-8"])
    
    # Date Selection
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", datetime.now() - timedelta(days=365))
    with col2:
        end_date = st.date_input("End Date", datetime.now())
    
    # Visualization Options
    viz_mode = st.radio("Visualization", ["Natural Color", "False Color (Infrared)"])
    
    run_basemap = st.button("🗺️ Load Satellite Imagery")
    st.info("Tip: Draw a polygon after the imagery loads to get coordinates.")

# --- Main Logic ---
if initialize_ee():
    center_lat, center_lon = 22.0, 68.5
    m = folium.Map(location=[center_lat, center_lon], zoom_start=8)
    
    if run_basemap:
        # 1. Define ROI & Collection
        default_roi = ee.Geometry.Point([center_lon, center_lat]).buffer(100000).bounds()
        
        if satellite == "Sentinel-2":
            col_id = "COPERNICUS/S2_SR_HARMONIZED"
            # Natural: B4,B3,B2 | False Color: B8,B4,B3
            viz_bands = ["B4", "B3", "B2"] if viz_mode == "Natural Color" else ["B8", "B4", "B3"]
        else:
            col_id = "LANDSAT/LC08/C02/T1_L2"
            # Natural: B4,B3,B2 | False Color: B5,B4,B3
            viz_bands = ["B4", "B3", "B2"] if viz_mode == "Natural Color" else ["B5", "B4", "B3"]

        # 2. Filter & Process Image
        img_col = ee.ImageCollection(col_id)\
                    .filterBounds(default_roi)\
                    .filterDate(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))\
                    .sort('CLOUDY_PIXEL_PERCENTAGE' if satellite == "Sentinel-2" else 'CLOUD_COVER')

        if img_col.size().getInfo() > 0:
            img = img_col.median() # Use median to clear out some clouds
            
            vis_params = {
                "bands": viz_bands,
                "min": 0,
                "max": 3000,
                "gamma": 1.4
            }
            
            map_id_dict = ee.Image(img).getMapId(vis_params)
            folium.TileLayer(
                tiles=map_id_dict['tile_fetcher'].url_format,
                attr='Google Earth Engine',
                name=f'{satellite} {viz_mode}',
                overlay=True,
                control=True
            ).add_to(m)
        else:
            st.warning("No images found for this date range/location.")

    # 3. Drawing Tools
    Draw(export=False, position='topleft').add_to(m)
    folium.LayerControl().add_to(m)

    # 4. Render Map
    map_output = st_folium(m, width=1200, height=600, key="drawing_map")

    # 5. Coordinate Processing
    st.divider()
    if map_output and map_output.get("last_active_drawing"):
        drawing_data = map_output["last_active_drawing"]
        geom_type = drawing_data["geometry"]["type"]
        coords = drawing_data["geometry"]["coordinates"]

        st.subheader(f"📍 {geom_type} Details")
        
        col_res1, col_res2 = st.columns([1, 2])
        with col_res1:
            if geom_type in ['Polygon', 'MultiPolygon']:
                df = pd.DataFrame(coords[0], columns=["Longitude", "Latitude"])
                st.write("**Polygon Points:**")
                st.dataframe(df, height=200)
        
        with col_res2:
            st.write("**GEE Geometry Snippet:**")
            st.code(f"roi = ee.Geometry.{geom_type}({coords})", language="python")
            
            # Metadata display
            st.write("**Session Metadata:**")
            st.json({
                "Satellite": satellite,
                "Date Range": f"{start_date} to {end_date}",
                "Viz Mode": viz_mode
            })
    else:
        st.info("Drawing a shape on the map will generate GEE-ready code here.")
