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

    # USERS TABLE
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT,
            password TEXT
        )
    """)
    conn.commit()

    # DEFAULT USER
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s)",
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

    # ---------- TABLE CREATION ----------
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
            product TEXT
        )
    """)
    conn.commit()

    # ---------- SAFE MIGRATIONS (VERY IMPORTANT) ----------
    cur.execute("ALTER TABLE product ADD COLUMN IF NOT EXISTS rate NUMERIC")
    cur.execute("ALTER TABLE purchase ADD COLUMN IF NOT EXISTS quantity NUMERIC")
    cur.execute("ALTER TABLE purchase ADD COLUMN IF NOT EXISTS rate NUMERIC")
    cur.execute("ALTER TABLE purchase ADD COLUMN IF NOT EXISTS amount NUMERIC")
    cur.execute("ALTER TABLE purchase ADD COLUMN IF NOT EXISTS purchase_date DATE")
    conn.commit()

    # ---------- POST ACTIONS ----------
    if request.method == "POST":

        # ADD VENDOR
        if request.form.get("new_vendor"):
            cur.execute(
                "INSERT INTO vendor (name) VALUES (%s)",
                (request.form["new_vendor"],)
            )
            conn.commit()
            return redirect("/")

        # DELETE VENDOR
        if request.form.get("delete_vendor"):
            cur.execute(
                "DELETE FROM vendor WHERE name=%s",
                (request.form["delete_vendor"],)
            )
            conn.commit()
            return redirect("/")

        # ADD PRODUCT
        if request.form.get("new_product"):
            cur.execute(
                "INSERT INTO product (name, rate) VALUES (%s, %s)",
                (request.form["new_product"], Decimal(request.form["rate"]))
            )
            conn.commit()
            return redirect("/")

        # DELETE PRODUCT
        if request.form.get("delete_product"):
            cur.execute(
                "DELETE FROM product WHERE name=%s",
                (request.form["delete_product"],)
            )
            conn.commit()
            return redirect("/")

        # ADD PURCHASE (MULTIPLE PRODUCTS PER VENDOR ALLOWED)
        qty = Decimal(request.form["quantity"])
        rate = Decimal(request.form["rate"])
        amount = qty * rate

        cur.execute("""
            INSERT INTO purchase
            (vendor, product, quantity, rate, amount, purchase_date)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            request.form["vendor"],
            request.form["product"],
            qty,
            rate,
            amount,
            request.form["date"]
        ))
        conn.commit()
        return redirect("/")

    # ---------- DASHBOARD ----------
    # TOTAL SOLD (ALL PRODUCTS)
    cur.execute("SELECT COALESCE(SUM(quantity),0) FROM purchase")
    total_sold = cur.fetchone()[0]

    # PRODUCT-WISE SOLD
    cur.execute("""
        SELECT product, COALESCE(SUM(quantity),0)
        FROM purchase
        GROUP BY product
    """)
    product_sales = cur.fetchall()

    # ---------- FETCH DATA ----------
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
        product_sales=product_sales,
        total_sold=total_sold
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
