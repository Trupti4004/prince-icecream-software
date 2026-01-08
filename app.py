from flask import Flask, render_template, request, redirect, session
import psycopg2, os
from decimal import Decimal
import json

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
        CREATE TABLE IF NOT EXISTS users(
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
        CREATE TABLE IF NOT EXISTS vendor(
            id SERIAL PRIMARY KEY,
            name TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS product(
            id SERIAL PRIMARY KEY,
            name TEXT,
            rate NUMERIC
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS purchase(
            id SERIAL PRIMARY KEY,
            vendor TEXT,
            purchase_date DATE,
            total_amount NUMERIC
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS purchase_item(
            id SERIAL PRIMARY KEY,
            purchase_id INTEGER,
            product TEXT,
            quantity NUMERIC,
            rate NUMERIC,
            amount NUMERIC
        )
    """)
    conn.commit()

    # ---------- POST ----------
    if request.method == "POST" and request.form.get("items_json"):
        items = json.loads(request.form["items_json"])
        vendor = request.form["vendor"]
        date = request.form["date"]

        total = sum(Decimal(i["amount"]) for i in items)

        cur.execute("""
            INSERT INTO purchase(vendor,purchase_date,total_amount)
            VALUES(%s,%s,%s) RETURNING id
        """, (vendor, date, total))
        purchase_id = cur.fetchone()[0]

        for i in items:
            cur.execute("""
                INSERT INTO purchase_item
                (purchase_id,product,quantity,rate,amount)
                VALUES(%s,%s,%s,%s,%s)
            """, (
                purchase_id,
                i["product"],
                i["quantity"],
                i["rate"],
                i["amount"]
            ))

        conn.commit()
        return redirect("/")

    # ---------- FETCH ----------
    cur.execute("SELECT name FROM vendor")
    vendors = cur.fetchall()

    cur.execute("SELECT name, rate FROM product")
    products = cur.fetchall()

    # ✅ SAFE QUERY (NO INTERNAL ERROR)
    cur.execute("""
        SELECT
            p.id,
            p.vendor,
            p.purchase_date,
            p.total_amount,
            COALESCE(
                json_agg(
                    json_build_object(
                        'product', pi.product,
                        'quantity', pi.quantity,
                        'rate', pi.rate,
                        'amount', pi.amount
                    )
                ) FILTER (WHERE pi.id IS NOT NULL),
                '[]'
            )
        FROM purchase p
        LEFT JOIN purchase_item pi ON p.id = pi.purchase_id
        GROUP BY p.id
        ORDER BY p.id DESC
    """)
    purchases = cur.fetchall()

    conn.close()

    return render_template(
        "index.html",
        vendors=vendors,
        products=products,
        purchases=purchases
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
