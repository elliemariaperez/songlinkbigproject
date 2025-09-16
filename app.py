import streamlit as st 
import pandas as pd
import requests
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from io import StringIO
import urllib.parse
import time
import os
from Levenshtein import ratio  # For fuzzy matching

# === Credentials from Streamlit input ===
SPOTIFY_CLIENT_ID = st.secrets.get("SPOTIFY_CLIENT_ID") or os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = st.secrets.get("SPOTIFY_CLIENT_SECRET") or os.getenv("SPOTIFY_CLIENT_SECRET")

if not all([SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET]):
    st.error("girl you lost your keys! Make sure Spotify tokens are provided.")
    st.stop()

# === Cached Spotify client ===
@st.cache_resource
def get_spotify_client():
    return spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET))

spotify = get_spotify_client()

# === Search functions ===
def search_spotify(title, artist):
    query = f'track:{title} artist:{artist}'
    try:
        result = spotify.search(q=query, type='track', limit=1)
        tracks = result.get('tracks', {}).get('items', [])
        if tracks:
            return tracks[0]['external_urls']['spotify']
    except Exception as e:
        st.warning(f"Spotify API error: {e}")
    return None

def search_itunes(title, artist):
    term = urllib.parse.quote(f"{title} {artist}")
    url = f"https://itunes.apple.com/search?term={term}&limit=1&entity=song"
    try:
        r = requests.get(url, timeout=5)
        
        if r.status_code != 200:
            st.warning(f"iTunes API returned status code {r.status_code} for '{title} - {artist}'")
            return None
        
        if not r.text.strip():
            st.warning(f"iTunes API returned an empty response for '{title} - {artist}'")
            return None

        data = r.json()
        if data.get('resultCount', 0) > 0:
            return data['results'][0].get('trackViewUrl')
        else:
            st.info(f"No iTunes result found for '{title} - {artist}'")
    except requests.exceptions.RequestException as e:
        st.warning(f"iTunes API request error: {e}")
    except ValueError as e:
        st.warning(f"iTunes API returned invalid JSON for '{title} - {artist}': {e}")
    return None

# === Streamlit App ===
st.title("🎵 ellie's song link finder!!!")

uploaded_file = st.file_uploader("upload a CSV file with 'title' and 'artist' columns, soooo sorry if it doesn't work, this is just phase 1 and I'm not a developer :D also you should probably include a column for unique ID but not required", type="csv")

if uploaded_file:
    try:
        # Try reading as UTF-8
        df = pd.read_csv(uploaded_file)
    except UnicodeDecodeError:
        # Retry with fallback encoding
        uploaded_file.seek(0)  # Reset file pointer
        try:
            df = pd.read_csv(uploaded_file, encoding='latin1')
            st.info("FYI: Your file wasn’t UTF-8, so we read it using Latin-1 encoding instead.")
        except Exception as e:
            st.error(f"Could not read the file due to encoding issues: {e}")
            st.stop()

    if 'title' not in df.columns or 'artist' not in df.columns:
        st.error("CSV must contain 'title' and 'artist' columns")
    else:
        if 'link' not in df.columns:
            df['link'] = ""
        if 'source' not in df.columns:
            df['source'] = ""

        if st.button("Find Links"):
            my_bar = st.progress(0)
            total = len(df)

            for i, row in df.iterrows():
                if row['link']:
                    my_bar.progress((i+1)/total)
                    continue

                title = row['title']
                artist = row['artist']

                link = search_spotify(title, artist)
                source = "Spotify"

                if not link:
                    link = search_itunes(title, artist)
                    source = "iTunes"

                df.at[i, 'link'] = link if link else ""
                df.at[i, 'source'] = source if link else "Not Found"

                my_bar.progress((i+1)/total)

                time.sleep(0.2)  # Be nice to the APIs

            st.success("all set diva!")

        st.write("### Results Preview")
        st.dataframe(df.head(20))

        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)
        st.download_button(label="Download CSV with links", data=csv_buffer.getvalue(), file_name="songs_with_links.csv", mime="text/csv")


