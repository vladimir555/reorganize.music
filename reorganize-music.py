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

# Кэш для запросов к iTunes: {(artist, album_query): {"name": str, "year": str} or None}
_itunes_cache = {}

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

def is_album_name_dirty(name: str) -> bool:
    """Определяет, выглядит ли название альбома как содержащее технический мусор."""
    if len(name) > 65:
        return True
    if '(' in name and ')' in name:
        # Скобки с годом, запятыми, CD/LP и т.п.
        if re.search(r'\([^)]*\d{4}[^)]*\)', name, re.IGNORECASE):
            return True
        if re.search(r'\([^)]*[,;][^)]*\)', name):
            return True
        if re.search(r'\([^)]*(CD|LP|Digipak|Ltd|Remaster|Edition)[^)]*\)', name, re.IGNORECASE):
            return True
    return False

def get_album_info_from_itunes(artist: str, album_query: str) -> dict | None:
    """Возвращает {'name': str, 'year': str} из iTunes API или None."""
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
        print(f"🌍 Запрашиваю чистое название для: {artist} — {album_query}", file=sys.stderr)
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as f:
            data = json.load(f)
        if data.get("results"):
            item = data["results"][0]
            print(f"🔍 Ответ от iTunes: {item.get('collectionName', '')} | {item.get('releaseDate', 'NO DATE')}", file=sys.stderr)
            name = item.get("collectionName", "").strip()
            date = item.get("releaseDate", "")
            year = date[:4] if date and len(date) >= 4 and date[:4].isdigit() else ""
            result = {"name": name, "year": year}
            _itunes_cache[key] = result
            return result
    except Exception as e:
        print(f"⚠️  Ошибка iTunes API: {e}", file=sys.stderr)
        pass

    _itunes_cache[key] = None
    return None

def reorganize_music(src_dir: str, dst_dir: str):
    src = Path(src_dir).resolve()
    dst = Path(dst_dir).resolve()

    if not src.is_dir():
        raise ValueError(f"Исходная папка не существует: {src}")

    dst.mkdir(parents=True, exist_ok=True)
    # dst.chmod(0o555)

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

            # Если название "грязное" или года нет — запрос к iTunes
            if not year or is_album_name_dirty(album_raw):
                info = get_album_info_from_itunes(artist_raw, album_raw)
                if info:
                    album_clean = safe_name(info["name"])
                    if info["year"]:
                        year = info["year"]

            # Формируем имя папки альбома
            album_folder = f"{year} {album_clean}" if year else album_clean

            # Номер трека
            track_raw = audio.get("trkn", [(0, 0)])[0]
            track_number = track_raw[0] if isinstance(track_raw, tuple) else 0
            track_str = f"{track_number:02d}" if track_number > 0 else "00"

            new_filename = f"{track_str} {title}.m4a"
            new_path = dst / artist / album_folder / new_filename

            # Пропускаем, если файл уже существует
            if new_path.exists():
                print(f"⚠️  Файл уже существует, пропускаем: {new_path}")
                continue

            # Создаём папки
            new_path.parent.mkdir(parents=True, exist_ok=True)

            # Устанавливаем права 555 на все созданные папки (artist и album)
            for parent in [new_path.parent, new_path.parent.parent]:
                if parent.exists():
                    try:
                        pass # parent.chmod(0o555)
                    except Exception:
                        pass

            # Копируем файл
            shutil.copy2(m4a_path, new_path)
            new_path.chmod(0o444)

            print(f"✅ Скопировано: {new_path}")

            # Пауза, чтобы не перегружать iTunes API
            time.sleep(0.3)

        except Exception as e:
            print(f"❌ Ошибка при обработке {m4a_path}: {e}")

    print("\n✅ Готово! Музыка скопирована и защищена.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Использование: python3 reorganize_music.py <исходная_папка> <папка_назначения>")
        print("Пример: python3 reorganize_music.py /Volumes/data/music /Volumes/data/music_reorganized")
        sys.exit(1)

    src_dir = sys.argv[1]
    dst_dir = sys.argv[2]

    reorganize_music(src_dir, dst_dir)
