import json, os, subprocess
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load environment variables from the .env file.
load_dotenv()

COURSEBOOK_COOKIE = os.getenv("COURSEBOOK_COOKIE")

# Use the session cookie to make the request.
def fetch_coursebook_html() -> str:
    if not COURSEBOOK_COOKIE:
        raise RuntimeError("Missing COURSEBOOK_COOKIE in .env")

    # Construct the curl command with the headers needed by CourseBook.
    curl_command = [
        "curl",
        "-sS",
        "--max-time", "20",
        "https://coursebook.utdallas.edu/clips/clip-cb11-hat.zog",
        "-H", "accept: */*",
        "-H", "accept-language: en-US,en;q=0.9,es;q=0.8,he;q=0.7,ja;q=0.6",
        "-H", "content-type: application/x-www-form-urlencoded; charset=UTF-8",
        "-b", COURSEBOOK_COOKIE,
        "-H", "origin: https://coursebook.utdallas.edu",
        "-H", "priority: u=1, i",
        "-H", "referer: https://coursebook.utdallas.edu/action=search&s%5B%5D=term_26u&s%5B%5D=cp_se",
        "-H", 'sec-ch-ua: "Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
        "-H", "sec-ch-ua-mobile: ?1",
        "-H", 'sec-ch-ua-platform: "iOS"',
        "-H", "sec-fetch-dest: empty",
        "-H", "sec-fetch-mode: cors",
        "-H", "sec-fetch-site: same-origin",
        "-H", "user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15",
        "-H", "x-requested-with: XMLHttpRequest",
        "--data-raw", "action=search&s%5B%5D=term_26u&s%5B%5D=cp_se",
    ]

    result = subprocess.run(
        curl_command,
        capture_output=True,
        text=True,
    )

# Error handling.
    if result.returncode != 0:
        raise RuntimeError(f"curl failed: {result.stderr}")
    if not result.stdout.strip():
        raise RuntimeError(
            "CourseBook returned empty response. "
            "Your COURSEBOOK_COOKIE may have expired."
        )

    # The response is JSON containing HTML in the sethtml field.
    data = json.loads(result.stdout)
    return data["sethtml"]["#sr"]


# Go through the HTML using BeautifulSoup to extract course sections, their status, and titles.
def parse_sections(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    sections = {}

    # Each course listing is contained in a row with the cb-row class.
    for row in soup.select("tr.cb-row"):
        status_tag = row.select_one(".section-open, .section-closed")
        course_link = row.select_one("a[href^='/search/']")

        if not status_tag or not course_link:
            # Skip rows that do not contain a valid course entry.
            continue

        section_id = row.get("data-id")
        section = course_link.get_text(strip=True)
        status = status_tag.get_text(strip=True)

        cells = row.select("td")
        title = cells[3].get_text(" ", strip=True) if len(cells) > 3 else ""

        sections[section_id] = {
            "section": section,
            "status": status,
            "title": title,
            "url": f"https://coursebook.utdallas.edu/search/{section_id}",
        }

    return sections

def get_sections() -> dict:
    html = fetch_coursebook_html()
    return parse_sections(html)


if __name__ == "__main__":
    # When the module is run directly, print the parsed section data.
    sections = get_sections()

    for section_id, info in sections.items():
        print(info["section"], info["status"], "-", info["title"])