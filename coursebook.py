# Coursebook.py to fetch and parse CourseBook data for specific terms and subjects. Plug this into classbot.py to get real-time updates on class statuses.

# Imports needed, BeautifulSoup for parsing.
import json, os, subprocess
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

COURSEBOOK_COOKIE = os.getenv("COURSEBOOK_COOKIE")
COURSEBOOK_URL = "https://coursebook.utdallas.edu/clips/clip-cb11-hat.zog"

def fetch_coursebook_html(term: str, subject: str) -> str:
    if not COURSEBOOK_COOKIE:
        raise RuntimeError("Missing COURSEBOOK_COOKIE in .env")

    # Term can be '26u' for Summer 2026, '26f' for Fall 2026, etc.
    # Subject filter format is 'cp_cs' for CS, 'cp_se' for SE, etc. We only support CS and SE in this version.
    term_filter = f"term_{term}"
    subject_filter = f"cp_{subject}"

    payload = f"action=search&s%5B%5D={term_filter}&s%5B%5D={subject_filter}"
    referer = f"https://coursebook.utdallas.edu/action=search&s%5B%5D={term_filter}&s%5B%5D={subject_filter}"

    # All this info is to mimic the exact request that CourseBook's frontend makes, including headers and cookies, to avoid being blocked or getting an empty response.
    curl_command = [
        "curl",
        "-sS",
        "--max-time", "20",
        COURSEBOOK_URL,
        "-H", "accept: */*",
        "-H", "accept-language: en-US,en;q=0.9,es;q=0.8,he;q=0.7,ja;q=0.6",
        "-H", "content-type: application/x-www-form-urlencoded; charset=UTF-8",
        "-b", COURSEBOOK_COOKIE,
        "-H", "origin: https://coursebook.utdallas.edu",
        "-H", "priority: u=1, i",
        "-H", f"referer: {referer}",
        "-H", 'sec-ch-ua: "Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
        "-H", "sec-ch-ua-mobile: ?1",
        "-H", 'sec-ch-ua-platform: "iOS"',
        "-H", "sec-fetch-dest: empty",
        "-H", "sec-fetch-mode: cors",
        "-H", "sec-fetch-site: same-origin",
        "-H", "user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15",
        "-H", "x-requested-with: XMLHttpRequest",
        "--data-raw", payload,
    ]

    result = subprocess.run(curl_command, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"curl failed for {subject.upper()} {term}: {result.stderr}")

    if not result.stdout.strip():
        raise RuntimeError(
            f"CourseBook returned empty response for {subject.upper()} {term}. "
            "Your COURSEBOOK_COOKIE may have expired."
        )

    data = json.loads(result.stdout)
    return data["sethtml"]["#sr"]

# Use soup to parse the HTML response and extract course sections, status, title, instructor, and URL.
# Turn this into dict keyed by section_id to look up the latest info when refreshing the watchlist.
def parse_sections(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    sections = {}

    # Inspect -> Network -> Get the .zog request's Response -> Better view. 
    for row in soup.select("tr.cb-row"):
        status_tag = row.select_one(".section-open, .section-closed")
        course_link = row.select_one("a[href^='/search/']")

        if not status_tag or not course_link:
            continue

        section_id = row.get("data-id")
        section = course_link.get_text(strip=True)
        status = status_tag.get_text(strip=True)

        cells = row.select("td")

        title = cells[3].get_text(" ", strip=True) if len(cells) > 3 else ""
        instructor = cells[4].get_text(" ", strip=True) if len(cells) > 4 else "TBA"

        if not instructor or instructor == "-Staff-":
            instructor = "TBA"

        sections[section_id] = {
            "section_id": section_id,
            "section": section,
            "status": status,
            "title": title,
            "instructor": instructor,
            "url": f"https://coursebook.utdallas.edu/search/{section_id}",
        }

    return sections

# Main function to get sections for specified term and subjects. This is what classbot.py will call to refresh the data.
def get_sections(term: str, subjects: tuple[str, ...] = ("cs", "se")) -> dict:
    all_sections = {}

    for subject in subjects:
        html = fetch_coursebook_html(term, subject)
        subject_sections = parse_sections(html)
        all_sections.update(subject_sections)

    return all_sections

# If this file is run directly, it will fetch and print the sections for the default term and subjects. This is useful for testing the CourseBook fetching and parsing logic in isolation.
if __name__ == "__main__":
    sections = get_sections(term="26u", subjects=("cs", "se")) # Filter to summer to avoid fetching too many sections during testing. Adjust term and subjects as needed.

    for section_id, info in sections.items():
        print(
            info["section"],
            info["status"],
            "-",
            info["title"],
            info.get("instructor", "TBA"),
        )