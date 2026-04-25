# GluCare - Diabetes Monitoring and Care Management System

## Features
- Secure authentication (register/login/logout) with password hashing
- Dashboard for logging glucose and food intake
- Interactive glucose trend chart (Chart.js)
- Daily calorie total, target comparison, and excess calorie highlight
- Profile page with caretaker emergency contact details
- Settings page for calorie and glucose threshold preferences
- Reports page with date-range summaries and CSV export
- Reward badges based on consistent tracking streaks
- Critical glucose alert logging for caretaker notifications

## Tech Stack
- Frontend: HTML, CSS, JavaScript (Chart.js)
- Backend: Python (Flask)
- Database: SQLite

## Run
1. Install dependencies:
   `pip install -r requirements.txt`
2. Start the app:
   `python run.py`
3. Open:
   `http://127.0.0.1:5000`

## Security Note
Update `SECRET_KEY` in `app/__init__.py` before production deployment.
