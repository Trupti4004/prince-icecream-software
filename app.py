from flask import Flask, render_template, request, redirect, session
import psycopg2, os
from decimal import Decimal

app = Flask(__name__)
app.secret_key = "prince_icecream_secret"

def get_db():
    return psycopg2.connect(os.environ["DATABASE_URL"], sslmode="require")

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT
        )
    """)
    conn.commit()

    # create default admin
    cur.execute("SELECT * FROM users")
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (username, password) VALUES (%s,%s)",
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

# ---------------- MAIN ----------------
@app.route("/", methods=["GET", "POST"])
def index():
    if "user" not in session:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    # tables
    cur.execute("""
        CREATE TABLE IF NOT EXISTS vendor (
            id SERIAL PRIMARY KEY,
            name TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS product (
            id SERIAL PRIMARY KEY,
            name TEXT,
            rate NUMERIC
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

    # -------- POST --------
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
                "INSERT INTO product(name, rate) VALUES(%s,%s)",
                (request.form["new_product"], request.form["rate"])
            )
            conn.commit()
            return redirect("/")

        if request.form.get("pay_id"):
            pid = request.form["pay_id"]
            received = Decimal(request.form["received"])
            cur.execute("SELECT pending FROM purchase WHERE id=%s", (pid,))
            old = Decimal(cur.fetchone()[0])
            new = max(old - received, 0)
            status = "Cleared" if new == 0 else "Pending"
            cur.execute(
                "UPDATE purchase SET pending=%s, status=%s WHERE id=%s",
                (new, status, pid)
            )
            conn.commit()
            return redirect("/")

        # purchase entry
        total = Decimal(request.form["total"])
        adv = Decimal(request.form["advance"])
        pending = total - adv
        status = "Cleared" if pending == 0 else "Pending"

        cur.execute("""
            INSERT INTO purchase
            (vendor, product, purchase_date, total, advance, pending, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (
            request.form["vendor"],
            request.form["product"],
            request.form["date"],
            total, adv, pending, status
        ))
        conn.commit()
        return redirect("/")

    # -------- DASHBOARD --------
    cur.execute("""
        SELECT
        COALESCE(SUM(total),0),
        COALESCE(SUM(advance),0),
        COALESCE(SUM(pending),0)
        FROM purchase
    """)
    total, received, pending = cur.fetchone()

    cur.execute("SELECT name FROM vendor")
    vendors = cur.fetchall()

    cur.execute("SELECT name, rate FROM product")
    products = cur.fetchall()

    cur.execute("SELECT * FROM purchase ORDER BY id DESC")
    purchases = cur.fetchall()

    conn.close()

    return render_template(
        "index.html",
        vendors=vendors,
        products=products,
        purchases=purchases,
        total=total,
        received=received,
        pending=pending
    )

if __name__ == "__main__":
    app.run()
