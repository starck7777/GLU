import csv
import io
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
    Response,
)
from werkzeug.security import check_password_hash, generate_password_hash


MEAL_PRESETS = [
    {
        "id": "idli-sambar",
        "name": "2 idli + sambar",
        "category": "Breakfast",
        "calories": 180,
        "image": "images/meals/idli-sambar.svg",
    },
    {
        "id": "oats-porridge",
        "name": "Oats porridge",
        "category": "Breakfast",
        "calories": 220,
        "image": "images/meals/oats-porridge.svg",
    },
    {
        "id": "sprouts-salad",
        "name": "Sprouts salad",
        "category": "Snack",
        "calories": 160,
        "image": "images/meals/sprouts-salad.svg",
    },
    {
        "id": "almonds-walnuts",
        "name": "Handful of almonds or walnuts",
        "category": "Snack",
        "calories": 170,
        "image": "images/meals/almonds-walnuts.svg",
    },
    {
        "id": "dal-roti",
        "name": "2 multigrain rotis + dal",
        "category": "Lunch",
        "calories": 340,
        "image": "images/meals/dal-roti.svg",
    },
    {
        "id": "sabzi-rice",
        "name": "Brown rice + vegetable sabzi",
        "category": "Lunch",
        "calories": 320,
        "image": "images/meals/sabzi-rice.svg",
    },
    {
        "id": "boiled-egg",
        "name": "1 boiled egg",
        "category": "Evening",
        "calories": 78,
        "image": "images/meals/boiled-egg.svg",
    },
    {
        "id": "grilled-protein-salad",
        "name": "Grilled chicken/fish + salad",
        "category": "Dinner",
        "calories": 290,
        "image": "images/meals/grilled-protein-salad.svg",
    },
]

MEAL_PRESET_MAP = {meal["id"]: meal for meal in MEAL_PRESETS}



def create_app():
    import os
    app = Flask('campusfic', instance_relative_config=True, root_path=os.path.dirname(__file__))
    app.config.from_mapping(
        SECRET_KEY="change-this-secret-key",
        DATABASE=app.instance_path + "/diabetes_app.sqlite3",
    )

    init_app(app)

    @app.route("/")
    def home():
        if g.user:
            return redirect(url_for("dashboard"))
        return redirect(url_for("login"))

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            username = request.form.get("username", "").strip().lower()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            if not username or not email or not password:
                flash("All fields are required.", "error")
                return render_template("register.html")

            if len(password) < 8:
                flash("Password must be at least 8 characters.", "error")
                return render_template("register.html")

            try:
                db = get_db()
                db.execute(
                    "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                    (username, email, generate_password_hash(password)),
                )
                db.commit()
                flash("Account created successfully. Please login.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("Username or email already exists.", "error")

        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip().lower()
            password = request.form.get("password", "")

            db = get_db()
            user = db.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()

            if not user or not check_password_hash(user["password_hash"], password):
                flash("Invalid username or password.", "error")
                return render_template("login.html")

            session.clear()
            session["user_id"] = user["id"]
            flash("Welcome back.", "success")
            return redirect(url_for("dashboard"))

        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        flash("Logged out.", "success")
        return redirect(url_for("login"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        db = get_db()
        user_id = g.user["id"]
        selected_preset = MEAL_PRESET_MAP.get(request.args.get("preset_meal_id", "").strip())

        today = date.today().isoformat()

        glucose_rows = db.execute(
            """
            SELECT reading_mgdl, logged_at
            FROM glucose_logs
            WHERE user_id = ?
            ORDER BY logged_at DESC
            LIMIT 30
            """,
            (user_id,),
        ).fetchall()

        food_rows_today = db.execute(
            """
            SELECT meal_name, calories, logged_at
            FROM food_logs
            WHERE user_id = ? AND date(logged_at) = ?
            ORDER BY logged_at DESC
            """,
            (user_id, today),
        ).fetchall()

        activity_rows_today = db.execute(
            """
            SELECT activity_name, minutes, calories_burned, logged_at
            FROM activity_logs
            WHERE user_id = ? AND date(logged_at) = ?
            ORDER BY logged_at DESC
            """,
            (user_id, today),
        ).fetchall()

        total_calories = sum(row["calories"] for row in food_rows_today)
        calories_burned = sum(row["calories_burned"] for row in activity_rows_today)
        net_calories = total_calories - calories_burned
        target = g.user["target_calories"]
        excess = max(0, net_calories - target)

        glucose_chart = sorted(glucose_rows, key=lambda x: x["logged_at"])
        labels = [format_dt(row["logged_at"]) for row in glucose_chart]
        values = [row["reading_mgdl"] for row in glucose_chart]

        streak_days = calculate_streak(db, user_id)
        reward_level = reward_from_streak(streak_days)
        streak_points = calculate_streak_points(db, user_id)

        recent_notifications = db.execute(
            """
            SELECT event_type, message, created_at
            FROM notification_logs
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 5
            """,
            (user_id,),
        ).fetchall()

        return render_template(
            "dashboard.html",
            glucose_rows=glucose_rows,
            food_rows_today=food_rows_today,
            activity_rows_today=activity_rows_today,
            total_calories=round(total_calories, 1),
            calories_burned=round(calories_burned, 1),
            net_calories=round(net_calories, 1),
            target_calories=target,
            excess_calories=round(excess, 1),
            glucose_labels=labels,
            glucose_values=values,
            streak_days=streak_days,
            streak_points=streak_points,
            reward_level=reward_level,
            recent_notifications=recent_notifications,
            selected_preset=selected_preset,
        )

    @app.route("/meals")
    @login_required
    def meals():
        return render_template("meals.html", meal_presets=MEAL_PRESETS)

    @app.route("/log/glucose", methods=["POST"])
    @login_required
    def log_glucose():
        reading = request.form.get("reading_mgdl", "").strip()
        notes = request.form.get("notes", "").strip()
        logged_at = build_logged_at_value(
            request.form.get("glucose_date", "").strip(),
            request.form.get("glucose_time", "").strip(),
            request.form.get("logged_at", "").strip(),
        )

        try:
            reading_value = float(reading)
            if reading_value <= 0:
                raise ValueError
        except ValueError:
            flash("Please enter a valid glucose value.", "error")
            return redirect(url_for("dashboard"))

        db = get_db()
        db.execute(
            """
            INSERT INTO glucose_logs (user_id, reading_mgdl, notes, logged_at)
            VALUES (?, ?, ?, ?)
            """,
            (g.user["id"], reading_value, notes, logged_at),
        )

        low = g.user["glucose_low_threshold"]
        high = g.user["glucose_high_threshold"]
        if reading_value < low or reading_value > high:
            event_type = "critical_glucose"
            message = (
                f"Critical glucose reading {reading_value} mg/dL at {logged_at}. "
                f"Notify caretaker {g.user['caretaker_name'] or 'not set'} "
                f"({g.user['caretaker_phone'] or 'phone not set'})."
            )
            db.execute(
                "INSERT INTO notification_logs (user_id, event_type, message) VALUES (?, ?, ?)",
                (g.user["id"], event_type, message),
            )
            flash("Critical reading detected. Caretaker alert has been queued.", "warning")
        else:
            flash("Glucose reading logged.", "success")

        db.commit()
        return redirect(url_for("dashboard"))

    @app.route("/log/food", methods=["POST"])
    @login_required
    def log_food():
        preset_id = request.form.get("preset_meal_id", "").strip()
        meal_name = request.form.get("meal_name", "").strip()
        calories = request.form.get("calories", "").strip()
        logged_at = request.form.get("logged_at", "").strip()

        preset = MEAL_PRESET_MAP.get(preset_id)
        if preset:
            meal_name = preset["name"]
            calories_value = float(preset["calories"])
        else:
            try:
                calories_value = float(calories)
                if calories_value <= 0:
                    raise ValueError
            except ValueError:
                flash("Calories must be a positive number.", "error")
                return redirect(url_for("dashboard"))

        if not meal_name:
            flash("Meal name is required.", "error")
            return redirect(url_for("dashboard"))

        if not logged_at:
            logged_at = datetime.now().strftime("%Y-%m-%dT%H:%M")

        db = get_db()
        db.execute(
            """
            INSERT INTO food_logs (user_id, meal_name, calories, logged_at)
            VALUES (?, ?, ?, ?)
            """,
            (g.user["id"], meal_name, calories_value, logged_at),
        )
        db.commit()
        flash("Food entry logged.", "success")
        return redirect(url_for("dashboard"))

    @app.route("/log/activity", methods=["POST"])
    @login_required
    def log_activity():
        activity_name = request.form.get("activity_name", "").strip()
        minutes = request.form.get("minutes", "").strip()
        calories_burned = request.form.get("calories_burned", "").strip()
        logged_at = request.form.get("logged_at", "").strip()

        if not activity_name:
            flash("Activity name is required.", "error")
            return redirect(url_for("dashboard"))

        try:
            minutes_value = float(minutes) if minutes else 0
            calories_burned_value = float(calories_burned)
            if minutes_value < 0 or calories_burned_value <= 0:
                raise ValueError
        except ValueError:
            flash("Minutes must be zero or more and calories burned must be positive.", "error")
            return redirect(url_for("dashboard"))

        if not logged_at:
            logged_at = datetime.now().strftime("%Y-%m-%dT%H:%M")

        db = get_db()
        db.execute(
            """
            INSERT INTO activity_logs (user_id, activity_name, minutes, calories_burned, logged_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (g.user["id"], activity_name, minutes_value, calories_burned_value, logged_at),
        )
        db.commit()
        flash("Calorie burn entry logged.", "success")
        return redirect(url_for("dashboard"))

    @app.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile():
        if request.method == "POST":
            full_name = request.form.get("full_name", "").strip()
            age = request.form.get("age", "0").strip()
            weight = request.form.get("weight", "0").strip()
            caretaker_name = request.form.get("caretaker_name", "").strip()
            caretaker_phone = request.form.get("caretaker_phone", "").strip()
            caretaker_email = request.form.get("caretaker_email", "").strip()

            try:
                age = int(age) if age else 0
                weight = float(weight) if weight else 0
            except ValueError:
                flash("Age and weight must be numeric.", "error")
                return render_template("profile.html")

            db = get_db()
            db.execute(
                """
                UPDATE users
                SET full_name = ?, age = ?, weight = ?, caretaker_name = ?, caretaker_phone = ?, caretaker_email = ?
                WHERE id = ?
                """,
                (
                    full_name,
                    age,
                    weight,
                    caretaker_name,
                    caretaker_phone,
                    caretaker_email,
                    g.user["id"],
                ),
            )
            db.commit()
            flash("Profile updated.", "success")
            refresh_user()
            return redirect(url_for("profile"))

        return render_template("profile.html")

    @app.route("/settings", methods=["GET", "POST"])
    @login_required
    def settings():
        if request.method == "POST":
            target_calories = request.form.get("target_calories", "2000").strip()
            low = request.form.get("glucose_low_threshold", "70").strip()
            high = request.form.get("glucose_high_threshold", "180").strip()

            try:
                target_calories = int(target_calories)
                low = int(low)
                high = int(high)
                if target_calories <= 0 or low <= 0 or high <= low:
                    raise ValueError
            except ValueError:
                flash("Invalid thresholds or calorie target.", "error")
                return render_template("settings.html")

            db = get_db()
            db.execute(
                """
                UPDATE users
                SET target_calories = ?, glucose_low_threshold = ?, glucose_high_threshold = ?
                WHERE id = ?
                """,
                (target_calories, low, high, g.user["id"]),
            )
            db.commit()
            refresh_user()
            flash("Settings saved.", "success")
            return redirect(url_for("settings"))

        return render_template("settings.html")

    @app.route("/reports")
    @login_required
    def reports():
        db = get_db()
        user_id = g.user["id"]

        end_date = request.args.get("end_date", date.today().isoformat())
        start_date = request.args.get("start_date", (date.today() - timedelta(days=6)).isoformat())

        glucose = db.execute(
            """
            SELECT date(logged_at) as day, AVG(reading_mgdl) as avg_glucose, MIN(reading_mgdl) as min_g, MAX(reading_mgdl) as max_g
            FROM glucose_logs
            WHERE user_id = ? AND date(logged_at) BETWEEN ? AND ?
            GROUP BY date(logged_at)
            ORDER BY day ASC
            """,
            (user_id, start_date, end_date),
        ).fetchall()

        calories = db.execute(
            """
            SELECT date(logged_at) as day, SUM(calories) as total_calories
            FROM food_logs
            WHERE user_id = ? AND date(logged_at) BETWEEN ? AND ?
            GROUP BY date(logged_at)
            ORDER BY day ASC
            """,
            (user_id, start_date, end_date),
        ).fetchall()

        glucose_count = db.execute(
            "SELECT COUNT(*) AS c FROM glucose_logs WHERE user_id = ? AND date(logged_at) BETWEEN ? AND ?",
            (user_id, start_date, end_date),
        ).fetchone()["c"]

        insights = build_insights(glucose, calories, g.user["target_calories"])

        return render_template(
            "reports.html",
            start_date=start_date,
            end_date=end_date,
            glucose=glucose,
            calories=calories,
            insights=insights,
            glucose_count=glucose_count,
        )

    @app.route("/reports/export")
    @login_required
    def export_report():
        db = get_db()
        user_id = g.user["id"]

        end_date = request.args.get("end_date", date.today().isoformat())
        start_date = request.args.get("start_date", (date.today() - timedelta(days=6)).isoformat())

        rows = db.execute(
            """
            SELECT date(g.logged_at) as day,
                   AVG(g.reading_mgdl) as avg_glucose,
                   SUM(f.calories) as total_calories
            FROM glucose_logs g
            LEFT JOIN food_logs f
                ON date(g.logged_at) = date(f.logged_at) AND g.user_id = f.user_id
            WHERE g.user_id = ? AND date(g.logged_at) BETWEEN ? AND ?
            GROUP BY date(g.logged_at)
            ORDER BY day ASC
            """,
            (user_id, start_date, end_date),
        ).fetchall()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Day", "Average Glucose (mg/dL)", "Total Calories"])
        for row in rows:
            writer.writerow(
                [row["day"], round(row["avg_glucose"], 1), round(row["total_calories"] or 0, 1)]
            )

        csv_data = output.getvalue()
        output.close()

        filename = f"diabetes_report_{start_date}_to_{end_date}.csv"
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    return app



def init_app(app: Flask):
    import os

    os.makedirs(app.instance_path, exist_ok=True)

    with app.app_context():
        init_db()

    @app.before_request
    def load_logged_in_user():
        user_id = session.get("user_id")
        if user_id is None:
            g.user = None
        else:
            g.user = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    @app.teardown_appcontext
    def close_db(_error):
        db = g.pop("db", None)
        if db is not None:
            db.close()



def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app().config["DATABASE"], detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
    return g.db



def current_app():
    from flask import current_app as flask_current_app

    return flask_current_app



def init_db():
    db = get_db()
    with current_app().open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf8"))
    db.commit()



def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("login"))
        return view(**kwargs)

    return wrapped_view



def refresh_user():
    g.user = get_db().execute("SELECT * FROM users WHERE id = ?", (g.user["id"],)).fetchone()



def calculate_streak(db, user_id: int) -> int:
    rows = get_logged_days(db, user_id)

    if not rows:
        return 0

    logged_days = {datetime.strptime(row["day"], "%Y-%m-%d").date() for row in rows}
    streak = 0
    cursor = date.today()

    while cursor in logged_days:
        streak += 1
        cursor -= timedelta(days=1)

    return streak


def calculate_streak_points(db, user_id: int) -> int:
    rows = get_logged_days(db, user_id)

    if not rows:
        return 0

    logged_days = {datetime.strptime(row["day"], "%Y-%m-%d").date() for row in rows}
    first_day = min(logged_days)
    total_days = (date.today() - first_day).days + 1
    missed_days = max(0, total_days - len(logged_days))
    points = (len(logged_days) * 10) - (missed_days * 8)
    return max(0, points)


def get_logged_days(db, user_id: int):
    return db.execute(
        """
        SELECT DISTINCT date(logged_at) AS day
        FROM (
            SELECT logged_at FROM glucose_logs WHERE user_id = ?
            UNION ALL
            SELECT logged_at FROM food_logs WHERE user_id = ?
            UNION ALL
            SELECT logged_at FROM activity_logs WHERE user_id = ?
        )
        ORDER BY day DESC
        """,
        (user_id, user_id, user_id),
    ).fetchall()



def reward_from_streak(streak_days: int) -> str:
    if streak_days >= 30:
        return "Platinum Consistency"
    if streak_days >= 14:
        return "Gold Consistency"
    if streak_days >= 7:
        return "Silver Consistency"
    if streak_days >= 3:
        return "Bronze Starter"
    return "Keep Going"



def build_insights(glucose_rows, calorie_rows, target_calories):
    insights = []

    if glucose_rows:
        avg = sum(row["avg_glucose"] for row in glucose_rows if row["avg_glucose"] is not None) / len(glucose_rows)
        insights.append(f"Average glucose in selected range: {avg:.1f} mg/dL")
    else:
        insights.append("No glucose data available in selected range.")

    if calorie_rows:
        above_target_days = sum(1 for row in calorie_rows if (row["total_calories"] or 0) > target_calories)
        insights.append(f"Days above calorie target: {above_target_days} out of {len(calorie_rows)}")
    else:
        insights.append("No food logs available in selected range.")

    return insights


def build_logged_at_value(date_value: str, time_value: str, fallback_value: str = "") -> str:
    if date_value:
        selected_time = time_value or datetime.now().strftime("%H:%M")
        return f"{date_value}T{selected_time}"

    if fallback_value:
        return fallback_value

    return datetime.now().strftime("%Y-%m-%dT%H:%M")


def format_dt(dt_text: str) -> str:
    try:
        return datetime.fromisoformat(dt_text).strftime("%b %d %H:%M")
    except ValueError:
        return dt_text
