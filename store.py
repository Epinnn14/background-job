"""In-memory report store. It forgets everything on restart. Same lesson as A1, still not a bug."""
REPORTS: dict[str, dict] = {}
