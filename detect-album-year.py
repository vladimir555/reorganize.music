#!/usr/bin/env python3
import sys
import urllib.parse
import urllib.request
import json
import re

def normalize_name(name: str) -> str:
    return re.sub(r'\s+', ' ', name.strip()).lower()

def get_year_from_reccobeats(artist: str, album: str) -> str | None:
    try:
        search_url = f"https://api.reccobeats.com/v1/artist/search?searchText={urllib.parse.quote(artist)}"
        req = urllib.request.Request(search_url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as f:
            data = json.load(f)

        artists = data.get("content", [])
        print(f"🔍 Найдено артистов: {len(artists)}", file=sys.stderr)
        for i, a in enumerate(artists):
            print(f"  {i+1}. ID: {a.get('id')}, Name: '{a.get('name')}'", file=sys.stderr)

        if not artists:
            return None

        query_norm = normalize_name(album)
        print(f"🔍 Ищем альбом: '{album}' → нормализовано как: '{query_norm}'", file=sys.stderr)

        for a in artists:
            artist_id = a.get("id")
            if not artist_id:
                continue

            try:
                albums_url = f"https://api.reccobeats.com/v1/artist/{urllib.parse.quote(artist_id)}/album"
                req_album = urllib.request.Request(albums_url, headers={'Accept': 'application/json'})
                with urllib.request.urlopen(req_album, timeout=10) as f_album:
                    albums_data = json.load(f_album)

                albums = albums_data.get("content", [])
                print(f"📚 У артиста {artist_id} найдено альбомов: {len(albums)}", file=sys.stderr)
                for alb in albums:
                    name = alb.get("name", "")
                    norm = normalize_name(name)
                    print(f"   - '{name}' → '{norm}'", file=sys.stderr)
                    if norm == query_norm:
                        release_date = alb.get("releaseDate", "")
                        if release_date and release_date[:4].isdigit():
                            print(f"✅ Найдено совпадение! Год: {release_date[:4]}", file=sys.stderr)
                            return release_date[:4]
            except Exception as e:
                print(f"⚠️  Пропуск артиста {artist_id}: {e}", file=sys.stderr)
                continue

        return None

    except Exception as e:
        print(f"❌ Ошибка: {e}", file=sys.stderr)
        return None

def main():
    if len(sys.argv) != 3:
        print("Использование: python3 detect-album-year.py 'Artist' 'Album'")
        sys.exit(1)

    artist = sys.argv[1]
    album = sys.argv[2]

    year = get_year_from_reccobeats(artist, album)
    if year:
        print(year)
    else:
        print("Год не найден")

if __name__ == "__main__":
    main()
