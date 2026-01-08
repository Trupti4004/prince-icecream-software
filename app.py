from flask import Flask, render_template, request, redirect
import psycopg2, os
from decimal import Decimal
from datetime import date

app = Flask(__name__)

def get_db():
    return psycopg2.connect(os.environ["DATABASE_URL"], sslmode="require")

@app.route("/", methods=["GET", "POST"])
def index():
    conn = get_db()
    cur = conn.cursor()

    # ---------- TABLES ----------
    cur.execute("""CREATE TABLE IF NOT EXISTS vendor(
        id SERIAL PRIMARY KEY, name TEXT)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS product(
        id SERIAL PRIMARY KEY, name TEXT)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS rate_master(
        id SERIAL PRIMARY KEY, product TEXT, rate NUMERIC)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS sales(
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
    )""")
    conn.commit()

    # ---------- POST ----------
    if request.method == "POST":

        # Masters
        if request.form.get("new_vendor"):
            cur.execute("INSERT INTO vendor(name) VALUES(%s)", (request.form["new_vendor"],))
            conn.commit()
            return redirect("/")

        if request.form.get("new_product"):
            cur.execute("INSERT INTO product(name) VALUES(%s)", (request.form["new_product"],))
            conn.commit()
            return redirect("/")

        if request.form.get("rate_product"):
            cur.execute("INSERT INTO rate_master(product,rate) VALUES(%s,%s)",
                        (request.form["rate_product"], request.form["rate"]))
            conn.commit()
            return redirect("/")

        # Delete master
        if request.form.get("delete_vendor"):
            cur.execute("DELETE FROM vendor WHERE id=%s", (request.form["delete_vendor"],))
            conn.commit()
            return redirect("/")

        if request.form.get("delete_product"):
            cur.execute("DELETE FROM product WHERE id=%s", (request.form["delete_product"],))
            conn.commit()
            return redirect("/")

        # Sale entry
        if request.form.get("vendor") and request.form.get("product"):
            cur.execute("SELECT rate FROM rate_master WHERE product=%s",
                        (request.form["product"],))
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

        # Update payment
        if request.form.get("pay_id"):
            cur.execute("SELECT pending FROM sales WHERE id=%s", (request.form["pay_id"],))
            old = cur.fetchone()[0]
            received = Decimal(request.form["received"])
            new_pending = old - received
            status = "Cleared" if new_pending <= 0 else "Pending"

            cur.execute("""
                UPDATE sales SET
                paid = paid + %s,
                pending = %s,
                status = %s
                WHERE id=%s
            """, (received, max(new_pending,0), status, request.form["pay_id"]))
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

    # Cards
    cur.execute("SELECT COALESCE(SUM(total),0), COALESCE(SUM(paid),0), COALESCE(SUM(pending),0) FROM sales " + where, params)
    total_amt, received_amt, pending_amt = cur.fetchone()

    # Product monthly qty
    cur.execute("""
        SELECT product, COALESCE(SUM(quantity),0)
        FROM sales
        """ + where + " GROUP BY product", params)
    product_qty = cur.fetchall()

    # Vendor-wise data
    cur.execute("SELECT * FROM sales " + where + " ORDER BY vendor")
    sales = cur.fetchall()

    cur.execute("SELECT id,name FROM vendor")
    vendors = cur.fetchall()

    cur.execute("SELECT id,name FROM product")
    products = cur.fetchall()

    cur.execute("SELECT * FROM rate_master")
    rates = cur.fetchall()

    conn.close()

    return render_template(
        "index.html",
        vendors=vendors,
        products=products,
        rates=rates,
        sales=sales,
        total_amt=total_amt,
        received_amt=received_amt,
        pending_amt=pending_amt,
        product_qty=product_qty
    )

if __name__ == "__main__":
    app.run()
