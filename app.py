from flask import Flask, render_template, request, redirect, session
import psycopg2, os
from decimal import Decimal

app = Flask(__name__)
app.secret_key = "prince_icecream_secret"

def get_db():
    return psycopg2.connect(
        os.environ["DATABASE_URL"],
        sslmode="require"
    )

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT,
            password TEXT
        )
    """)
    conn.commit()

    # default admin user
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s)",
            ("admin", "admin123")
        )
        conn.commit()

    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]
        cur.execute(
            "SELECT * FROM users WHERE username=%s AND password=%s",
            (u, p)
        )
        if cur.fetchone():
            session["user"] = u
            conn.close()
            return redirect("/")

    conn.close()
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ---------------- MAIN PAGE ----------------
@app.route("/", methods=["GET", "POST"])
def index():
    if "user" not in session:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    # ---------- TABLES ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS vendor (
            id SERIAL PRIMARY KEY,
            name TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS product (
            id SERIAL PRIMARY KEY,
            name TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS purchase (
            id SERIAL PRIMARY KEY,
            vendor TEXT,
            product TEXT,
            purchase_date DATE,
            total NUMERIC,
            advance NUMERIC,
            pending NUMERIC,
            status TEXT
        )
    """)
    conn.commit()

    # ---------- POST ACTIONS ----------
    if request.method == "POST":

        if request.form.get("new_vendor"):
            cur.execute(
                "INSERT INTO vendor(name) VALUES(%s)",
                (request.form["new_vendor"],)
            )
            conn.commit()
            return redirect("/")

        if request.form.get("new_product"):
            cur.execute(
                "INSERT INTO product(name) VALUES(%s)",
                (request.form["new_product"],)
            )
            conn.commit()
            return redirect("/")

        if request.form.get("delete_id"):
            cur.execute(
                "DELETE FROM purchase WHERE id=%s",
                (request.form["delete_id"],)
            )
            conn.commit()
            return redirect("/")

        if request.form.get("pay_id"):
            pid = int(request.form["pay_id"])
            received = Decimal(request.form["received"])
            cur.execute("SELECT pending FROM purchase WHERE id=%s", (pid,))
            old_pending = Decimal(cur.fetchone()[0])
            new_pending = old_pending - received
            status = "Cleared" if new_pending <= 0 else "Pending"
            new_pending = max(new_pending, 0)
            cur.execute(
                "UPDATE purchase SET pending=%s, status=%s WHERE id=%s",
                (new_pending, status, pid)
            )
            conn.commit()
            return redirect("/")

        # Purchase entry
        total = Decimal(request.form["total"])
        advance = Decimal(request.form["advance"])
        pending = total - advance
        status = "Cleared" if pending <= 0 else "Pending"

        cur.execute("""
            INSERT INTO purchase
            (vendor, product, purchase_date, total, advance, pending, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (
            request.form["vendor"],
            request.form["product"],
            request.form["date"],
            total, advance, pending, status
        ))
        conn.commit()
        return redirect("/")

    # ---------- DASHBOARD ----------
    cur.execute("""
        SELECT
            COALESCE(SUM(total),0),
            COALESCE(SUM(advance),0),
            COALESCE(SUM(pending),0)
        FROM purchase
        WHERE DATE_TRUNC('month', purchase_date)
              = DATE_TRUNC('month', CURRENT_DATE)
    """)
    total_sum, received_sum, pending_sum = cur.fetchone()

    # ---------- FETCH DATA ----------
    cur.execute("SELECT name FROM vendor")
    vendors = cur.fetchall()

    cur.execute("SELECT name FROM product")
    products = cur.fetchall()

    cur.execute("SELECT * FROM purchase ORDER BY id DESC")
    purchases = cur.fetchall()

    conn.close()

    return render_template(
        "index.html",
        vendors=vendors,
        products=products,
        purchases=purchases,
        total=total_sum,
        received=received_sum,
        pending=pending_sum
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
