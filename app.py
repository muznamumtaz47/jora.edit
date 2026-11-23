
from flask import (
    Flask, request, jsonify, send_from_directory,
    session, redirect, url_for, render_template_string, abort
)

from functools import wraps
from email.message import EmailMessage
from datetime import datetime
from werkzeug.utils import secure_filename

import sqlite3
import smtplib
import json
import os
import re
import secrets
import uuid
from dotenv import load_dotenv


# =========================================
# APP SETTINGS
# =========================================

# Load environment variables from .env file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

app = Flask(__name__)

app.secret_key = (
    os.environ.get("JORA_SECRET_KEY")
    or secrets.token_hex(32)
)

app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

ADMIN_USERNAME = os.environ.get("JORA_ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("JORA_ADMIN_PASSWORD")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "jora_orders.db")

# Payment screenshots are stored outside public website files.
PAYMENT_PROOF_DIR = os.path.join(BASE_DIR, "payment_proofs")
os.makedirs(PAYMENT_PROOF_DIR, exist_ok=True)

SHIPPING_CHARGES = 300

PRODUCT_CATALOG = {
    "GULRUKH": 8490,
    "RAQS": 17490,
    "ANDAAZ": 9890
}
ALLOWED_PAYMENT_METHODS = [
    "Bank Transfer",
    "NayaPay Personal Transfer"
]

ALLOWED_PAYMENT_PREFERENCES = [
    "50% Advance",
    "Full Payment"
]


# =========================================
# DATABASE CONNECTION
# =========================================

def get_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


# =========================================
# CREATE DATABASE AND MIGRATIONS
# =========================================

def create_database():

    connection = get_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT,
            city TEXT NOT NULL,
            address TEXT NOT NULL,
            payment_method TEXT NOT NULL,
            products TEXT NOT NULL,
            order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'Pending',
            subtotal INTEGER NOT NULL DEFAULT 0,
            shipping INTEGER NOT NULL DEFAULT 300,
            advance INTEGER NOT NULL DEFAULT 0,
            remaining INTEGER NOT NULL DEFAULT 0,
            delivery_amount INTEGER NOT NULL DEFAULT 0,
            total INTEGER NOT NULL DEFAULT 0,
            payment_status TEXT NOT NULL DEFAULT 'Pending Verification',
            email_sent_at TEXT DEFAULT NULL
        )
    """)

    columns = connection.execute(
        "PRAGMA table_info(orders)"
    ).fetchall()

    column_names = [column["name"] for column in columns]

    migrations = {
        "status": "TEXT NOT NULL DEFAULT 'Pending'",
        "subtotal": "INTEGER NOT NULL DEFAULT 0",
        "shipping": "INTEGER NOT NULL DEFAULT 300",
        "advance": "INTEGER NOT NULL DEFAULT 0",
        "remaining": "INTEGER NOT NULL DEFAULT 0",
        "delivery_amount": "INTEGER NOT NULL DEFAULT 0",
        "total": "INTEGER NOT NULL DEFAULT 0",
        "payment_status": "TEXT NOT NULL DEFAULT 'Pending Verification'",
        "email_sent_at": "TEXT DEFAULT NULL",
        "payment_preference": "TEXT NOT NULL DEFAULT '50% Advance'",
        "transaction_id": "TEXT DEFAULT NULL",
        "payment_proof": "TEXT DEFAULT NULL"
    }

    for column_name, definition in migrations.items():

        if column_name not in column_names:
            connection.execute(
                f"ALTER TABLE orders ADD COLUMN {column_name} {definition}"
            )

    connection.execute("""
        CREATE TABLE IF NOT EXISTS subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            subscription_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.commit()
    connection.close()


# =========================================
# SEND ORDER CONFIRMATION EMAIL
# =========================================

def send_confirmation_email(order_id):

    connection = get_connection()

    try:

        order = connection.execute(
            "SELECT * FROM orders WHERE id = ?",
            (order_id,)
        ).fetchone()

        if not order:
            return

        if (
            order["status"] != "Confirmed"
            or order["payment_status"] != "Verified"
            or not order["email"]
            or order["email_sent_at"]
        ):
            return

        sender = os.environ.get("JORA_EMAIL_ADDRESS")
        password = os.environ.get("JORA_EMAIL_APP_PASSWORD")

        if not sender or not password:
            print("Email not sent: Gmail settings are missing.")
            return

        message = EmailMessage()

        message["Subject"] = (
            f"Your JORA.EDIT Order #{order_id} is Confirmed"
        )

        message["From"] = sender
        message["To"] = order["email"]

        if order["payment_preference"] == "Full Payment":
            payment_message = (
                f"Full Payment Received: PKR {order['advance']:,}\n"
                "Remaining on Delivery: PKR 0"
            )
        else:
            payment_message = (
                f"Advance Payment: PKR {order['advance']:,}\n"
                f"Remaining on Delivery: PKR {order['delivery_amount']:,}"
            )

        message.set_content(f"""
Hello {order['customer_name']},

Thank you for choosing JORA.EDIT!

Your payment has been verified and your order is confirmed.

Order Number: #{order_id}

Order Total: PKR {order['total']:,}

{payment_message}

We will keep you updated about your order.

ROOTED IN TRADITION, MADE FOR TODAY.

JORA.EDIT
""")

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.send_message(message)

        connection.execute(
            "UPDATE orders SET email_sent_at = ? WHERE id = ?",
            (datetime.now().isoformat(), order_id)
        )

        connection.commit()

        print(f"Confirmation email sent for order #{order_id}")

    except Exception as error:
        print("Email sending failed:", error)

    finally:
        connection.close()


# =========================================
# WEBSITE HOME
# =========================================

@app.route("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


# =========================================
# SERVE WEBSITE FILES
# =========================================

@app.route("/<path:filename>")
def website_files(filename):

    allowed_extensions = (
        ".html", ".css", ".js", ".png", ".jpg",
        ".jpeg", ".webp", ".svg", ".woff", ".woff2"
    )

    if not filename.lower().endswith(allowed_extensions):
        return "File not found", 404

    return send_from_directory(BASE_DIR, filename)


# =========================================
# SERVER-SIDE ORDER CALCULATION
# =========================================

def calculate_order(products, payment_preference):

    if not isinstance(products, list) or not products:
        raise ValueError("Your shopping bag is empty.")

    if payment_preference not in ALLOWED_PAYMENT_PREFERENCES:
        raise ValueError("Please select a valid payment preference.")

    subtotal = 0
    verified_products = []

    for product in products:

        if not isinstance(product, dict):
            raise ValueError("Invalid product information.")

        product_name = str(
            product.get("name", "")
        ).strip().upper()

        if product_name not in PRODUCT_CATALOG:
            raise ValueError(
                f"{product_name or 'This product'} is currently unavailable."
            )

        quantity = product.get("quantity", 1)

        if isinstance(quantity, bool) or not isinstance(quantity, int):
            raise ValueError("Invalid product quantity.")

        if quantity < 1 or quantity > 20:
            raise ValueError("Product quantity must be between 1 and 20.")

        size = str(product.get("size", "")).strip()

        if not size:
            raise ValueError("Please select a product size.")

        price = PRODUCT_CATALOG[product_name]
        product_total = price * quantity
        subtotal += product_total

        verified_products.append({
            "name": product_name.title(),
            "size": size,
            "quantity": quantity,
            "price": f"PKR {price:,}",
            "unit_price": price,
            "product_total": product_total
        })

    shipping = SHIPPING_CHARGES
    total = subtotal + shipping

    if payment_preference == "Full Payment":

        advance = total
        remaining = 0
        delivery_amount = 0

    else:

        advance = round(subtotal / 2)
        remaining = subtotal - advance
        delivery_amount = remaining + shipping

    return {
        "products": verified_products,
        "subtotal": subtotal,
        "shipping": shipping,
        "advance": advance,
        "remaining": remaining,
        "delivery_amount": delivery_amount,
        "total": total
    }


# =========================================
# VALIDATE PAYMENT SCREENSHOT
# =========================================

def validate_payment_screenshot(file):

    if not file or not file.filename:
        raise ValueError("Please upload your payment screenshot.")

    if file.content_length and file.content_length > 5 * 1024 * 1024:
        raise ValueError("Screenshot must be smaller than 5 MB.")

    extension = os.path.splitext(file.filename)[1].lower()

    if extension not in [".jpg", ".jpeg", ".png", ".webp"]:
        raise ValueError("Only JPG, PNG and WEBP screenshots are allowed.")

    file_bytes = file.read()

    if not file_bytes:
        raise ValueError("The uploaded screenshot is empty.")

    if len(file_bytes) > 5 * 1024 * 1024:
        raise ValueError("Screenshot must be smaller than 5 MB.")

    valid_image = (
        file_bytes.startswith(b"\xff\xd8\xff")
        or file_bytes.startswith(b"\x89PNG\r\n\x1a\n")
        or (
            file_bytes.startswith(b"RIFF")
            and file_bytes[8:12] == b"WEBP"
        )
    )

    if not valid_image:
        raise ValueError("The uploaded file is not a valid image.")

    return file_bytes, extension


# =========================================
# RECEIVE CUSTOMER ORDER
# =========================================

@app.route("/api/place-order", methods=["POST"])
def place_order():

    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip()
    city = request.form.get("city", "").strip()
    address = request.form.get("address", "").strip()

    payment = request.form.get("payment_method", "").strip()
    payment_preference = request.form.get(
        "payment_preference", ""
    ).strip()

    transaction_id = request.form.get(
        "transaction_id", ""
    ).strip()

    try:
        products = json.loads(request.form.get("products", "[]"))

    except (json.JSONDecodeError, TypeError):
        return jsonify({
            "success": False,
            "message": "Invalid product information."
        }), 400

    if not all([name, phone, city, address]):
        return jsonify({
            "success": False,
            "message": "Please complete all required delivery fields."
        }), 400

    if not re.fullmatch(r"[0-9+\-\s()]{10,20}", phone):
        return jsonify({
            "success": False,
            "message": "Please enter a valid phone number."
        }), 400

    if email and not re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+",
        email
    ):
        return jsonify({
            "success": False,
            "message": "Please enter a valid email address."
        }), 400

    if payment not in ALLOWED_PAYMENT_METHODS:
        return jsonify({
            "success": False,
            "message": "Please select a valid payment method."
        }), 400

    if payment_preference not in ALLOWED_PAYMENT_PREFERENCES:
        return jsonify({
            "success": False,
            "message": "Please select 50% Advance or Full Payment."
        }), 400

    if not transaction_id or len(transaction_id) > 100:
        return jsonify({
            "success": False,
            "message": "Please enter a valid transaction ID."
        }), 400

    try:
        amounts = calculate_order(products, payment_preference)

        screenshot = request.files.get("payment_screenshot")

        image_bytes, extension = validate_payment_screenshot(screenshot)

    except ValueError as error:
        return jsonify({
            "success": False,
            "message": str(error)
        }), 400

    # Generate a random, safe filename.
    proof_filename = secrets.token_hex(16) + extension
    proof_path = os.path.join(PAYMENT_PROOF_DIR, proof_filename)

    connection = get_connection()

    try:

        # Save uploaded proof in the private folder.
        with open(proof_path, "wb") as image_file:
            image_file.write(image_bytes)

        cursor = connection.execute("""
            INSERT INTO orders (
                customer_name,
                phone,
                email,
                city,
                address,
                payment_method,
                products,
                status,
                subtotal,
                shipping,
                advance,
                remaining,
                delivery_amount,
                total,
                payment_status,
                payment_preference,
                transaction_id,
                payment_proof
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name,
            phone,
            email,
            city,
            address,
            payment,
            json.dumps(amounts["products"]),
            "Pending",
            amounts["subtotal"],
            amounts["shipping"],
            amounts["advance"],
            amounts["remaining"],
            amounts["delivery_amount"],
            amounts["total"],
            "Pending Verification",
            payment_preference,
            transaction_id,
            proof_filename
        ))

        order_id = cursor.lastrowid

        connection.commit()

    except Exception as error:

        connection.rollback()
        print("Order database error:", error)

        if os.path.exists(proof_path):
            os.remove(proof_path)

        return jsonify({
            "success": False,
            "message": "Unable to save your order. Please try again."
        }), 500

    finally:
        connection.close()

    return jsonify({
        "success": True,
        "message": "Your order has been received!",
        "order_id": order_id,
        "advance": amounts["advance"],
        "total": amounts["total"],
        "delivery_amount": amounts["delivery_amount"],
        "payment_method": payment,
        "payment_preference": payment_preference
    })


# =========================================
# SAVE NEWSLETTER SUBSCRIPTION
# =========================================

@app.route("/api/subscribe", methods=["POST"])
def subscribe():

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "Invalid request."
        }), 400

    email = data.get("email", "")

    if not isinstance(email, str):
        return jsonify({
            "success": False,
            "message": "Please enter a valid email."
        }), 400

    email = email.strip().lower()

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return jsonify({
            "success": False,
            "message": "Please enter a valid email address."
        }), 400

    connection = get_connection()

    try:

        connection.execute(
            "INSERT INTO subscribers (email) VALUES (?)",
            (email,)
        )

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Thank you for subscribing to JORA.EDIT!"
        })

    except sqlite3.IntegrityError:

        return jsonify({
            "success": True,
            "message": "You are already subscribed!"
        })

    finally:
        connection.close()


# =========================================
# ADMIN LOGIN REQUIRED
# =========================================

def admin_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))

        return function(*args, **kwargs)

    return wrapper


# =========================================
# ADMIN LOGIN PAGE
# =========================================

@app.route("/admin", methods=["GET", "POST"])
def admin_login():

    if session.get("admin_logged_in"):
        return redirect(url_for("admin_dashboard"))

    error = ""

    if request.method == "POST":

        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if not ADMIN_USERNAME or not ADMIN_PASSWORD:
            error = "Admin credentials are not configured."

        elif (
            secrets.compare_digest(username, ADMIN_USERNAME)
            and secrets.compare_digest(password, ADMIN_PASSWORD)
        ):
            session["admin_logged_in"] = True
            return redirect(url_for("admin_dashboard"))

        else:
            error = "Incorrect username or password."

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>JORA.EDIT Admin Login</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {
                background: #f8f7f3;
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
            }
            .login-box {
                background: white;
                padding: 40px;
                width: 300px;
                max-width: calc(100% - 80px);
                text-align: center;
                border: 1px solid #e5e0d8;
            }
            h1 { color: #201e1b; font-size: 25px; }
            input, button {
                box-sizing: border-box;
                width: 100%;
                padding: 12px;
                margin-top: 12px;
            }
            input { border: 1px solid #e5e0d8; }
            button {
                background: #927762;
                color: white;
                border: none;
                cursor: pointer;
            }
            .error { color: #b00020; font-size: 13px; }
        </style>
    </head>
    <body>
        <div class="login-box">
            <h1>JORA.EDIT</h1>
            <p>Admin Login</p>
            <form method="POST">
                <input name="username" placeholder="Username" required>
                <input name="password" type="password" placeholder="Password" required>
                <button type="submit">LOGIN</button>
            </form>
            <p class="error">{{ error }}</p>
        </div>
    </body>
    </html>
    """, error=error)


# =========================================
# VIEW PAYMENT PROOF - ADMIN ONLY
# =========================================

@app.route("/admin/payment-proof/<int:order_id>")
@admin_required
def view_payment_proof(order_id):

    connection = get_connection()

    order = connection.execute(
        "SELECT payment_proof FROM orders WHERE id = ?",
        (order_id,)
    ).fetchone()

    connection.close()

    if not order or not order["payment_proof"]:
        abort(404)

    filename = os.path.basename(order["payment_proof"])

    return send_from_directory(
        PAYMENT_PROOF_DIR,
        filename,
        as_attachment=False
    )


# =========================================
# ADMIN DASHBOARD
# =========================================

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():

    connection = get_connection()

    orders = connection.execute(
        "SELECT * FROM orders ORDER BY id DESC"
    ).fetchall()

    subscribers = connection.execute(
        "SELECT * FROM subscribers ORDER BY id DESC"
    ).fetchall()

    connection.close()

    formatted_orders = []

    for order in orders:

        order_data = dict(order)

        try:
            products = json.loads(order_data["products"])

            if not isinstance(products, list):
                products = []

        except (json.JSONDecodeError, TypeError):
            products = []

        order_data["products_list"] = products
        formatted_orders.append(order_data)

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>JORA.EDIT Dashboard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">

        <style>
            body {
                background: #f8f7f3;
                color: #201e1b;
                font-family: Arial, sans-serif;
                padding: 30px;
            }

            h1, h2 { color: #6d594a; }

            .stats {
                display: flex;
                gap: 20px;
                flex-wrap: wrap;
            }

            .stat {
                background: white;
                padding: 20px;
                border: 1px solid #e5e0d8;
                margin-bottom: 20px;
                min-width: 150px;
            }

            table {
                width: 100%;
                border-collapse: collapse;
                background: white;
                margin-bottom: 30px;
                min-width: 1400px;
            }

            th, td {
                padding: 12px;
                border: 1px solid #e5e0d8;
                text-align: left;
                font-size: 13px;
                vertical-align: top;
            }

            th { background: #e9ded2; }

            .logout {
                color: #927762;
                float: right;
            }

            .table-wrap { overflow-x: auto; }

            .product-line {
                padding: 8px 0;
                border-bottom: 1px solid #e5e0d8;
                line-height: 1.7;
            }

            .product-name {
                font-weight: bold;
                color: #6d594a;
            }

            select {
                padding: 9px;
                border: 1px solid #d8c7b7;
                border-radius: 4px;
                font-size: 12px;
                cursor: pointer;
                max-width: 180px;
            }

            .amount {
                white-space: nowrap;
                line-height: 1.8;
            }

            .proof-link {
                display: inline-block;
                margin-top: 8px;
                color: #785c46;
                font-weight: bold;
            }

            .transaction {
                overflow-wrap: anywhere;
                max-width: 160px;
            }

            @media(max-width: 600px) {
                body { padding: 15px; }
            }
        </style>
    </head>

    <body>

        <a class="logout" href="/admin/logout">Logout</a>

        <h1>JORA.EDIT Admin Dashboard</h1>
        <p>Welcome to your store management panel.</p>

        <div class="stats">
            <div class="stat">
                <h2>{{ orders|length }}</h2>
                <p>Total Orders</p>
            </div>

            <div class="stat">
                <h2>{{ subscribers|length }}</h2>
                <p>Newsletter Subscribers</p>
            </div>
        </div>

        <h2>Customer Orders</h2>

        <div class="table-wrap">
        <table>
            <tr>
                <th>Order ID</th>
                <th>Customer</th>
                <th>Contact</th>
                <th>Delivery Address</th>
                <th>Payment Method</th>
                <th>Payment Preference</th>
                <th>Transaction ID & Proof</th>
                <th>Products</th>
                <th>Payment Breakdown</th>
                <th>Payment Verification</th>
                <th>Order Status</th>
                <th>Date</th>
            </tr>

            {% for order in orders %}
            <tr>
                <td>#{{ order.id }}</td>

                <td>{{ order.customer_name }}</td>

                <td>
                    {{ order.phone }}<br>
                    {{ order.email }}
                </td>

                <td>
                    {{ order.city }}<br>
                    {{ order.address }}
                </td>

                <td>{{ order.payment_method }}</td>

                <td>{{ order.payment_preference }}</td>

                <td>
                    <div class="transaction">
                        <strong>Transaction ID:</strong><br>
                        {{ order.transaction_id or "Not provided" }}
                    </div>

                    {% if order.payment_proof %}
                    <a class="proof-link"
                       href="{{ url_for('view_payment_proof', order_id=order.id) }}"
                       target="_blank">
                        VIEW PAYMENT SCREENSHOT
                    </a>
                    {% else %}
                    No screenshot uploaded.
                    {% endif %}
                </td>

                <td>
                    {% for product in order.products_list %}
                    <div class="product-line">
                        <div class="product-name">
                            {{ product.get("name", "Product") }}
                        </div>
                        Size: {{ product.get("size", "N/A") }}<br>
                        Quantity: {{ product.get("quantity", 1) }}<br>
                        Price: {{ product.get("price", "N/A") }}
                    </div>
                    {% else %}
                    No product details available.
                    {% endfor %}
                </td>

                <td class="amount">
                    Subtotal: PKR {{ "{:,}".format(order.subtotal) }}<br>
                    Shipping: PKR {{ "{:,}".format(order.shipping) }}<br>
                    <strong>
                        Total: PKR {{ "{:,}".format(order.total) }}
                    </strong>
                    <hr>
                    Paid / Submitted:
                    PKR {{ "{:,}".format(order.advance) }}<br>
                    Remaining: PKR {{ "{:,}".format(order.remaining) }}<br>
                    Pay on delivery:
                    PKR {{ "{:,}".format(order.delivery_amount) }}
                </td>

                <td>
                    <form method="POST" action="/admin/update-payment-status">
                        <input type="hidden" name="order_id" value="{{ order.id }}">

                        <select name="payment_status" onchange="this.form.submit()">
                            {% for option in [
                                "Pending Verification",
                                "Verified",
                                "Rejected"
                            ] %}
                            <option value="{{ option }}"
                                {% if order.payment_status == option %}selected{% endif %}>
                                {{ option }}
                            </option>
                            {% endfor %}
                        </select>
                    </form>

                    {% if order.email_sent_at %}
                    <p>Email sent ✓</p>
                    {% elif order.email %}
                    <p>Email not sent yet</p>
                    {% else %}
                    <p>No customer email</p>
                    {% endif %}
                </td>

                <td>
                    <form method="POST" action="/admin/update-order-status">
                        <input type="hidden" name="order_id" value="{{ order.id }}">

                        <select name="status" onchange="this.form.submit()">
                            {% for option in [
                                "Pending",
                                "Confirmed",
                                "Shipped",
                                "Delivered",
                                "Cancelled"
                            ] %}
                            <option value="{{ option }}"
                                {% if order.status == option %}selected{% endif %}>
                                {{ option }}
                            </option>
                            {% endfor %}
                        </select>
                    </form>
                </td>

                <td>{{ order.order_date }}</td>
            </tr>

            {% else %}
            <tr>
                <td colspan="12">No orders received yet.</td>
            </tr>
            {% endfor %}
        </table>
        </div>

        <h2>Newsletter Subscribers</h2>

        <div class="table-wrap">
        <table>
            <tr>
                <th>ID</th>
                <th>Email</th>
                <th>Subscription Date</th>
            </tr>

            {% for subscriber in subscribers %}
            <tr>
                <td>{{ subscriber.id }}</td>
                <td>{{ subscriber.email }}</td>
                <td>{{ subscriber.subscription_date }}</td>
            </tr>

            {% else %}
            <tr>
                <td colspan="3">No subscribers yet.</td>
            </tr>
            {% endfor %}
        </table>
        </div>

    </body>
    </html>
    """, orders=formatted_orders, subscribers=subscribers)


# =========================================
# UPDATE ORDER STATUS
# =========================================

@app.route("/admin/update-order-status", methods=["POST"])
@admin_required
def update_order_status():

    order_id = request.form.get("order_id")
    status = request.form.get("status")

    allowed_statuses = [
        "Pending",
        "Confirmed",
        "Shipped",
        "Delivered",
        "Cancelled"
    ]

    if status not in allowed_statuses:
        return "Invalid order status", 400

    connection = get_connection()

    connection.execute("""
        UPDATE orders
        SET status = ?
        WHERE id = ?
    """, (status, order_id))

    connection.commit()
    connection.close()

    send_confirmation_email(order_id)

    return redirect(url_for("admin_dashboard"))


# =========================================
# UPDATE PAYMENT VERIFICATION STATUS
# =========================================

@app.route("/admin/update-payment-status", methods=["POST"])
@admin_required
def update_payment_status():

    order_id = request.form.get("order_id")
    payment_status = request.form.get("payment_status")

    allowed_statuses = [
        "Pending Verification",
        "Verified",
        "Rejected"
    ]

    if payment_status not in allowed_statuses:
        return "Invalid payment status", 400

    connection = get_connection()

    connection.execute("""
        UPDATE orders
        SET payment_status = ?
        WHERE id = ?
    """, (payment_status, order_id))

    connection.commit()
    connection.close()

    send_confirmation_email(order_id)

    return redirect(url_for("admin_dashboard"))


# =========================================
# ADMIN LOGOUT
# =========================================

@app.route("/admin/logout")
def admin_logout():

    session.clear()
    return redirect(url_for("admin_login"))


# =========================================
# HANDLE LARGE FILE ERROR
# =========================================

@app.errorhandler(413)
def file_too_large(error):

    return jsonify({
        "success": False,
        "message": "Screenshot must be smaller than 5 MB."
    }), 413


# =========================================
# RUN WEBSITE
# =========================================

create_database()

if __name__ == "__main__":

    print("JORA.EDIT website is running!")

    app.run(
        debug=True,
        port=5001
    )
