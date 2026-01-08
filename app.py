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
            username TEXT,
            password TEXT
        )
    """)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO users (username,password) VALUES (%s,%s)",
            ("admin","admin123")
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
        CREATE TABLE IF NOT EXISTS rate_master (
            id SERIAL PRIMARY KEY,
            product TEXT,
            rate NUMERIC
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS purchase (
            id SERIAL PRIMARY KEY,
            vendor TEXT,
            product TEXT,
            quantity NUMERIC,
            rate NUMERIC,
            purchase_date DATE
        )
    """)
    conn.commit()

    # ---------- POST ----------
    if request.method == "POST":

        # ADD VENDOR
        if request.form.get("new_vendor"):
            cur.execute("INSERT INTO vendor(name) VALUES(%s)",
                        (request.form["new_vendor"],))
            conn.commit()
            return redirect("/")

        # DELETE VENDOR
        if request.form.get("delete_vendor_id"):
            cur.execute("DELETE FROM vendor WHERE id=%s",
                        (request.form["delete_vendor_id"],))
            conn.commit()
            return redirect("/")

        # ADD PRODUCT
        if request.form.get("new_product"):
            cur.execute("INSERT INTO product(name) VALUES(%s)",
                        (request.form["new_product"],))
            conn.commit()
            return redirect("/")

        # DELETE PRODUCT
        if request.form.get("delete_product_id"):
            cur.execute("DELETE FROM product WHERE id=%s",
                        (request.form["delete_product_id"],))
            conn.commit()
            return redirect("/")

        # ADD RATE
        if request.form.get("rate_product"):
            cur.execute("""
                INSERT INTO rate_master(product,rate)
                VALUES(%s,%s)
            """, (
                request.form["rate_product"],
                Decimal(request.form["rate"])
            ))
            conn.commit()
            return redirect("/")

        # DELETE RATE
        if request.form.get("delete_rate_id"):
            cur.execute("DELETE FROM rate_master WHERE id=%s",
                        (request.form["delete_rate_id"],))
            conn.commit()
            return redirect("/")

        # ADD PURCHASE ENTRY
        cur.execute(
            "SELECT rate FROM rate_master WHERE product=%s",
            (request.form["product"],)
        )
        rate = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO purchase
            (vendor,product,quantity,rate,purchase_date)
            VALUES(%s,%s,%s,%s,%s)
        """, (
            request.form["vendor"],
            request.form["product"],
            Decimal(request.form["quantity"]),
            rate,
            request.form["date"]
        ))
        conn.commit()
        return redirect("/")

    # ---------- FILTER ----------
    filter_vendor = request.args.get("filter_vendor")
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")

    base = "FROM purchase WHERE 1=1"
    params = []

    if filter_vendor:
        base += " AND vendor=%s"
        params.append(filter_vendor)

    if from_date and to_date:
        base += " AND purchase_date BETWEEN %s AND %s"
        params.extend([from_date, to_date])

    # ---------- CARDS ----------
    cur.execute("SELECT COALESCE(SUM(quantity),0) " + base, params)
    total_sold = cur.fetchone()[0]

    cur.execute("""
        SELECT product, COALESCE(SUM(quantity),0)
        """ + base + " GROUP BY product", params)
    product_sales = cur.fetchall()

    # ---------- FETCH ----------
    cur.execute("SELECT id,name FROM vendor")
    vendors = cur.fetchall()

    cur.execute("SELECT id,name FROM product")
    products = cur.fetchall()

    cur.execute("SELECT id,product,rate FROM rate_master")
    rates = cur.fetchall()

    cur.execute("SELECT * " + base + " ORDER BY id DESC", params)
    purchases = cur.fetchall()

    conn.close()

    return render_template(
        "index.html",
        vendors=vendors,
        products=products,
        rates=rates,
        purchases=purchases,
        total_sold=total_sold,
        product_sales=product_sales
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
