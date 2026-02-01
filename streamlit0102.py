import streamlit as st
import ee
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw
from google.oauth2 import service_account
from datetime import date
import pandas as pd

# --- Page Config ---
st.set_page_config(layout="wide", page_title="GEE Polygon Tool")
st.title("🗺️ GEE Polygon Coordinate Extractor")

# --- EE Initialization ---
def initialize_ee():
    try:
        if "GCP_SERVICE_ACCOUNT_JSON" not in st.secrets:
            st.error("Secrets not found!")
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
    st.header("1. Setup Background")
    satellite = st.selectbox("Basemap Satellite", ["Sentinel-2", "Landsat-8"])
    run_basemap = st.button("🗺️ Load Map Area")
    st.info("After map loads, use the tools on the left of the map to draw a polygon.")

# --- Main Logic ---
if initialize_ee():
    # Define a default center if no ROI is provided
    center_lat, center_lon = 22.0, 68.5
    
    # Create the Folium Map
    m = folium.Map(location=[center_lat, center_lon], zoom_start=8)
    
    # Add GEE Layer if requested
    if run_basemap:
        # Simple default ROI to show background tiles
        default_roi = ee.Geometry.Point([center_lon, center_lat]).buffer(50000).bounds()
        col_id = "COPERNICUS/S2_SR_HARMONIZED" if satellite == "Sentinel-2" else "LANDSAT/LC08/C02/T1_L2"
        
        img = ee.ImageCollection(col_id)\
                .filterBounds(default_roi)\
                .filterDate('2024-01-01', '2024-12-31')\
                .median()
        
        vis = {"bands": ["B4", "B3", "B2"], "min": 0, "max": 3000, "gamma": 1.4}
        map_id_dict = ee.Image(img).getMapId(vis)
        
        folium.TileLayer(
            tiles=map_id_dict['tile_fetcher'].url_format,
            attr='Google Earth Engine',
            name='Satellite',
            overlay=True,
            control=True
        ).add_to(m)

    # 2. Add Drawing Tool
    draw_tool = Draw(
        export=False,
        position='topleft',
        draw_options={
            'polyline': False,
            'rectangle': True,
            'polygon': True,
            'circle': False,
            'marker': False,
            'circlemarker': False,
        }
    )
    draw_tool.add_to(m)

    # 3. Render Map and Capture Interaction
    # This is the "Magic" part that gets coordinates back
    map_output = st_folium(m, width=1200, height=600, key="drawing_map")

    # 4. Display Results
    st.divider()
    if map_output and map_output.get("last_active_drawing"):
        drawing_data = map_output["last_active_drawing"]
        geom_type = drawing_data["geometry"]["type"]
        coordinates = drawing_data["geometry"]["coordinates"]

        st.subheader(f"📍 Drawn {geom_type} Coordinates")
        
        # Polygons are nested lists: [[[lon, lat], ...]]
        if geom_type in ['Polygon', 'MultiPolygon']:
            # Extract the first ring of the polygon
            flat_list = coordinates[0]
            df = pd.DataFrame(flat_list, columns=["Longitude", "Latitude"])
            
            col1, col2 = st.columns([1, 2])
            with col1:
                st.write("**Point List:**")
                st.dataframe(df, use_container_width=True)
            with col2:
                st.write("**GEE Ready String:**")
                st.code(f"ee.Geometry.Polygon({coordinates})")
                st.write("**Center Point:**")
                avg_lat = df["Latitude"].mean()
                avg_lon = df["Longitude"].mean()
                st.write(f"Lat: {avg_lat:.6f}, Lon: {avg_lon:.6f}")
    else:
        st.write("👆 **Draw a shape on the map to see coordinates here.**")
