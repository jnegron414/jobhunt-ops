PY := .venv/bin/python

.PHONY: morning scrape digest shortlist sheets inbox sync today stats

morning: scrape digest shortlist sheets inbox sync today

scrape:
	$(PY) scripts/scrape_boards.py

digest:
	$(PY) scripts/digest.py

shortlist:
	$(PY) scripts/shortlist.py

sheets:
	$(PY) scripts/sheet_sync.py

inbox:
	$(PY) scripts/inbox_watch.py

sync:
	$(PY) scripts/email_sync.py

today:
	$(PY) scripts/tracker.py today

stats:
	$(PY) scripts/tracker.py stats
