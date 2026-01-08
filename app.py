from flask import Flask, render_template, request, redirect, session
import psycopg2, os
from decimal import Decimal

app = Flask(__name__)
app.secret_key = "secret123"

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

    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO users(username,password) VALUES(%s,%s)",
            ("admin", "admin123")
        )
        conn.commit()

    if request.method == "POST":
        cur.execute(
            "SELECT * FROM users WHERE username=%s AND password=%s",
            (request.form["username"], request.form["password"])
        )
        if cur.fetchone():
            session["user"] = request.form["username"]
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

    # ---------- TABLES ----------
    cur.execute("CREATE TABLE IF NOT EXISTS vendor(id SERIAL PRIMARY KEY, name TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS product(id SERIAL PRIMARY KEY, name TEXT)")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS rate_master(
            id SERIAL PRIMARY KEY,
            product TEXT,
            rate NUMERIC
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sales(
            id SERIAL PRIMARY KEY,
            vendor TEXT,
            product TEXT,
            quantity NUMERIC,
            rate NUMERIC,
            total NUMERIC,
            paid NUMERIC DEFAULT 0,
            pending NUMERIC,
            sale_date DATE,
            status TEXT
        )
    """)
    conn.commit()

    # ---------- POST ----------
    if request.method == "POST":

        if request.form.get("new_vendor"):
            cur.execute("INSERT INTO vendor(name) VALUES(%s)", (request.form["new_vendor"],))
            conn.commit()
            return redirect("/")

        if request.form.get("new_product"):
            cur.execute("INSERT INTO product(name) VALUES(%s)", (request.form["new_product"],))
            conn.commit()
            return redirect("/")

        if request.form.get("rate_product"):
            cur.execute(
                "INSERT INTO rate_master(product,rate) VALUES(%s,%s)",
                (request.form["rate_product"], request.form["rate"])
            )
            conn.commit()
            return redirect("/")

        if request.form.get("delete_id"):
            cur.execute("DELETE FROM sales WHERE id=%s", (request.form["delete_id"],))
            conn.commit()
            return redirect("/")

        if request.form.get("pay_id"):
            cur.execute("SELECT pending FROM sales WHERE id=%s", (request.form["pay_id"],))
            old = cur.fetchone()[0]
            received = Decimal(request.form["received"])
            new_pending = old - received
            status = "Cleared" if new_pending <= 0 else "Pending"

            cur.execute("""
                UPDATE sales
                SET paid = paid + %s,
                    pending = %s,
                    status = %s
                WHERE id = %s
            """, (received, max(new_pending,0), status, request.form["pay_id"]))
            conn.commit()
            return redirect("/")

        # SALE ENTRY
        cur.execute(
            "SELECT rate FROM rate_master WHERE product=%s",
            (request.form["product"],)
        )
        rate = cur.fetchone()[0]

        qty = Decimal(request.form["quantity"])
        total = qty * rate
        paid = Decimal(request.form["paid"])
        pending = total - paid
        status = "Cleared" if pending == 0 else "Pending"

        cur.execute("""
            INSERT INTO sales
            (vendor,product,quantity,rate,total,paid,pending,sale_date,status)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            request.form["vendor"],
            request.form["product"],
            qty, rate, total,
            paid, pending,
            request.form["date"],
            status
        ))
        conn.commit()
        return redirect("/")

    # ---------- FILTER ----------
    fv = request.args.get("vendor")
    fd = request.args.get("from")
    td = request.args.get("to")

    where = "WHERE 1=1"
    params = []

    if fv:
        where += " AND vendor=%s"
        params.append(fv)
    if fd and td:
        where += " AND sale_date BETWEEN %s AND %s"
        params.extend([fd, td])

    cur.execute(
        "SELECT COALESCE(SUM(total),0), COALESCE(SUM(paid),0), COALESCE(SUM(pending),0) FROM sales " + where,
        params
    )
    total_amt, received_amt, pending_amt = cur.fetchone()

    cur.execute("SELECT * FROM sales " + where + " ORDER BY id DESC", params)
    sales = cur.fetchall()

    cur.execute("SELECT name FROM vendor")
    vendors = cur.fetchall()

    cur.execute("SELECT name FROM product")
    products = cur.fetchall()

    conn.close()

    return render_template(
        "index.html",
        vendors=vendors,
        products=products,
        sales=sales,
        total_amt=total_amt,
        received_amt=received_amt,
        pending_amt=pending_amt
    )

if __name__ == "__main__":
    app.run()
