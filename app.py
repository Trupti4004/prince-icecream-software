from flask import Flask, render_template, request, redirect, session
import psycopg2, os
from decimal import Decimal
from datetime import date

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
            username TEXT,
            password TEXT
        )
    """)
    conn.commit()

    cur.execute("SELECT * FROM users")
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (username,password) VALUES (%s,%s)",
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

    # ---------- TABLES ----------
    cur.execute("""CREATE TABLE IF NOT EXISTS vendor (
        id SERIAL PRIMARY KEY, name TEXT)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS product (
        id SERIAL PRIMARY KEY, name TEXT)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS ice_cream_type (
        id SERIAL PRIMARY KEY, name TEXT)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS purchase (
        id SERIAL PRIMARY KEY,
        vendor TEXT,
        product TEXT,
        ice_cream_type TEXT,
        quantity NUMERIC,
        purchase_date DATE,
        total NUMERIC,
        advance NUMERIC,
        pending NUMERIC,
        status TEXT
    )""")
    conn.commit()

    # ---------- POST ----------
    if request.method == "POST":

        if request.form.get("new_vendor"):
            cur.execute("INSERT INTO vendor(name) VALUES(%s)",
                        (request.form["new_vendor"],))
            conn.commit()
            return redirect("/")

        if request.form.get("new_product"):
            cur.execute("INSERT INTO product(name) VALUES(%s)",
                        (request.form["new_product"],))
            conn.commit()
            return redirect("/")

        if request.form.get("new_type"):
            cur.execute("INSERT INTO ice_cream_type(name) VALUES(%s)",
                        (request.form["new_type"],))
            conn.commit()
            return redirect("/")

        if request.form.get("delete_id"):
            cur.execute("DELETE FROM purchase WHERE id=%s",
                        (request.form["delete_id"],))
            conn.commit()
            return redirect("/")

        if request.form.get("pay_id"):
            pid = int(request.form["pay_id"])
            received = Decimal(request.form["received"])
            cur.execute("SELECT pending FROM purchase WHERE id=%s", (pid,))
            old = Decimal(cur.fetchone()[0])
            new = old - received
            status = "Cleared" if new <= 0 else "Pending"
            new = max(new, 0)
            cur.execute("""
                UPDATE purchase SET pending=%s, status=%s WHERE id=%s
            """, (new, status, pid))
            conn.commit()
            return redirect("/")

        # Purchase entry
        total = Decimal(request.form["total"])
        adv = Decimal(request.form["advance"])
        qty = Decimal(request.form["quantity"])
        pending = total - adv
        status = "Cleared" if pending <= 0 else "Pending"

        cur.execute("""
            INSERT INTO purchase
            (vendor, product, ice_cream_type, quantity,
             purchase_date, total, advance, pending, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            request.form["vendor"],
            request.form["product"],
            request.form["ice_cream_type"],
            qty,
            request.form["date"],
            total, adv, pending, status
        ))
        conn.commit()
        return redirect("/")

    # ---------- FILTER ----------
    fv = request.args.get("filter_vendor")
    fd = request.args.get("from_date")
    td = request.args.get("to_date")

    q = "SELECT * FROM purchase WHERE 1=1"
    p = []

    if fv:
        q += " AND vendor=%s"
        p.append(fv)
    if fd and td:
        q += " AND purchase_date BETWEEN %s AND %s"
        p.extend([fd, td])

    # ---------- DASHBOARD ----------
    cur.execute("""
        SELECT COALESCE(SUM(total),0),
               COALESCE(SUM(advance),0),
               COALESCE(SUM(pending),0)
        FROM purchase
        WHERE DATE_TRUNC('month', purchase_date)
              = DATE_TRUNC('month', CURRENT_DATE)
    """)
    total, received, pending = cur.fetchone()

    # Ice cream type analysis
    cur.execute("""
        SELECT ice_cream_type, SUM(quantity)
        FROM purchase
        GROUP BY ice_cream_type
    """)
    type_sales = cur.fetchall()

    cur.execute("SELECT name FROM vendor")
    vendors = cur.fetchall()

    cur.execute("SELECT name FROM product")
    products = cur.fetchall()

    cur.execute("SELECT name FROM ice_cream_type")
    types = cur.fetchall()

    cur.execute(q + " ORDER BY id DESC", p)
    purchases = cur.fetchall()

    conn.close()

    return render_template(
        "index.html",
        vendors=vendors,
        products=products,
        types=types,
        purchases=purchases,
        total=total,
        received=received,
        pending=pending,
        type_sales=type_sales
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
