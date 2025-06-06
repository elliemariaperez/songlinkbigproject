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
from Levenshtein import ratio

# === Load credentials from user input ===
SPOTIFY_CLIENT_ID = st.secrets.get("SPOTIFY_CLIENT_ID") or st.text_input("Spotify Client ID", type="password")
SPOTIFY_CLIENT_SECRET = st.secrets.get("SPOTIFY_CLIENT_SECRET") or st.text_input("Spotify Client Secret", type="password")
DISCOGS_USER_TOKEN = st.secrets.get("DISCOGS_USER_TOKEN") or st.text_input("Discogs User Token", type="password")
GENIUS_ACCESS_TOKEN = st.secrets.get("GENIUS_ACCESS_TOKEN") or st.text_input("Genius Access Token", type="password")

if not all([SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, DISCOGS_USER_TOKEN, GENIUS_ACCESS_TOKEN]):
    st.warning("Please enter all API credentials (Spotify, Discogs, and Genius) to continue.")
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

# === Genius search function ===
def search_genius(title, artist):
    try:
        query = f"{title} {artist}"
        headers = {"Authorization": f"Bearer {GENIUS_ACCESS_TOKEN}"}
        url = f"https://api.genius.com/search?q={urllib.parse.quote(query)}"
        response = requests.get(url, headers=headers)
        data = response.json()
        hits = data.get("response", {}).get("hits", [])

        if hits:
            # Use best fuzzy match
            best_match = None
            best_score = 0
            for hit in hits:
                result_title = hit['result']['title']
                result_artist = hit['result']['primary_artist']['name']
                artist_score = ratio(artist.lower(), result_artist.lower())
                title_score = ratio(title.lower(), result_title.lower())
                avg_score = (artist_score + title_score) / 2
                if avg_score > best_score and avg_score > 0.65:
                    best_score = avg_score
                    best_match = hit

            if best_match:
                return best_match['result']['url']
    except Exception as e:
        st.warning(f"Genius API error: {e}")
    return None

# === Other search functions (unchanged) ===
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
        best_match = None
        best_score = 0

        for r in results.page(1):
            result_title = r.title or ''
            result_artists = ", ".join([a.name for a in getattr(r, 'artists', [])])
            artist_score = ratio(artist.lower(), result_artists.lower())
            title_score = ratio(title.lower(), result_title.lower())
            avg_score = (artist_score + title_score) / 2

            if avg_score > best_score and avg_score > 0.7:
                best_score = avg_score
                best_match = r

        if best_match:
            return best_match.data.get('uri')
    except Exception as e:
        st.warning(f"Discogs API error: {e}")
    return None

# === Streamlit App ===
st.title("🎵 ellie's song link finder!!! (now with genius lyrics too 💅)")

uploaded_file = st.file_uploader("Upload a CSV file with 'title' and 'artist' columns", type="csv")

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
                    time.sleep(1.1)

                if not link:
                    link = search_genius(title, artist)
                    source = "Genius"

                df.at[i, 'link'] = link if link else ""
                df.at[i, 'source'] = source if link else "Not Found"

                my_bar.progress((i+1)/total)

            st.success("All set, diva! ✨")

        st.write("### Results Preview")
        st.dataframe(df.head(20))

        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)
        st.download_button(label="Download CSV with links", data=csv_buffer.getvalue(), file_name="songs_with_links.csv", mime="text/csv")
