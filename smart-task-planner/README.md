# Smart Task Planner

A Japanese-language task planning application by Zwe Htet, built with Python, Flask, SQLite, and the Google Gen AI SDK.

## Features

- Create, view, edit, and delete tasks with dates, start/end times, importance, and status.
- Search tasks by title and sort the task list.
- Detect overlapping schedules and suggest up to three alternative time slots.
- Compare task priorities when exactly one existing task conflicts and offer to move the lower-priority task.
- Request Gemini recommendations for available time slots and unfinished task priorities.

Scheduling currently uses the hours 09:00–22:00. The database is created automatically on startup.

## Run locally on Windows

Install Python 3.10 or later. Open PowerShell in this project folder, then run:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:GEMINI_API_KEY = "YOUR_API_KEY"
.\.venv\Scripts\python.exe app.py
```

Open http://127.0.0.1:5000 in your browser. Replace `YOUR_API_KEY` with your own Gemini API key in your local terminal only. The application reads the key from the environment; no key file is needed. `.env` files are not loaded automatically.

The current source requests the model `gemini-3.6-flash` in `app.py` and `gemini_test.py`. AI features require this model to be available to your account; these live API calls have not been verified in this prepared copy. If needed, change both occurrences to a model available to your account.

`gemini_test.py` is an optional connectivity check that makes a live API request:

```powershell
.\.venv\Scripts\python.exe gemini_test.py
```

## Project structure

```text
app.py             Flask routes, scheduling logic, and SQLite storage
gemini_test.py     Optional Gemini connectivity check
requirements.txt  Python dependencies
templates/        Japanese HTML interface
.gitignore        Excludes secrets, local data, and generated files
```

## Current scope

This is a local learning/portfolio prototype, with Flask debug mode enabled and no authentication. Task information is sent to Google Gemini when AI recommendations are requested. Public application hosting requires further work; publishing this source repository does not host the running application.

## Graduation project

The next stage is to upgrade Smart Task Planner into a personal assistant.
