import os
import re
import hashlib
import secrets
from datetime import datetime

from dotenv import load_dotenv
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify
)
from flask_mail import Mail, Message
from flask_mysqldb import MySQL
import MySQLdb.cursors
from itsdangerous import (
    BadSignature, SignatureExpired, URLSafeTimedSerializer
)

# --------------------------------------------------
# APPLICATION CONFIGURATION
# --------------------------------------------------

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("FLASK_SECRET_KEY")
if not app.secret_key:
    raise RuntimeError(
        "FLASK_SECRET_KEY is missing. Add it to your .env file."
    )

app.config["MYSQL_HOST"] = os.getenv("MYSQL_HOST", "localhost")
app.config["MYSQL_USER"] = os.getenv("MYSQL_USER", "root")
app.config["MYSQL_PASSWORD"] = os.getenv("MYSQL_PASSWORD", "")
app.config["MYSQL_DB"] = os.getenv(
    "MYSQL_DB", "service_marketplace"
)

app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", "587"))
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME", "")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD", "")

mysql = MySQL(app)
mail = Mail(app)

password_reset_serializer = URLSafeTimedSerializer(app.secret_key)


# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------

def send_email(to_email, subject, body):
    """Send email without interrupting the booking workflow."""
    if not to_email or not app.config["MAIL_USERNAME"]:
        return False

    try:
        message = Message(
            subject=subject,
            recipients=[to_email],
            body=body
        )
        mail.send(message)
        return True
    except Exception:
        app.logger.exception("Failed to send email to %s", to_email)
        return False


def hash_password(password):
    """Kept compatible with the existing SHA-256 password records."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def make_password_reset_token(email, role):
    return password_reset_serializer.dumps(
        {"email": email, "role": role},
        salt="password-reset"
    )


def read_password_reset_token(token):
    return password_reset_serializer.loads(
        token,
        salt="password-reset",
        max_age=3600
    )


# --------------------------------------------------
# HOME PAGE
# --------------------------------------------------

@app.route("/")
def index():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("""
        SELECT
            w.*,
            AVG(b.rating) AS avg_rating,
            COUNT(b.id) AS total_bookings
        FROM workers w
        LEFT JOIN bookings b
            ON w.id = b.worker_id
            AND b.rating IS NOT NULL
        GROUP BY w.id
        ORDER BY avg_rating DESC
        LIMIT 6
    """)

    featured_workers = cursor.fetchall()

    cursor.execute("""
        SELECT DISTINCT category
        FROM workers
        ORDER BY category
    """)

    categories = cursor.fetchall()
    cursor.close()

    return render_template(
        "index.html",
        featured_workers=featured_workers,
        categories=categories
    )


# --------------------------------------------------
# LOGIN
# --------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        role = request.form.get("role", "")
        email = request.form.get("email", "").strip()
        password = hash_password(request.form.get("password", ""))

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        if role == "user":
            cursor.execute(
                "SELECT * FROM users WHERE email=%s AND password=%s",
                (email, password)
            )
            account = cursor.fetchone()

            if account:
                session["loggedin"] = True
                session["id"] = account["id"]
                session["name"] = account["name"]
                session["role"] = "user"

                cursor.close()
                return redirect(url_for("user_dashboard"))

        elif role == "worker":
            cursor.execute(
                "SELECT * FROM workers WHERE email=%s AND password=%s",
                (email, password)
            )
            account = cursor.fetchone()

            if account:
                session["loggedin"] = True
                session["id"] = account["id"]
                session["name"] = account["name"]
                session["role"] = "worker"

                cursor.close()
                return redirect(url_for("worker_dashboard"))

        cursor.close()
        flash("Invalid credentials. Please try again.", "error")

    return render_template("login.html")


# --------------------------------------------------
# FORGOT PASSWORD
# --------------------------------------------------

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        role = request.form.get("role")
        email = request.form.get("email", "").strip()

        table = (
            "users" if role == "user"
            else "workers" if role == "worker"
            else None
        )

        if table and email:
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

            cursor.execute(
                f"SELECT email FROM {table} WHERE email=%s",
                (email,)
            )
            account = cursor.fetchone()
            cursor.close()

            if account:
                token = make_password_reset_token(email, role)
                reset_url = url_for(
                    "reset_password",
                    token=token,
                    _external=True
                )

                send_email(
                    email,
                    "Reset your Service Marketplace password",
                    f"Use this link to reset your password "
                    f"(valid for 1 hour):\n\n{reset_url}\n\n"
                    "If you did not request this, ignore this email."
                )

        flash(
            "If an account matches that email, we sent a reset link.",
            "info"
        )
        return redirect(url_for("forgot_password"))

    return render_template("forgot_password.html")


# --------------------------------------------------
# RESET PASSWORD
# --------------------------------------------------

@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        reset_data = read_password_reset_token(token)
    except (BadSignature, SignatureExpired):
        flash("That password reset link is invalid or expired.", "error")
        return redirect(url_for("forgot_password"))

    role = reset_data.get("role")
    email = reset_data.get("email")

    table = (
        "users" if role == "user"
        else "workers" if role == "worker"
        else None
    )

    if not table or not email:
        flash("That password reset link is invalid.", "error")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")

        elif password != confirm_password:
            flash("Passwords do not match.", "error")

        else:
            cursor = mysql.connection.cursor()

            cursor.execute(
                f"UPDATE {table} SET password=%s WHERE email=%s",
                (hash_password(password), email)
            )

            mysql.connection.commit()
            cursor.close()

            flash("Password updated successfully. Please login.", "success")
            return redirect(url_for("login"))

    return render_template("reset_password.html")


# --------------------------------------------------
# REGISTRATION
# --------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        role = request.form.get("role")
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        password = hash_password(request.form.get("password", ""))

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        if role == "user":
            cursor.execute(
                "SELECT id FROM users WHERE email=%s",
                (email,)
            )

            if cursor.fetchone():
                flash("Email already registered!", "error")
            else:
                cursor.execute("""
                    INSERT INTO users (name, email, phone, password)
                    VALUES (%s, %s, %s, %s)
                """, (name, email, phone, password))

                mysql.connection.commit()
                cursor.close()

                flash("Registration successful! Please login.", "success")
                return redirect(url_for("login"))

        elif role == "worker":
            category = request.form.get("category", "").strip()
            skills = request.form.get("skills", "").strip()
            hourly_rate = request.form.get("hourly_rate", "0")
            bio = request.form.get("bio", "").strip()

            cursor.execute(
                "SELECT id FROM workers WHERE email=%s",
                (email,)
            )

            if cursor.fetchone():
                flash("Email already registered!", "error")
            else:
                cursor.execute("""
                    INSERT INTO workers
                        (name, email, phone, password, category,
                         skills, hourly_rate, bio)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    name, email, phone, password, category,
                    skills, hourly_rate, bio
                ))

                mysql.connection.commit()
                cursor.close()

                flash(
                    "Worker registration successful! Please login.",
                    "success"
                )
                return redirect(url_for("login"))

        else:
            flash("Please select a valid account role.", "error")

        cursor.close()

    return render_template("register.html")


# --------------------------------------------------
# LOGOUT
# --------------------------------------------------

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# --------------------------------------------------
# CUSTOMER DASHBOARD
# --------------------------------------------------

@app.route("/user/dashboard")
def user_dashboard():
    if (
        not session.get("loggedin")
        or session.get("role") != "user"
    ):
        return redirect(url_for("login"))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("""
        SELECT
            b.*,
            w.name AS worker_name,
            w.category,
            w.profile_image
        FROM bookings b
        JOIN workers w ON b.worker_id = w.id
        WHERE b.user_id = %s
        ORDER BY b.created_at DESC
        LIMIT 5
    """, (session["id"],))

    recent_bookings = cursor.fetchall()

    cursor.execute(
        "SELECT COUNT(*) AS total FROM bookings WHERE user_id=%s",
        (session["id"],)
    )
    stats = cursor.fetchone()

    cursor.execute("""
        SELECT COUNT(*) AS pending
        FROM bookings
        WHERE user_id=%s AND status='pending'
    """, (session["id"],))
    pending = cursor.fetchone()

    cursor.execute("""
        SELECT COUNT(*) AS completed
        FROM bookings
        WHERE user_id=%s AND status='completed'
    """, (session["id"],))
    completed = cursor.fetchone()

    cursor.close()

    return render_template(
        "user_dashboard.html",
        recent_bookings=recent_bookings,
        total=stats["total"],
        pending=pending["pending"],
        completed=completed["completed"]
    )


@app.route("/user/bookings")
def user_bookings():
    if (
        not session.get("loggedin")
        or session.get("role") != "user"
    ):
        return redirect(url_for("login"))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("""
        SELECT
            b.*,
            w.name AS worker_name,
            w.category,
            w.phone AS worker_phone
        FROM bookings b
        JOIN workers w ON b.worker_id = w.id
        WHERE b.user_id = %s
        ORDER BY b.created_at DESC
    """, (session["id"],))

    bookings = cursor.fetchall()
    cursor.close()

    return render_template("user_bookings.html", bookings=bookings)


@app.route("/user/rate/<int:booking_id>", methods=["POST"])
def rate_booking(booking_id):
    if (
        not session.get("loggedin")
        or session.get("role") != "user"
    ):
        return redirect(url_for("login"))

    rating = request.form.get("rating")
    review = request.form.get("review", "")

    if not rating or not rating.isdigit() or not 1 <= int(rating) <= 5:
        flash("Please select a rating between 1 and 5.", "error")
        return redirect(url_for("user_bookings"))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("""
        UPDATE bookings
        SET rating=%s, review=%s
        WHERE id=%s AND user_id=%s AND status='completed'
    """, (int(rating), review, booking_id, session["id"]))

    mysql.connection.commit()
    updated = cursor.rowcount
    cursor.close()

    if updated:
        flash("Rating submitted successfully!", "success")
    else:
        flash("Booking not found or not completed yet.", "error")

    return redirect(url_for("user_bookings"))


# --------------------------------------------------
# SERVICE SEARCH
# --------------------------------------------------

@app.route("/services")
def services():
    category = request.args.get("category", "").strip()
    service_type = request.args.get("service_type", "").strip()
    location = request.args.get("location", "").strip()
    pincode = request.args.get("pincode", "").strip()

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    query = """
        SELECT
            w.*,
            AVG(b.rating) AS avg_rating,
            COUNT(b.id) AS total_reviews
        FROM workers w
        LEFT JOIN bookings b
            ON w.id = b.worker_id
            AND b.rating IS NOT NULL
        WHERE w.is_available = 1
    """

    params = []

    if category:
        query += " AND w.category = %s"
        params.append(category)

    if service_type:
        query += " AND w.category LIKE %s"
        params.append(f"%{service_type}%")

    if location:
        query += " AND w.location LIKE %s"
        params.append(f"%{location}%")

    if pincode:
        query += " AND w.pincode LIKE %s"
        params.append(f"%{pincode}%")

    query += """
        GROUP BY w.id
        ORDER BY avg_rating DESC
    """

    cursor.execute(query, params)
    workers = cursor.fetchall()

    cursor.execute("""
        SELECT DISTINCT category
        FROM workers
        ORDER BY category
    """)
    categories = cursor.fetchall()

    cursor.close()

    return render_template(
        "services.html",
        workers=workers,
        categories=categories,
        selected_category=category,
        service_type=service_type,
        location=location,
        pincode=pincode
    )


# --------------------------------------------------
# WORKER PROFILE
# --------------------------------------------------

@app.route("/worker/<int:worker_id>")
def worker_profile(worker_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("""
        SELECT
            w.*,
            AVG(b.rating) AS avg_rating,
            COUNT(b.id) AS total_reviews
        FROM workers w
        LEFT JOIN bookings b
            ON w.id = b.worker_id
            AND b.rating IS NOT NULL
        WHERE w.id = %s
        GROUP BY w.id
    """, (worker_id,))

    worker = cursor.fetchone()

    if not worker:
        cursor.close()
        return redirect(url_for("services"))

    cursor.execute("""
        SELECT
            b.rating,
            b.review,
            b.created_at,
            u.name AS user_name
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        WHERE b.worker_id = %s
          AND b.rating IS NOT NULL
        ORDER BY b.created_at DESC
        LIMIT 10
    """, (worker_id,))

    reviews = cursor.fetchall()
    cursor.close()

    return render_template(
        "worker_profile.html",
        worker=worker,
        reviews=reviews
    )


# --------------------------------------------------
# BOOK SERVICE
# --------------------------------------------------

@app.route("/book/<int:worker_id>", methods=["GET", "POST"])
def book_service(worker_id):
    if (
        not session.get("loggedin")
        or session.get("role") != "user"
    ):
        flash("Please login to book a service.", "info")
        return redirect(url_for("login"))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute(
        "SELECT * FROM workers WHERE id=%s AND is_available=1",
        (worker_id,)
    )
    worker = cursor.fetchone()

    if not worker:
        cursor.close()
        flash("Worker not found or unavailable.", "error")
        return redirect(url_for("services"))

    if request.method == "POST":
        try:
            service_date = request.form["service_date"]
            service_time = request.form["service_time"]
            duration = float(request.form["duration"])
            address = request.form["address"].strip()
            notes = request.form.get("notes", "").strip()

            if duration <= 0 or not address:
                raise ValueError("Invalid duration or address.")

            total_amount = float(worker["hourly_rate"]) * duration

        except (KeyError, ValueError, TypeError):
            cursor.close()
            flash("Please enter valid booking details.", "error")
            return redirect(url_for("book_service", worker_id=worker_id))

        cursor.execute(
            "SELECT name, email, phone FROM users WHERE id=%s",
            (session["id"],)
        )
        customer = cursor.fetchone()

        if not customer:
            cursor.close()
            flash("Customer account not found.", "error")
            return redirect(url_for("login"))

        cursor.execute("""
            INSERT INTO bookings
                (user_id, worker_id, service_date, service_time,
                 duration, address, notes, total_amount)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            session["id"], worker_id, service_date, service_time,
            duration, address, notes, total_amount
        ))

        mysql.connection.commit()
        cursor.close()

        send_email(
            worker["email"],
            "New Service Booking Received",
            f"""Hello {worker['name']},

You have received a new service booking from {customer['name']}.

Customer phone: {customer['phone'] or 'Not provided'}
Service date: {service_date}
Service time: {service_time}
Duration: {duration} hours
Address: {address}
Notes: {notes or 'None'}
Total amount: Rs. {total_amount:.2f}
"""
        )

        send_email(
            customer["email"],
            "Booking Confirmation - Service Marketplace",
            f"""Hello {customer['name']},

Your booking with {worker['name']} has been received.

Service date: {service_date}
Service time: {service_time}
Duration: {duration} hours
Address: {address}
Total amount: Rs. {total_amount:.2f}

You will receive further updates as the worker processes your booking.
"""
        )

        flash("Booking created successfully!", "success")
        return redirect(url_for("user_bookings"))

    cursor.close()
    return render_template("book_service.html", worker=worker)


# --------------------------------------------------
# WORKER DASHBOARD
# --------------------------------------------------

@app.route("/worker/dashboard")
def worker_dashboard():
    if (
        not session.get("loggedin")
        or session.get("role") != "worker"
    ):
        return redirect(url_for("login"))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("""
        SELECT
            b.*,
            u.name AS user_name,
            u.phone AS user_phone
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        WHERE b.worker_id = %s
        ORDER BY b.created_at DESC
        LIMIT 5
    """, (session["id"],))

    recent_bookings = cursor.fetchall()

    cursor.execute(
        "SELECT COUNT(*) AS total FROM bookings WHERE worker_id=%s",
        (session["id"],)
    )
    total = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT COUNT(*) AS pending
        FROM bookings
        WHERE worker_id=%s AND status='pending'
    """, (session["id"],))
    pending = cursor.fetchone()["pending"]

    cursor.execute("""
        SELECT COUNT(*) AS completed
        FROM bookings
        WHERE worker_id=%s AND status='completed'
    """, (session["id"],))
    completed = cursor.fetchone()["completed"]

    cursor.execute("""
        SELECT SUM(total_amount) AS revenue
        FROM bookings
        WHERE worker_id=%s AND status='completed'
    """, (session["id"],))
    revenue = cursor.fetchone()["revenue"] or 0

    cursor.execute("""
        SELECT AVG(rating) AS avg_rating
        FROM bookings
        WHERE worker_id=%s AND rating IS NOT NULL
    """, (session["id"],))
    avg_rating = cursor.fetchone()["avg_rating"] or 0

    cursor.close()

    return render_template(
        "worker_dashboard.html",
        recent_bookings=recent_bookings,
        total=total,
        pending=pending,
        completed=completed,
        revenue=revenue,
        avg_rating=round(float(avg_rating), 1)
    )


@app.route("/worker/bookings")
def worker_bookings():
    if (
        not session.get("loggedin")
        or session.get("role") != "worker"
    ):
        return redirect(url_for("login"))

    status_filter = request.args.get("status", "")
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    query = """
        SELECT
            b.*,
            u.name AS user_name,
            u.phone AS user_phone,
            u.email AS user_email
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        WHERE b.worker_id = %s
    """

    params = [session["id"]]

    allowed_filters = {
        "pending", "confirmed", "in_progress",
        "completed", "cancelled"
    }

    if status_filter in allowed_filters:
        query += " AND b.status = %s"
        params.append(status_filter)
    else:
        status_filter = ""

    query += " ORDER BY b.created_at DESC"

    cursor.execute(query, params)
    bookings = cursor.fetchall()
    cursor.close()

    return render_template(
        "worker_bookings.html",
        bookings=bookings,
        status_filter=status_filter
    )


# --------------------------------------------------
# UPDATE BOOKING STATUS
# --------------------------------------------------

@app.route("/worker/update_booking/<int:booking_id>", methods=["POST"])
def update_booking_status(booking_id):
    if (
        not session.get("loggedin")
        or session.get("role") != "worker"
    ):
        return redirect(url_for("login"))

    status = request.form.get("status", "")
    allowed_statuses = {"confirmed", "in_progress", "cancelled"}

    if status not in allowed_statuses:
        flash("Invalid booking status.", "error")
        return redirect(url_for("worker_bookings"))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("""
        SELECT
            b.status,
            u.name AS customer_name,
            u.email AS customer_email,
            w.name AS worker_name
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        JOIN workers w ON b.worker_id = w.id
        WHERE b.id=%s AND b.worker_id=%s
    """, (booking_id, session["id"]))

    booking = cursor.fetchone()

    if not booking:
        cursor.close()
        flash("Booking not found.", "error")
        return redirect(url_for("worker_bookings"))

    if status == "confirmed":
        if booking["status"] != "pending":
            cursor.close()
            flash("Only pending bookings can be confirmed.", "error")
            return redirect(url_for("worker_bookings"))

        cursor.execute("""
            UPDATE bookings
            SET status='confirmed'
            WHERE id=%s AND worker_id=%s AND status='pending'
        """, (booking_id, session["id"]))

    elif status == "in_progress":
        if booking["status"] != "confirmed":
            cursor.close()
            flash("Only confirmed bookings can be started.", "error")
            return redirect(url_for("worker_bookings"))

        otp = str(secrets.randbelow(9000) + 1000)

        cursor.execute("""
            UPDATE bookings
            SET status='in_progress', otp=%s
            WHERE id=%s AND worker_id=%s AND status='confirmed'
        """, (otp, booking_id, session["id"]))

    else:
        if booking["status"] not in {"pending", "confirmed"}:
            cursor.close()
            flash("This booking cannot be cancelled now.", "error")
            return redirect(url_for("worker_bookings"))

        cursor.execute("""
            UPDATE bookings
            SET status='cancelled'
            WHERE id=%s AND worker_id=%s
        """, (booking_id, session["id"]))

    mysql.connection.commit()
    cursor.close()

    if status in {"confirmed", "in_progress"}:
        send_email(
            booking["customer_email"],
            f"Booking Status Updated: {status.replace('_', ' ').title()}",
            f"""Hello {booking['customer_name']},

Your booking with {booking['worker_name']} is now
{status.replace('_', ' ')}.

Please check your dashboard for the latest booking details.
"""
        )

    flash(f"Booking status updated to {status}!", "success")
    return redirect(url_for("worker_bookings"))


# --------------------------------------------------
# COMPLETE BOOKING WITH OTP
# --------------------------------------------------

@app.route("/complete_booking/<int:booking_id>", methods=["POST"])
def complete_booking(booking_id):
    if (
        not session.get("loggedin")
        or session.get("role") != "worker"
    ):
        return redirect(url_for("login"))

    submitted_otp = request.form.get("otp", "").strip()

    if not re.fullmatch(r"\d{4}", submitted_otp):
        flash("Please enter the 4-digit OTP.", "error")
        return redirect(url_for("worker_bookings"))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("""
        SELECT
            b.otp,
            u.name AS customer_name,
            u.email AS customer_email,
            w.name AS worker_name
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        JOIN workers w ON b.worker_id = w.id
        WHERE b.id=%s
          AND b.worker_id=%s
          AND b.status='in_progress'
    """, (booking_id, session["id"]))

    booking = cursor.fetchone()

    if (
        not booking
        or not booking["otp"]
        or not secrets.compare_digest(
            str(booking["otp"]), submitted_otp
        )
    ):
        cursor.close()
        flash("Incorrect OTP. The booking was not completed.", "error")
        return redirect(url_for("worker_bookings"))

    cursor.execute("""
        UPDATE bookings
        SET status='completed', otp=NULL
        WHERE id=%s
          AND worker_id=%s
          AND status='in_progress'
    """, (booking_id, session["id"]))

    mysql.connection.commit()
    cursor.close()

    send_email(
        booking["customer_email"],
        "Service Completed - Please Leave a Review",
        f"""Hello {booking['customer_name']},

Your service with {booking['worker_name']} has been completed.

Please visit your dashboard to rate the service and leave a review.
"""
    )

    flash("Booking completed successfully!", "success")
    return redirect(url_for("worker_bookings"))


# --------------------------------------------------
# EDIT WORKER PROFILE
# --------------------------------------------------

@app.route("/worker/profile", methods=["GET", "POST"])
def worker_edit_profile():
    if (
        not session.get("loggedin")
        or session.get("role") != "worker"
    ):
        return redirect(url_for("login"))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        category = request.form.get("category", "").strip()
        skills = request.form.get("skills", "").strip()
        hourly_rate = request.form.get("hourly_rate", "0")
        bio = request.form.get("bio", "").strip()
        is_available = 1 if request.form.get("is_available") else 0

        cursor.execute("""
            UPDATE workers
            SET name=%s,
                phone=%s,
                category=%s,
                skills=%s,
                hourly_rate=%s,
                bio=%s,
                is_available=%s
            WHERE id=%s
        """, (
            name, phone, category, skills,
            hourly_rate, bio, is_available, session["id"]
        ))

        mysql.connection.commit()
        session["name"] = name
        flash("Profile updated successfully!", "success")

    cursor.execute(
        "SELECT * FROM workers WHERE id=%s",
        (session["id"],)
    )
    worker = cursor.fetchone()
    cursor.close()

    return render_template(
        "worker_profile_edit.html",
        worker=worker
    )


# --------------------------------------------------
# RUN APPLICATION
# --------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)
