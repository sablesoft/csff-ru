venv:
	python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt

run:
	source venv/bin/activate && python translate_update.py Jp.csv Ru.csv