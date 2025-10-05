# AI Coding Instructions for "type" - Russian Language Learning App

## Project Overview
**type** is a TikTok-style infinite word feed for Russian language EGE (Unified State Exam) preparation. Users complete fill-in-the-blank exercises by selecting correct answers from multiple choices, with a gamified strike system and Telegram bot integration.

## Architecture & Key Components

### Core Structure
- **Flask App**: Main application in `app/` with modular routing (`app/routes/`)
- **Dual Word Systems**: 
  - Regular words (`app/models.py`) with missing letters marked as `_`
  - Paronyms (`app/paronym/models.py`) with morphological analysis via pymorphy3
- **Strike System**: Progressive achievement levels [50, 100, 500, 1000] with background rewards
- **iframe-based UI**: TikTok-like swiping interface using nested iframes (`frame_inner.html`)

### Database Models
```python
# Words use JSON arrays for answers (first = correct)
Word.answers = ["correct", "wrong1", "wrong2"]  # First is always correct
Word.word = "пр_вильно"  # _ marks missing letters

# Paronyms handle morphological forms
Sentence.word_tags = "sing,nomn"  # Morphological tags for word forms
```

### Environment Configuration
- **Development**: `ENV=development` enables debug mode, uses `run_dev.py`
- **Production**: Uses `wsgi.py` with Gunicorn
- **Telegram**: Toggle with `ENABLE_TELEGRAM=true/false` - affects bot initialization and webhooks

## Critical Development Workflows

### Running the Application
```bash
# Development (with scheduler and debug)
python run_dev.py

# Production
gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app

# Database initialization
python app.py  # Creates tables
python json_to_db.py  # Loads data dump
```

### Data Management
- **Export**: `python db_to_json.py` → `fixtures/backup_YYYY-MM-DD.json`
- **Import**: `python json_to_db.py` loads from `fixtures/` 
- **Parsing**: Use `parsing/` scripts to process new word data from CSV/external sources

### Telegram Bot Setup
```bash
python set_webhook.py  # Sets webhook to /tg_webhook endpoint
# Requires BOT_TOKEN and URL in .env
```

## Project-Specific Patterns

### Strike System Logic
```python
# Session-based strike tracking with database fallback
session['strike'] = get_strike(user_id) if not in session
# Resets to 0 on wrong answers, increments on correct answers
# Affects background images and achievement levels
```

### iframe Communication
- Parent page (`index.html`) manages two iframes (current/next)
- `framesManaging.js` handles swipe gestures and frame transitions
- `postMessage` API coordinates between parent and iframe content

### Dual Content Types
- **Task 5** (Paronyms): Uses `Sentence` model with morphological inflection
- **Other Tasks**: Uses `Word` model with simple letter replacement
- Route detection: `'task_id=5' in request.url` determines rendering mode

### Admin Features
- Admin access: `user_id == ADMIN_ID` from environment
- Live explanation editing via AJAX (`/add_explanation`)
- Answer management (`/delete_answer`)
- Mistake reporting to `mistakes.txt` file

### Background Scheduler
- Auto-backup every `BACKUP_PERIOD` days
- Telegram notifications every `SEND_NOTIFICATION_PERIOD` minutes
- Only runs in development via `run_dev.py`

## Integration Points

### Telegram Web App
- Authentication via `InitData.parse()` and hash validation
- Web App button launches main interface
- Daily statistics sent via `/day` command

### Static Assets
- Dynamic backgrounds based on strike level (`/get_background`)
- Theme system with JSON configuration (`static/css/themes/`)
- Material Symbols icons for UI consistency

## Common Pitfalls
- **Session Management**: User ID stored in Flask session, fallback for unauthenticated users
- **JSON Answers**: Always ensure first element in `Word.answers` is correct answer
- **Morphology**: Paronym inflection uses comma-separated tags in `word_tags` field
- **iframe Security**: Be careful with `postMessage` communication patterns
- **Database Migrations**: Use Flask-Migrate, but backup before schema changes

## Key Files for Understanding
- `app/__init__.py` - Application initialization and conditional imports
- `app/routes/user_pages.py` - Core game logic and word checking
- `app/static/js/framesManaging.js` - UI interaction patterns
- `config.py` - Feature flags and environment-specific settings