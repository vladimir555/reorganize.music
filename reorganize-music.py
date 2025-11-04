#!/usr/bin/env python3
import os
import shutil
import urllib.parse
import urllib.request
import json
import time
import sys
import re
from pathlib import Path
from mutagen.mp4 import MP4

# Кэши
_itunes_cache = {}
_recco_cache = {}

def safe_name(name: str) -> str:
    """Удаляет недопустимые символы из имени папки/файла."""
    if not name:
        return "Unknown"
    for char in '<>:"/\\|?*':
        name = name.replace(char, '_')
    return name.strip() or "Unknown"

def get_tag(item, key, default=""):
    """Безопасно извлекает значение тега из MP4-файла."""
    try:
        tags = item.get(key, [default])
        return tags[0] if tags else default
    except Exception:
        return default

def normalize_name(name: str) -> str:
    """Нормализует название: убирает лишние пробелы и приводит к нижнему регистру."""
    return re.sub(r'\s+', ' ', name.strip()).lower()

def is_album_name_dirty(name: str) -> bool:
    """Определяет, выглядит ли название альбома как содержащее технический мусор."""
    if len(name) > 65:
        return True
    # Круглые скобки
    if '(' in name and ')' in name:
        if re.search(r'\([^)]*\d{4}[^)]*\)', name, re.IGNORECASE):
            return True
        if re.search(r'\([^)]*[,;][^)]*\)', name):
            return True
        if re.search(r'\([^)]*(CD|LP|Digipak|Ltd|Remaster|Edition|Japan|Mercury|Sony|Nuclear Blast)[^)]*\)', name, re.IGNORECASE):
            return True
    # Квадратные скобки
    if '[' in name and ']' in name:
        if re.search(r'\[[^\]]*(Japan|Mercury|Sony|Nuclear Blast|CD|LP|Ltd|Ent\.|PHCR|UMC|Digipak|Remaster|Edition)[^\]]*\]', name, re.IGNORECASE):
            return True
        if re.search(r'\[[^\]]*\d{4}[^\]]*\]', name):
            return True
        if re.search(r'\[[^\]]*[,;][^\]]*\]', name):
            return True
    return False

def normalize_artist(artist: str) -> str:
    """Нормализует имя исполнителя для сравнения."""
    return re.sub(r'[^\w]', '', artist.lower())  # удаляем всё кроме букв/цифр

def get_album_info_from_itunes(artist: str, album_query: str) -> dict | None:
    key = (artist, album_query)
    if key in _itunes_cache:
        return _itunes_cache[key]

    query = f"{artist} {album_query}"
    url = "https://itunes.apple.com/search?" + urllib.parse.urlencode({
        "term": query,
        "entity": "album",
        "limit": "1"
    })

    try:
        print(f"🌍 iTunes: запрос {url}", file=sys.stderr)
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as f:
            data = json.load(f)
        print(f"📥 iTunes: ответ = {data}", file=sys.stderr)

        if data.get("results"):
            item = data["results"][0]
            returned_artist = item.get("artistName", "").strip()
            # 🔥 Проверяем совпадение исполнителя
            if normalize_artist(returned_artist) == normalize_artist(artist):
                name = item.get("collectionName", "").strip()
                date = item.get("releaseDate", "")
                year = date[:4] if date and len(date) >= 4 and date[:4].isdigit() else ""
                result = {"name": name, "year": year}
                _itunes_cache[key] = result
                return result
            else:
                print(f"⚠️  iTunes: исполнитель не совпадает (ожидался '{artist}', получен '{returned_artist}')", file=sys.stderr)
    except Exception as e:
        print(f"⚠️  iTunes ошибка: {e}", file=sys.stderr)
        pass

    _itunes_cache[key] = None
    return None

def get_album_info_from_reccobeats(artist: str, album: str) -> dict | None:
    key = (artist, album)
    if key in _recco_cache:
        return _recco_cache[key]

    try:
        search_url = f"https://api.reccobeats.com/v1/artist/search?searchText={urllib.parse.quote(artist)}"
        print(f"🔍 ReccoBeats: запрос артиста: {search_url}", file=sys.stderr)
        req = urllib.request.Request(search_url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as f:
            data = json.load(f)
        print(f"📥 ReccoBeats: ответ артиста = {data}", file=sys.stderr)

        artists = data.get("content", [])
        if not artists:
            _recco_cache[key] = None
            return None

        query_norm = normalize_name(album)

        for a in artists:
            artist_id = a.get("id")
            if not artist_id:
                continue

            try:
                albums_url = f"https://api.reccobeats.com/v1/artist/{urllib.parse.quote(artist_id)}/album"
                print(f"🔍 ReccoBeats: запрос альбомов: {albums_url}", file=sys.stderr)
                req_album = urllib.request.Request(albums_url, headers={'Accept': 'application/json'})
                with urllib.request.urlopen(req_album, timeout=10) as f_album:
                    albums_data = json.load(f_album)
                print(f"📥 ReccoBeats: ответ альбомов = {albums_data}", file=sys.stderr)

                albums = albums_data.get("content", [])
                for alb in albums:
                    name = alb.get("name", "")
                    if normalize_name(name) == query_norm:
                        release_date = alb.get("releaseDate", "")
                        year = release_date[:4] if release_date and release_date[:4].isdigit() else ""
                        result = {"name": name, "year": year}
                        _recco_cache[key] = result
                        return result
            except Exception as e2:
                print(f"⚠️  ReccoBeats (альбомы): {e2}", file=sys.stderr)
                continue

    except Exception as e:
        print(f"⚠️  ReccoBeats общая ошибка: {e}", file=sys.stderr)
        _recco_cache[key] = None
        return None

    _recco_cache[key] = None
    return None

def reorganize_music(src_dir: str, dst_dir: str):
    src = Path(src_dir).resolve()
    dst = Path(dst_dir).resolve()

    if not src.is_dir():
        raise ValueError(f"Исходная папка не существует: {src}")

    dst.mkdir(parents=True, exist_ok=True)

    for m4a_path in src.rglob("*.m4a"):
        try:
            audio = MP4(m4a_path)

            artist_raw = get_tag(audio, "\xa9ART", "Unknown Artist")
            album_raw = get_tag(audio, "\xa9alb", "Unknown Album")
            title = safe_name(get_tag(audio, "\xa9nam", "Unknown Title"))

            artist = safe_name(artist_raw)
            album_clean = safe_name(album_raw)

            # Извлечение года из тега
            year_raw = get_tag(audio, "\xa9day", "").strip()
            if not year_raw:
                year_raw = get_tag(audio, "year", "").strip()

            year = ""
            if year_raw:
                candidate = str(year_raw)[:4]
                if candidate.isdigit() and int(candidate) > 0:
                    year = candidate

            # Обработка "грязных" названий
            if not year or is_album_name_dirty(album_raw):
                # Извлекаем чистое название для поиска (до первой скобки)
                clean_for_search = re.split(r'\s*[\[\(]', album_raw)[0].strip()
                if not clean_for_search:
                    clean_for_search = album_raw

                info = get_album_info_from_itunes(artist_raw, clean_for_search)
                if not info:
                    info = get_album_info_from_reccobeats(artist_raw, clean_for_search)
                if info:
                    album_clean = safe_name(info["name"])
                    if info["year"]:
                        year = info["year"]
                else:
                    # Если API не ответил — оставляем исходное название
                    album_clean = safe_name(album_raw)

            album_folder = f"{year} {album_clean}" if year else album_clean

            # Номер трека
            track_raw = audio.get("trkn", [(0, 0)])[0]
            track_number = track_raw[0] if isinstance(track_raw, tuple) else 0
            track_str = f"{track_number:02d}" if track_number > 0 else "00"

            new_filename = f"{track_str} {title}.m4a"
            new_path = dst / artist / album_folder / new_filename

            if new_path.exists():
                print(f"⚠️  Пропущено (уже есть): {new_path}")
                continue

            new_path.parent.mkdir(parents=True, exist_ok=True)

            # Копируем файл
            shutil.copy2(m4a_path, new_path)

            # Записываем год в тег, если его не было
            if year and year != "0000":
                try:
                    audio_new = MP4(new_path)
                    # Проверяем, есть ли уже год
                    existing_year = get_tag(audio_new, "\xa9day", "").strip()
                    if not existing_year or existing_year == "0" or not existing_year.isdigit():
                        audio_new["\xa9day"] = [year]
                        audio_new.save()
                        print(f"📅 Записан год {year} в тег ©day для: {new_path.name}", file=sys.stderr)
                except Exception as e:
                    print(f"⚠️  Не удалось записать год в тег: {e}", file=sys.stderr)

            # Устанавливаем права только на чтение
            new_path.chmod(0o444)
            print(f"✅ {m4a_path} → {new_path}")

            time.sleep(0.3)

        except Exception as e:
            print(f"❌ Ошибка при обработке {m4a_path}: {e}")

    print("\n✅ Готово! Музыка скопирована и защищена.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Использование: python3 reorganize_music.py <исходная_папка> <папка_назначения>")
        sys.exit(1)

    src_dir = sys.argv[1]
    dst_dir = sys.argv[2]

    reorganize_music(src_dir, dst_dir)
