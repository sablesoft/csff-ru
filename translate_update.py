#!/usr/bin/env python3

import csv
import os
import sys
import time
import openai
from datetime import datetime
from pathlib import Path

# === НАСТРОЙКИ ===
CHUNK_SIZE = 50
DELIMITER = "|"
DEBUG_DIR = "debug"
PROMPT_FILE = "prompt.txt"
RESUME_FILE = os.path.join(DEBUG_DIR, "resume_state.txt")

# === API МОДЕЛЬ ===
MODEL = "gpt-4o"
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("❌ Set OPENAI_API_KEY in environment.")
    sys.exit(1)

# === ВХОДНЫЕ ПАРАМЕТРЫ ===
if len(sys.argv) != 3:
    print("Usage: python translate_full_file.py <source.csv> <lang_code>.csv")
    sys.exit(1)

src_file = sys.argv[1]
dst_file = sys.argv[2]

# === ЯЗЫК ===
lang_code = Path(dst_file).stem.split("-")[0]
date_str = datetime.now().strftime("%Y%m%d")
output_file = f"{lang_code}-{date_str}.csv"

os.makedirs(DEBUG_DIR, exist_ok=True)
translated_rows = []

# === ЗАГРУЗКА CSV ===
with open(src_file, newline='', encoding='utf-8') as f:
    reader = list(csv.reader(f))
    print(f"📥 Загрузили {len(reader)} строк из {src_file}")

# === ЗАГРУЗКА ПРОМПТА ===
with open(PROMPT_FILE, encoding='utf-8') as f:
    prompt_template = f.read()

# === ЗАГРУЗКА СОСТОЯНИЯ RESUME ===
resume_index = 0
if os.path.exists(RESUME_FILE):
    with open(RESUME_FILE) as f:
        resume_index = int(f.read().strip())
        print(f"🔁 Режим resume: продолжаем с чанка #{resume_index}")

# === ЧАНКИНГ ===
chunks = [reader[i:i + CHUNK_SIZE] for i in range(0, len(reader), CHUNK_SIZE)]

for chunk_index, chunk in enumerate(chunks):
    if chunk_index < resume_index:
        continue

    print(f"\n⚙️ Обработка чанка {chunk_index + 1}/{len(chunks)}")

    keys, english_texts = [], []
    for row in chunk:
        if len(row) < 2:
            print(f"❌ Ошибка: строка с недостаточным количеством колонок: {row}")
            sys.exit(1)
        keys.append(row[0])
        english_texts.append(row[1])

    joined_input = DELIMITER.join(english_texts)

    # === ЛОГ ВХОДА ===
    with open(f"{DEBUG_DIR}/batch_{chunk_index:03d}_input.txt", "w", encoding='utf-8') as f:
        f.write(joined_input)

    # === GPT-ЗАПРОС ===
    prompt = prompt_template.replace("{lang}", lang_code).replace("{sep}", DELIMITER)

    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": joined_input}
            ],
            temperature=0.3
        )
        translated_text = response.choices[0].message.content

        # === ЛОГ ВЫХОДА ===
        with open(f"{DEBUG_DIR}/batch_{chunk_index:03d}_output.txt", "w", encoding='utf-8') as f:
            f.write(translated_text)

        translated_lines = translated_text.split(DELIMITER)

        # Логируем и сравниваем
        debug_summary = f"""
        🔎 Batch: {chunk_index}
        🔑 Keys: {keys}
        📥 Input lines: {len(english_texts)}
        📤 Translated lines: {len(translated_lines)}
        """

        if len(english_texts) <= 10:
            for i in range(len(translated_lines)):
                en = english_texts[i] if i < len(english_texts) else "<missing>"
                tr = translated_lines[i] if i < len(translated_lines) else "<missing>"
                debug_summary += f"\n{i+1:02d}. EN: {en}\n    TR: {tr}"

        with open(f"{DEBUG_DIR}/batch_{chunk_index:03d}_debug_summary.txt", "w", encoding="utf-8") as f:
            f.write(debug_summary)

        if len(translated_lines) != len(english_texts):
            print(f"❌ Ошибка: несовпадение количества строк: {len(english_texts)} → {len(translated_lines)}")
            print("📂 Проверь debug/ для подробностей")
            sys.exit(1)

        for i in range(len(chunk)):
            row = chunk[i]
            translated_row = [row[0], row[1], translated_lines[i]]
            translated_rows.append(translated_row)

        # === СОХРАНЯЕМ ПРОГРЕСС ===
        with open(output_file, "w", encoding='utf-8', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            writer.writerows(translated_rows)

        with open(RESUME_FILE, "w") as f:
            f.write(str(chunk_index + 1))

    except Exception as e:
        print(f"❌ Ошибка при обработке чанка {chunk_index}: {e}")
        sys.exit(1)

print(f"\n✅ Перевод завершён: {output_file}")
print("📂 Промежуточные файлы: debug/")
