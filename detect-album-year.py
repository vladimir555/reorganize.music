#!/usr/bin/env python3
import sys
import musicbrainzngs

musicbrainzngs.set_useragent(
    "MyMusicTool",
    "0.1",
    "https://example.com"  # можно оставить любой URL или email
)

def get_album_year(artist: str, album: str):
    try:
        result = musicbrainzngs.search_releases(
            artist=artist,
            release=album,
            limit=1
        )
        releases = result.get('release-list', [])
        if releases:
            release = releases[0]
            year = release.get('date', '')[:4]  # "1997-05-12" → "1997"
            if year.isdigit():
                return year
    except Exception as e:
        print(f"Ошибка: {e}", file=sys.stderr)
    return None

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Использование: python3 lookup_year.py 'Artist' 'Album'")
        sys.exit(1)

    artist = sys.argv[1]
    album = sys.argv[2]
    year = get_album_year(artist, album)
    if year:
        print(year)
    else:
        print("Год не найден")
