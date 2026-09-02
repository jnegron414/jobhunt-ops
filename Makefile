PY := .venv/bin/python

.PHONY: morning scrape digest sync today stats

morning: scrape digest sync today

scrape:
	$(PY) scripts/scrape_boards.py

digest:
	$(PY) scripts/digest.py

sync:
	$(PY) scripts/email_sync.py

today:
	$(PY) scripts/tracker.py today

stats:
	$(PY) scripts/tracker.py stats
