# Debug file with the purpose of testing if the bot can access coursebook.

# Essential:
import json, os, subprocess
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

COURSEBOOK_COOKIE = os.getenv("COURSEBOOK_COOKIE")

if not COURSEBOOK_COOKIE:
    raise RuntimeError("Missing COURSEBOOK_COOKIE in .env")

# Use the cURL from the request (Inspect Element -> Fetch/XHR)
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
    raise RuntimeError("No JSON returned. Cookie may have expired or request was rejected.")

# Initialize data variables with the data from the cURL command.
data = json.loads(result.stdout)
html = data["sethtml"]["#sr"]
soup = BeautifulSoup(html, "html.parser")

# Print data of the course.
for row in soup.select("tr.cb-row"):
    status_tag = row.select_one(".section-open, .section-closed")
    course_link = row.select_one("a[href^='/search/']")

    if not status_tag or not course_link:
        continue

    section_id = row.get("data-id")
    section = course_link.get_text(strip=True)
    status = status_tag.get_text(strip=True)

    print(section_id, section, status)