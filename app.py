import streamlit as st
import pandas as pd
import requests
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import discogs_client
from io import StringIO
import urllib.parse
import time
import os

# === Load environment variables ===
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
DISCOGS_USER_TOKEN = os.getenv("DISCOGS_USER_TOKEN")

if not all([SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, DISCOGS_USER_TOKEN]):
    st.error("girl you lost your keys! Please set SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, and DISCOGS_USER_TOKEN environment variables.")
    st.stop()

# === Cached API clients ===
@st.cache_resource
def get_spotify_client():
    return spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET))

@st.cache_resource
def get_discogs_client():
    return discogs_client.Client('song-link-finder/1.0', user_token=DISCOGS_USER_TOKEN)

spotify = get_spotify_client()
discogs = get_discogs_client()

# search functions in spotify, itunes and discogs
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
        r = requests.get(url)
        data = r.json()
        if data['resultCount'] > 0:
            return data['results'][0].get('trackViewUrl')
    except Exception as e:
        st.warning(f"iTunes API error: {e}")
    return None

def search_discogs(title, artist):
    try:
        query = f"{title} {artist}"
        results = discogs.search(query, type='release')
        for r in results.page(1):
            result_title = r.title.lower()
            result_artists = ", ".join([a.name for a in getattr(r, 'artists', [])]).lower()
            
            if title.lower() in result_title and artist.lower() in result_artists:
                return r.data.get('uri')
    except Exception as e:
        st.warning(f"Discogs API error: {e}")
    return None

# creating streamlit app
st.title("🎵 ellie's song link finder!!!")

uploaded_file = st.file_uploader("upload a CSV file with 'title' and 'artist' columns, soooo sorry if it doesn't work, this is just phase 1 and I'm not a developer :D also you should probably include a column for unique ID but not required", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)
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

                if not link:
                    link = search_discogs(title, artist)
                    source = "Discogs"
                    time.sleep(1.1)  # Throttle to avoid Discogs rate limit

                df.at[i, 'link'] = link if link else ""
                df.at[i, 'source'] = source if link else "Not Found"

                my_bar.progress((i+1)/total)

            st.success("all set diva!")

        st.write("### Results Preview")
        st.dataframe(df.head(20))

        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)
        st.download_button(label="Download CSV with links", data=csv_buffer.getvalue(), file_name="songs_with_links.csv", mime="text/csv")
