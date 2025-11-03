#!/usr/bin/env python3
import sys
from pathlib import Path

def show_tags(filepath):
    filepath = Path(filepath)
    if not filepath.is_file():
        print(f"❌ Файл не найден: {filepath}")
        return

    try:
        # Пытаемся определить формат автоматически
        from mutagen import File
        audio = File(filepath)
        if audio is None:
            print("⚠️  Неизвестный или неподдерживаемый формат файла.")
            return

        print(f"🔤 Теги файла: {filepath}\n")
        for key, value in sorted(audio.tags.items() if audio.tags else []):
            # Для M4A значения часто — списки
            if isinstance(value, list):
                value = "; ".join(str(v) for v in value)
            print(f"{key:20} : {value}")

        # Отдельно покажем длительность и битрейт, если есть
        if hasattr(audio.info, 'length'):
            print(f"\n⏱ Длительность (сек): {audio.info.length:.2f}")
        if hasattr(audio.info, 'bitrate'):
            print(f"🎙 Битрейт (бит/сек): {audio.info.bitrate}")

    except Exception as e:
        print(f"❌ Ошибка при чтении тегов: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python3 show_tags.py <путь_к_файлу.m4a>")
        sys.exit(1)

    show_tags(sys.argv[1])
