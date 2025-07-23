#!/usr/bin/env python3

# === 1. Импорты и настройки ===
import csv
import os
import sys
import openai
from pathlib import Path
from datetime import datetime

CHUNK_SIZE = 50
DELIMITER = "|"
DEBUG_DIR = "debug"
PROMPT_FILE = "prompt.txt"
RESUME_FILE = os.path.join(DEBUG_DIR, "resume_state.txt")
MODEL = "gpt-4o"

# === 2. Проверка API ключа ===
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("❌ Set OPENAI_API_KEY in environment.")
    sys.exit(1)

# === 3. Аргументы и имена файлов ===
if len(sys.argv) != 3:
    print("Usage: python translate_full_file.py <source.csv> <lang_code>.csv")
    sys.exit(1)

src_file = sys.argv[1]
dst_file = sys.argv[2]

lang_code = Path(dst_file).stem.split("-")[0]
date_str = datetime.now().strftime("%Y%m%d")
output_file = f"{lang_code}-{date_str}.csv"

os.makedirs(DEBUG_DIR, exist_ok=True)
translated_rows = []

# === 4. Загрузка исходного CSV ===
with open(src_file, newline='', encoding='utf-8') as f:
    reader = list(csv.reader(f))
    print(f"📥 Загрузили {len(reader)} строк из {src_file}")

# === 5. Загрузка старого перевода (если есть) ===
existing_translations = {}
if os.path.exists(dst_file):
    with open(dst_file, newline='', encoding='utf-8') as f:
        for row in csv.reader(f):
            if len(row) >= 3:
                existing_translations[row[0]] = row[2]
    print(f"📚 Найдено {len(existing_translations)} строк в предыдущем переводе")

# === 6. Загрузка шаблона промпта ===
with open(PROMPT_FILE, encoding='utf-8') as f:
    prompt_template = f.read()

# === 7. Загрузка состояния resume ===
resume_index = 0
if os.path.exists(RESUME_FILE):
    with open(RESUME_FILE) as f:
        resume_index = int(f.read().strip())
        print(f"🔁 Resume: продолжаем с чанка #{resume_index}")

if resume_index == 0 and os.path.exists(output_file):
    os.remove(output_file)

# === 8. Формирование чанков ===
chunks = [reader[i:i + CHUNK_SIZE] for i in range(0, len(reader), CHUNK_SIZE)]

# === 9. Обработка чанков ===
for chunk_index, chunk in enumerate(chunks):
    if chunk_index < resume_index:
        continue

    print(f"⚙️ Обработка чанка {chunk_index + 1}/{len(chunks)}")

    keys, english_texts, reused_translations = [], [], []
    missing_translations = []

    for row in chunk:
        if len(row) < 2:
            print(f"❌ Ошибка: строка слишком короткая: {row}")
            sys.exit(1)
        key, en = row[0], row[1]
        keys.append(key)
        english_texts.append(en)
        ru = existing_translations.get(key)
        if ru:
            reused_translations.append(ru)
        else:
            reused_translations.append(None)
            missing_translations.append(en)

    # === 10. Попытка загрузить сохранённый перевод ===
    debug_input_file = f"{DEBUG_DIR}/batch_{chunk_index + 1:03d}_gpt_input.txt"
    debug_output_file = f"{DEBUG_DIR}/batch_{chunk_index + 1:03d}_gpt_output.txt"
    debug_summary_file = f"{DEBUG_DIR}/batch_{chunk_index + 1:03d}_debug_summary.txt"

    translated_lines = reused_translations.copy()

    translated_text = None
    if os.path.exists(debug_output_file):
        print(f"⚡️ Используем сохранённый перевод: batch_{chunk_index + 1:03d}_output.txt")
        with open(debug_output_file, encoding='utf-8') as f:
            translated_text = f.read()
    elif missing_translations:
        try:
            prompt = prompt_template.replace("{lang}", lang_code).replace("{sep}", DELIMITER)
            joined_input = DELIMITER.join(missing_translations)

            with open(debug_input_file, "w", encoding="utf-8") as f:
                f.write(joined_input)

            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": joined_input}
                ],
                temperature=0.3
            )
            translated_text = response.choices[0].message.content
            with open(debug_output_file, "w", encoding='utf-8') as f:
                f.write(translated_text)
        except Exception as e:
            print(f"❌ Ошибка в чанке {chunk_index}: {e}")
            sys.exit(1)

    if translated_text:
        new_translations = translated_text.split(DELIMITER)
        if len(new_translations) != len(missing_translations):
            print(f"❌ Ошибка: несовпадение количества строк: {len(missing_translations)} → {len(new_translations)}")
            sys.exit(1)
        idx = 0
        for i, val in enumerate(translated_lines):
            if val is None:
                translated_lines[i] = new_translations[idx]
                idx += 1

    # === 11. Запись таблицы логов и финального результата ===
    with open(debug_summary_file, "w", encoding='utf-8') as f:
        for i in range(len(chunk)):
            key = keys[i]
            en = english_texts[i]
            ru = translated_lines[i]
            status = "OLD" if existing_translations.get(key) else "NEW"
            f.write(f"{i+1:02d}|{status}|{key}|{en}|{ru}\n")

    with open(output_file, "a", encoding='utf-8', newline='') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        for i in range(len(chunk)):
            writer.writerow([keys[i], english_texts[i], translated_lines[i]])

    with open(RESUME_FILE, "w") as f:
        f.write(str(chunk_index + 1))
#     break  # ⛔️ Обрабатываем только один чанк и выходим

# === 12. Финал ===
print(f"✅ Перевод завершён: {output_file}")
print("📂 Отладочные файлы: debug/")
