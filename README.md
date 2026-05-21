# UTD Course Tracker

Last updated: May 20, 2026

UTD Course Tracker is a Discord bot that monitors UT Dallas CourseBook sections and sends direct message alerts when tracked classes open.

The bot is written in Python using `discord.py`, `BeautifulSoup4`, `python-dotenv`, `subprocess/cURL`, and JSON file persistence.

IDE used: VS Code

## Features

- Track all sections of a course
- Track one specific section of a course
- Multi-user watchlists separated by Discord user ID
- Instructor tracking
- Background CourseBook polling
- Discord DM alerts when tracked sections open
- Private error logging for bot failures

## Project Structure

```text
classbot.py           # Main bot entry point and background polling loop
CourseBook.py         # CourseBook fetch + parsing logic
track.py              # /track and /untrack slash commands
list.py               # /list slash command
watchlist_store.py    # JSON persistence layer
test_CourseBook.py    # Standalone CourseBook parser test
```

**Supports:**
- Tracking all sections of a course
- Tracking specific sections
- Multi-user watchlists
- Instructor tracking
- Background CourseBook polling
- Private Discord DM alerts

**Limitations:**
- Only Computer Science or Software Engineering courses for 2026 Summer and Fall
- User must have DMs from server members enabled, wherever the bot lives
- User must not block the bot
- CourseBook cookie may expire and require a refresh at times
- This version uses local JSON persistence instead of a database'

This project is unofficial and is not affiliated with UT Dallas.

## How to use:
**/track (CS or SE) (number) (term) (optional: section)**

Example: I want to track all of the CS 3345 (Data Structures) courses for Fall 2026
`/track CS 3345 26f`
This will add all the sections to your tracking list.

Example: I want to track my favorite section for CS 3341 (Probability and Stats) for Summer 2026
`/track CS 3341 26u 0W1`
This will add CS.3341.0W1 to your tracking list, without adding the other sections.

**/untrack (CS or SE) (number) (term) (optional: section)**

Example: I no longer want to track the CS 3345 (Data Structures) courses for Fall 2026
`/untrack CS 3345 26f`
This removes all the sections from your tracking list.

Example: I no longer want to track my favorite section for CS 3341 (Probability and Stats) for Summer 2026
`/untrack CS 3341 26u 0W1`
This will delete CS.3341.0W1 from your tracking list, without deleting the other sections.

**/list** (no arguments)

Prints the list of all courses you are tracking, with open/full information, class name, and instructor. 

## Example output:
If a class opens:
```
🚨 Course opened!

CS XXXX.YYY — Class Name
Instructor: Instructor Name
Status: Open
https://CourseBook.utdallas.edu/search/csXXXX.YYY.26z
```
When using /list:
```
📋 Your tracked classes:

cs1111.000.26a — Open — Class Name
Instructor: Instructor Name

cs1111.001.26b — Open — Class Name
Instructor: Instructor Name
```
## Future Reliability Improvements
- Migrate from JSON storage to SQLite or PostgreSQL.
- Add deployment support with Docker.
- Add professor assignment alerts.
- Add professor change alerts.
- Add section cancellation alerts.
- Add automatic old-term cleanup.
- Add better logging and monitoring.
- Add support for more UTD departments.
- Add a hosted always-on deployment.

