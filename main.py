"""
Student Record Manager
A command-line project using only Python's standard library.

Features:
- Add, view, search, update, and delete student records
- Validate user input (including NaN/infinity and corrupted data files)
- Save records atomically in a JSON file so they survive restarts and crashes
- Display class statistics
"""

import json
import math
import os
import tempfile
from pathlib import Path

DATA_FILE = Path(__file__).with_name("students.json")
PASS_MARK = 40
MAX_NAME_LENGTH = 100
MAX_ID_LENGTH = 32


# --------------------------------------------------------------------------
# Validation helpers
# --------------------------------------------------------------------------
def is_valid_marks(value):
    """True if value is a real number (not bool/NaN/inf) between 0 and 100."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value) and 0 <= value <= 100


def parse_marks(raw_value):
    """Convert text to marks. Return None if the text is not valid marks."""
    try:
        marks = float(str(raw_value).strip())
    except ValueError:
        return None
    return marks if is_valid_marks(marks) else None


def is_valid_record(record):
    """True if a loaded record has the right keys and value types."""
    return (
        isinstance(record, dict)
        and isinstance(record.get("student_id"), str)
        and record["student_id"].strip() != ""
        and isinstance(record.get("name"), str)
        and record["name"].strip() != ""
        and is_valid_marks(record.get("marks"))
    )


# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------
def load_students():
    """Load records from JSON, skipping corrupted or duplicate entries.

    Returns an empty list if the file is missing or unreadable.
    """
    if not DATA_FILE.exists():
        return []

    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        print("Warning: could not read students.json. Starting with no records.")
        return []

    if not isinstance(data, list):
        print("Warning: data file format was invalid. Starting with no records.")
        return []

    students, seen_ids, skipped = [], set(), 0
    for record in data:
        if not is_valid_record(record):
            skipped += 1
            continue
        key = record["student_id"].strip().casefold()
        if key in seen_ids:
            skipped += 1
            continue
        seen_ids.add(key)
        students.append(
            {
                "student_id": record["student_id"].strip(),
                "name": record["name"].strip(),
                "marks": float(record["marks"]),
            }
        )

    if skipped:
        print(f"Warning: skipped {skipped} invalid or duplicate record(s).")
    return students


def save_students(students):
    """Save all records atomically (temp file + replace). Return True on success."""
    tmp_path = None
    try:
        directory = DATA_FILE.parent
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=directory, suffix=".tmp", delete=False
        ) as tmp:
            tmp_path = tmp.name
            json.dump(students, tmp, indent=4, ensure_ascii=False)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_path, DATA_FILE)
        return True
    except (OSError, TypeError, ValueError):
        print("Error: records could not be saved. Check folder permissions.")
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        return False


# --------------------------------------------------------------------------
# Input helpers
# --------------------------------------------------------------------------
def get_nonempty_text(prompt, max_length=None):
    """Ask until the user enters non-empty text (optionally length-limited)."""
    while True:
        value = input(prompt).strip()
        if not value:
            print("This field cannot be empty. Please try again.")
        elif max_length and len(value) > max_length:
            print(f"Please use at most {max_length} characters.")
        else:
            return value


def get_valid_marks(prompt="Enter marks (0-100): "):
    """Ask for a numeric mark between 0 and 100, inclusive."""
    while True:
        raw_value = input(prompt).strip()
        try:
            float(raw_value)
        except ValueError:
            print("Please enter a number, such as 75 or 82.5.")
            continue

        marks = parse_marks(raw_value)
        if marks is not None:
            return marks
        print("Marks must be between 0 and 100.")


def get_yes_no(prompt):
    """Ask until the user answers y or n. Return True for yes."""
    while True:
        answer = input(prompt).strip().casefold()
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Please enter y or n.")


def find_student_index(students, student_id):
    """Return the index of a student ID (case-insensitive), or -1 if absent."""
    wanted = student_id.strip().casefold()
    for index, student in enumerate(students):
        if student["student_id"].casefold() == wanted:
            return index
    return -1


# --------------------------------------------------------------------------
# Statistics (pure function, easy to test)
# --------------------------------------------------------------------------
def calculate_statistics(students):
    """Return a dict of class statistics, or None if there are no students."""
    if not students:
        return None
    marks = [s["marks"] for s in students]
    passed = sum(mark >= PASS_MARK for mark in marks)
    return {
        "count": len(students),
        "average": sum(marks) / len(marks),
        "highest": max(students, key=lambda s: s["marks"]),
        "lowest": min(students, key=lambda s: s["marks"]),
        "passed": passed,
        "failed": len(students) - passed,
    }


# --------------------------------------------------------------------------
# Menu actions
# --------------------------------------------------------------------------
def add_student(students):
    print("\n--- Add Student ---")
    while True:
        student_id = get_nonempty_text("Enter student ID: ", MAX_ID_LENGTH)
        if find_student_index(students, student_id) == -1:
            break
        print("That student ID already exists. Please use a unique ID.")

    name = get_nonempty_text("Enter student name: ", MAX_NAME_LENGTH)
    marks = get_valid_marks()

    students.append({"student_id": student_id, "name": name, "marks": marks})

    if save_students(students):
        print(f"Student '{name}' added successfully.")
    else:
        # Keep the in-memory list consistent with the last saved state.
        students.pop()
        print("Student was not added because saving failed.")


def view_students(students):
    print("\n--- All Students ---")
    if not students:
        print("No student records found. Add a student first.")
        return

    print(f"{'ID':<16} {'NAME':<28} {'MARKS':>8}")
    print("-" * 54)
    for student in students:
        print(
            f"{student['student_id'][:15]:<16} "
            f"{student['name'][:27]:<28} {student['marks']:>8.2f}"
        )


def search_student(students):
    print("\n--- Search Student ---")
    student_id = get_nonempty_text("Enter student ID to search: ")
    index = find_student_index(students, student_id)

    if index == -1:
        print("Student not found.")
        return

    student = students[index]
    print(f"ID:    {student['student_id']}")
    print(f"Name:  {student['name']}")
    print(f"Marks: {student['marks']:.2f}")


def update_student(students):
    print("\n--- Update Student ---")
    student_id = get_nonempty_text("Enter student ID to update: ")
    index = find_student_index(students, student_id)

    if index == -1:
        print("Student not found.")
        return

    student = students[index]
    print(f"Current name: {student['name']}")
    while True:
        new_name = input("Enter new name (press Enter to keep current): ").strip()
        if len(new_name) <= MAX_NAME_LENGTH:
            break
        print(f"Please use at most {MAX_NAME_LENGTH} characters.")

    print(f"Current marks: {student['marks']:.2f}")
    change_marks = get_yes_no("Change marks? (y/n): ")

    old_student = student.copy()
    if new_name:
        student["name"] = new_name
    if change_marks:
        student["marks"] = get_valid_marks("Enter new marks (0-100): ")

    if student == old_student:
        print("No changes were made.")
        return

    if save_students(students):
        print("Student record updated successfully.")
    else:
        students[index] = old_student
        print("Changes were not saved; original record restored.")


def delete_student(students):
    print("\n--- Delete Student ---")
    student_id = get_nonempty_text("Enter student ID to delete: ")
    index = find_student_index(students, student_id)

    if index == -1:
        print("Student not found.")
        return

    student = students[index]
    confirmed = get_yes_no(
        f"Delete {student['name']} (ID: {student['student_id']})? (y/n): "
    )
    if not confirmed:
        print("Deletion cancelled.")
        return

    removed_student = students.pop(index)
    if save_students(students):
        print("Student record deleted successfully.")
    else:
        students.insert(index, removed_student)
        print("Deletion was not saved; original record restored.")


def show_statistics(students):
    print("\n--- Class Statistics ---")
    stats = calculate_statistics(students)
    if stats is None:
        print("No records available to calculate statistics.")
        return

    print(f"Number of students: {stats['count']}")
    print(f"Class average:      {stats['average']:.2f}")
    print(f"Highest marks:      {stats['highest']['marks']:.2f} ({stats['highest']['name']})")
    print(f"Lowest marks:       {stats['lowest']['marks']:.2f} ({stats['lowest']['name']})")
    print(f"Passed ({PASS_MARK}+):       {stats['passed']}")
    print(f"Below {PASS_MARK}:           {stats['failed']}")


def display_menu():
    print("\n" + "=" * 32)
    print("      STUDENT RECORD MANAGER")
    print("=" * 32)
    print("1. Add student")
    print("2. View all students")
    print("3. Search student by ID")
    print("4. Update student details")
    print("5. Delete student")
    print("6. Show class statistics")
    print("7. Exit")


def main():
    students = load_students()
    actions = {
        "1": add_student,
        "2": view_students,
        "3": search_student,
        "4": update_student,
        "5": delete_student,
        "6": show_statistics,
    }

    try:
        while True:
            display_menu()
            choice = input("Choose an option (1-7): ").strip()

            if choice == "7":
                print("Goodbye! Your saved records will be available next time.")
                break
            action = actions.get(choice)
            if action is None:
                print("Invalid option. Please enter a number from 1 to 7.")
                continue
            action(students)
    except (EOFError, KeyboardInterrupt):
        print("\nInput closed. Exiting. Saved records are kept.")


if __name__ == "__main__":
    main()
