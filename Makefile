PY := .venv/bin/python

.PHONY: morning scrape digest shortlist sync today stats

morning: scrape digest shortlist sync today

scrape:
	$(PY) scripts/scrape_boards.py

digest:
	$(PY) scripts/digest.py

shortlist:
	$(PY) scripts/shortlist.py

sync:
	$(PY) scripts/email_sync.py

today:
	$(PY) scripts/tracker.py today

stats:
	$(PY) scripts/tracker.py stats
