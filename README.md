# Student Record Manager

A command-line Python application for managing student records, with JSON
persistence, strict input validation, class statistics, and a 50-test
automated suite. Built with the standard library only.

## Highlights
- Full CRUD: add, view, search (case-insensitive), update, delete with confirmation
- Class statistics: size, average, highest/lowest, pass/fail count (pass mark = 40)
- **Atomic saves** (temp file + `os.replace`), so a crash never corrupts `students.json`
- **Self-healing loads**: corrupted, duplicate, or malformed records are skipped with a warning instead of crashing
- **Strict validation**: rejects empty input, `NaN`/`inf`, out-of-range marks, booleans, over-long names/IDs
- **Rollback on failed saves**: in-memory data always matches what is on disk
- Clean exit on Ctrl+C / end-of-input
- Statistics logic is a pure function (`calculate_statistics`) and easy to test

## Requirements
- Python 3.9+
- No third-party packages

## Run
```bash
python main.py
```

## Test
```bash
python -m unittest -v
```
The suite covers boundary values (0, 100, 39.99, 40), invalid input (NaN, inf,
negatives, text), unicode IDs and names, corrupted/empty/binary data files,
duplicate IDs, save failures with rollback, long values in table layout, a
5,000-student class, and a full add/update/delete workflow that persists across restarts.

## Project structure
```
student_record_manager/
├── main.py            # application
├── tests/test_main.py # automated tests
├── README.md
└── .gitignore
```

## Notes
- `students.json` is created automatically after the first successful save.
- This is a learning project, not a secure database. Use sample data only.

## Suggested GitHub description
Python CLI student record manager with JSON storage, atomic saves, input validation, class statistics, and a 50-test unittest suite.
