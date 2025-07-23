import csv
import sys
import os
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

CHUNK_SIZE = 50
DELIMITER = "|"
MODEL = "gpt-4o"

# Чтение шаблона промпта
if not os.path.exists(PROMPT_TEMPLATE_FILE):
    print(f"❌ Prompt template file not found: {PROMPT_TEMPLATE_FILE}")
    sys.exit(1)

with open(PROMPT_TEMPLATE_FILE, "r", encoding="utf-8") as f:
    PROMPT_TEMPLATE = f.read()

# Проверка API-ключа
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("❌ OPENAI_API_KEY is not set.")
    sys.exit(1)

client = OpenAI(api_key=api_key)

# Параметры командной строки
if len(sys.argv) != 3:
    print("Usage: python translate_full_file.py SRC_LANG DST_LANG")
    sys.exit(1)

src_lang = sys.argv[1]
dst_lang = sys.argv[2]

src_file = f"{src_lang}.csv"
date_str = datetime.now().strftime("%Y%m%d")
out_file = f"{dst_lang}-{date_str}.csv"

print(f"🔁 Translating '{src_file}' → '{out_file}'...")

# Загрузка исходных данных
with open(src_file, newline='', encoding='utf-8') as f:
    reader = list(csv.reader(f))
    chunks = [reader[i:i + CHUNK_SIZE] for i in range(0, len(reader), CHUNK_SIZE)]

with open(out_file, 'w', newline='', encoding='utf-8') as out_f:
    writer = csv.writer(out_f, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')

    for chunk_index, chunk in enumerate(chunks):
        keys, english_lines = [], []

        for row in chunk:
            if len(row) < 2:
                continue
            keys.append(row[0])
            english_lines.append(row[1])

        joined_en = DELIMITER.join(english_lines)

        print(f"\n📦 Translating chunk {chunk_index + 1}/{len(chunks)} ({len(english_lines)} lines)...")

        try:
            system_prompt = PROMPT_TEMPLATE.format(lang=dst_lang, sep=DELIMITER)
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": joined_en
                    }
                ],
                temperature=0.3
            )

            translated = response.choices[0].message.content
            translated_lines = translated.split(DELIMITER)

            if len(translated_lines) != len(english_lines):
                print("❌ Line count mismatch!")
                print("Original:", english_lines)
                print("Translated:", translated_lines)
                sys.exit(1)

            for i in range(len(keys)):
                writer.writerow([keys[i], english_lines[i], translated_lines[i]])

        except Exception as e:
            print(f"❌ Error during translation batch {chunk_index}: {e}")
            sys.exit(1)

print(f"\n✅ Translation complete! Output saved to: {out_file}")