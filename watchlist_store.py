import json
from pathlib import Path
from typing import Any

# watchlist.json is organized by Discord user ID and keeps each user's tracked sections separate, even if multiple users track the same class.
WATCHLIST_FILE = Path("watchlist.json")

# Load the file, make new if it doesn't exist. 
def load_watchlist() -> dict[str, Any]:
    if not WATCHLIST_FILE.exists():
        return {"users": {}}

    with WATCHLIST_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    # Make sure the top-level "users" key exists, even if the file was manually edited.
    data.setdefault("users", {})
    return data


# Save through a temporary file first, then replace the real file.
def save_watchlist(data: dict[str, Any]) -> None:
    temp_file = WATCHLIST_FILE.with_suffix(".tmp")

    with temp_file.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, sort_keys=True)

    temp_file.replace(WATCHLIST_FILE)


# Extract the section code from a CourseBook section ID.
def get_section_code_from_section_id(section_id: str) -> str:
    parts = section_id.lower().split(".")

    if len(parts) >= 3:
        return parts[1]

    return ""


# Add matched CourseBook sections to one Discord user's watchlist.
# Returns two lists: newly added sections and sections that were already tracked.
def add_sections_for_user(user_id: str, matched_sections: dict, subject: str, course_number: str, term: str) -> tuple[list[dict], list[dict]]:
    data = load_watchlist()

    user_data = data["users"].setdefault(user_id, {})
    user_sections = user_data.setdefault("sections", {})

    added = []
    already_tracked = []

    subject = subject.lower().strip()
    course_number = course_number.strip()
    term = term.lower().strip()

    for section_id, info in sorted(matched_sections.items()):
        section_id = section_id.lower()
        section_code = get_section_code_from_section_id(section_id)

        # Store a snapshot of the section.
        # The background checker can refresh stale fields later, such as instructor or status.
        record = {
            "section_id": section_id,
            "section_code": section_code,
            "section": info.get("section", ""),
            "title": info.get("title", ""),
            "instructor": info.get("instructor", "TBA"),
            "status": info.get("status", ""),
            "url": info.get("url", ""),
            "subject": subject,
            "course_number": course_number,
            "term": term,
        }

        if section_id in user_sections:
            already_tracked.append(record)
        else:
            user_sections[section_id] = record
            added.append(record)

    save_watchlist(data)
    return added, already_tracked


# Remove either one specific section or every section of a course for this user.
# If section is None, remove all matching sections for subject/course_number/term.
def remove_course_for_user(user_id: str, subject: str, course_number: str, term: str, section: str | None = None) -> list[dict]:
    data = load_watchlist()

    user_data = data["users"].setdefault(user_id, {})
    user_sections = user_data.setdefault("sections", {})

    subject = subject.lower().strip()
    course_number = course_number.strip()
    term = term.lower().strip()
    section_code = section.strip().lstrip(".").lower() if section else None

    removed = []

    target_prefix = f"{subject}{course_number}."
    target_suffix = f".{term}"
    exact_section_id = f"{subject}{course_number}.{section_code}.{term}" if section_code else None

    for section_id, info in list(user_sections.items()):
        normalized_id = section_id.lower()

        if exact_section_id:
            should_remove = normalized_id == exact_section_id
        else:
            same_subject = info.get("subject") == subject
            same_course = info.get("course_number") == course_number
            same_term = info.get("term") == term

            # Fallback for older watchlist.json records that may not have
            # subject/course_number/term saved correctly.
            same_id_pattern = normalized_id.startswith(target_prefix) and normalized_id.endswith(target_suffix)

            should_remove = (same_subject and same_course and same_term) or same_id_pattern

        if should_remove:
            removed.append(info)
            del user_sections[section_id]

    save_watchlist(data)
    return removed


# Return every unique section ID tracked by any user.
# The background checker uses this to know which CourseBook sections matter.
def get_all_tracked_section_ids() -> set[str]:
    data = load_watchlist()
    section_ids = set()

    for user_data in data.get("users", {}).values():
        section_ids.update(user_data.get("sections", {}).keys())

    return {section_id.lower() for section_id in section_ids}


# Return all users tracking a specific section.
# If a section opens, every user in this list should receive a DM.
def get_users_tracking(section_id: str) -> list[str]:
    data = load_watchlist()
    users = []

    section_id = section_id.lower()

    for user_id, user_data in data.get("users", {}).items():
        if section_id in user_data.get("sections", {}):
            users.append(user_id)

    return users


# Build the unique CourseBook searches needed by the background checker.
def get_tracked_query_groups() -> set[tuple[str, str]]:
    data = load_watchlist()
    groups = set()

    for user_data in data.get("users", {}).values():
        for info in user_data.get("sections", {}).values():
            term = info.get("term")
            subject = info.get("subject")

            if term and subject:
                groups.add((term, subject))

    return groups


# Refresh saved watchlist records with the latest CourseBook data.
# This fixes stale fields like TBA instructors, changed statuses, or updated titles.
def update_tracked_sections_from_coursebook(current_sections: dict) -> list[dict]:
    data = load_watchlist()
    changes = []

    for user_id, user_data in data.get("users", {}).items():
        user_sections = user_data.get("sections", {})

        for section_id, saved_info in user_sections.items():
            normalized_id = section_id.lower()

            if normalized_id not in current_sections:
                continue

            latest_info = current_sections[normalized_id]

            fields_to_update = [
                "section",
                "status",
                "title",
                "instructor",
                "url",
            ]

            for field in fields_to_update:
                old_value = saved_info.get(field)
                new_value = latest_info.get(field)

                if new_value is None:
                    continue

                if field == "instructor" and not new_value:
                    new_value = "TBA"

                if old_value != new_value:
                    saved_info[field] = new_value

                    changes.append(
                        {
                            "user_id": user_id,
                            "section_id": normalized_id,
                            "field": field,
                            "old": old_value,
                            "new": new_value,
                        }
                    )

    if changes:
        save_watchlist(data)

    return changes