from flask import Flask, render_template, request, redirect
import sqlite3

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    # ---------- CREATE TABLES ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS vendor (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS product (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS purchase (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor TEXT,
            product TEXT,
            purchase_date TEXT,
            total_amount REAL,
            advance REAL,
            pending REAL
        )
    """)

    # ---------- HANDLE FORM ----------
    if request.method == "POST":

        # Add Vendor
        if request.form.get("new_vendor"):
            cur.execute(
                "INSERT INTO vendor (name) VALUES (?)",
                (request.form.get("new_vendor"),)
            )
            conn.commit()
            return redirect("/")

        # Add Product
        if request.form.get("new_product"):
            cur.execute(
                "INSERT INTO product (name) VALUES (?)",
                (request.form.get("new_product"),)
            )
            conn.commit()
            return redirect("/")

        # Add Purchase Entry
        vendor = request.form.get("vendor")
        product = request.form.get("product")
        purchase_date = request.form.get("purchase_date")
        total = float(request.form.get("total_amount"))
        advance = float(request.form.get("advance"))
        pending = total - advance

        cur.execute("""
            INSERT INTO purchase
            (vendor, product, purchase_date, total_amount, advance, pending)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (vendor, product, purchase_date, total, advance, pending))

        conn.commit()
        return redirect("/")

    # ---------- FETCH DATA ----------
    cur.execute("SELECT name FROM vendor")
    vendors = cur.fetchall()

    cur.execute("SELECT name FROM product")
    products = cur.fetchall()

    cur.execute("SELECT * FROM purchase")
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

