from flask import Flask, render_template, request, redirect
import psycopg2
import os

app = Flask(__name__)

def get_db_connection():
    return psycopg2.connect(
        os.environ["DATABASE_URL"],
        sslmode="require"
    )


@app.route("/", methods=["GET", "POST"])
def index():
    conn = get_db_connection()
    cur = conn.cursor()

    # ---------- CREATE TABLES ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS vendor (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS product (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS purchase (
            id SERIAL PRIMARY KEY,
            vendor TEXT,
            product TEXT,
            purchase_date DATE,
            total_amount NUMERIC,
            advance NUMERIC,
            pending NUMERIC,
            status TEXT
        )
    """)

    conn.commit()

    # ---------- HANDLE POST ----------
    if request.method == "POST":

        # Add Vendor
        if request.form.get("new_vendor"):
            cur.execute(
                "INSERT INTO vendor (name) VALUES (%s)",
                (request.form.get("new_vendor"),)
            )
            conn.commit()
            return redirect("/")

        # Add Product
        if request.form.get("new_product"):
            cur.execute(
                "INSERT INTO product (name) VALUES (%s)",
                (request.form.get("new_product"),)
            )
            conn.commit()
            return redirect("/")

        # Update Payment
        if request.form.get("pay_id"):
            pay_id = int(request.form.get("pay_id"))
            received = float(request.form.get("received_amount"))

            cur.execute("SELECT pending FROM purchase WHERE id=%s", (pay_id,))
            old_pending = cur.fetchone()[0]

            new_pending = old_pending - received
            if new_pending <= 0:
                new_pending = 0
                status = "Cleared"
            else:
                status = "Pending"

            cur.execute("""
                UPDATE purchase
                SET pending=%s, status=%s
                WHERE id=%s
            """, (new_pending, status, pay_id))

            conn.commit()
            return redirect("/")

        # Add Purchase Entry
        vendor = request.form.get("vendor")
        product = request.form.get("product")
        purchase_date = request.form.get("purchase_date")
        total = float(request.form.get("total_amount"))
        advance = float(request.form.get("advance"))

        pending = total - advance
        status = "Cleared" if pending == 0 else "Pending"

        cur.execute("""
            INSERT INTO purchase
            (vendor, product, purchase_date, total_amount, advance, pending, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (vendor, product, purchase_date, total, advance, pending, status))

        conn.commit()
        return redirect("/")

    # ---------- FILTER ----------
    filter_vendor = request.args.get("filter_vendor")
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")

    query = "SELECT * FROM purchase WHERE 1=1"
    params = []

    if filter_vendor:
        query += " AND vendor=%s"
        params.append(filter_vendor)

    if from_date and to_date:
        query += " AND purchase_date BETWEEN %s AND %s"
        params.extend([from_date, to_date])

    # ---------- FETCH DATA ----------
    cur.execute("SELECT name FROM vendor")
    vendors = cur.fetchall()

    cur.execute("SELECT name FROM product")
    products = cur.fetchall()

    cur.execute(query, params)
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
