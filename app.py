from flask import Flask, render_template, request, redirect, session, flash, url_for
import mysql.connector
import random

app = Flask(__name__)
app.secret_key = "snackstack123"

# -------------------------
# DATABASE CONNECTION
# -------------------------
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="snackstack"
    )

# -------------------------
# ROOT REDIRECT TO LOGIN
# -------------------------
@app.route("/")
def root():
    return redirect(url_for("login"))

# -------------------------
# HOME / USER PAGES
# -------------------------
@app.route("/user_home")
def user_home():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM restaurants")
    restaurants = cursor.fetchall()
    cursor.execute("""
        SELECT m.*, r.name AS restaurant_name
        FROM menu_items m
        JOIN restaurants r ON m.restaurant_id=r.restaurant_id
        WHERE m.available=1
    """)
    items = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("user_home.html", restaurants=restaurants, items=items)

@app.route("/item/<int:item_id>", methods=["GET","POST"])
def item_detail(item_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT m.*, r.name AS restaurant_name
        FROM menu_items m
        JOIN restaurants r ON m.restaurant_id=r.restaurant_id
        WHERE m.item_id=%s
    """, (item_id,))
    item = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template("item_detail.html", item=item)

# -------------------------
# USER AUTH
# -------------------------
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        phone = request.form.get('phone')
        address = request.form.get('address')

        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (name,email,password,phone_no,address) VALUES (%s,%s,%s,%s,%s)",
                           (name,email,password,phone,address))
            conn.commit()
            flash("Registration successful, please login")
            return redirect(url_for("login"))
        except mysql.connector.errors.IntegrityError:
            flash("Email already exists")
        cursor.close()
        conn.close()
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        login_type = request.form['login_type']
        email = request.form['email']
        password = request.form['password']

        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        if login_type=="user":
            cursor.execute("SELECT * FROM users WHERE email=%s AND password=%s", (email,password))
            user = cursor.fetchone()
            if user:
                session['user_id'] = user['user_id']
                session['user_name'] = user['name']
                flash("Login successful")
                return redirect(url_for("user_home"))
            else:
                flash("Invalid user credentials")
        else:
            cursor.execute("SELECT * FROM employees WHERE emp_id=%s AND password=%s", (email,password))
            emp = cursor.fetchone()
            if emp:
                session['emp_id'] = emp['emp_id']
                session['emp_name'] = emp['emp_id']
                flash("Employee login successful")
                return redirect(url_for("employee_dashboard"))
            else:
                flash("Invalid employee credentials")
        cursor.close()
        conn.close()
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out")
    return redirect(url_for("login"))

# -------------------------
# CART / ORDERS
# -------------------------
@app.route("/cart")
def view_cart():
    if not session.get('user_id'):
        flash("Login required")
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    user_id = session['user_id']
    cursor.execute("""
        SELECT c.*, m.name, m.price
        FROM cart c
        JOIN menu_items m ON c.item_id = m.item_id
        WHERE c.user_id=%s
    """, (user_id,))
    cart_items = cursor.fetchall()
    total = sum(item['price']*item['quantity'] for item in cart_items)
    cursor.close()
    conn.close()
    return render_template("cart.html", cart_items=cart_items, total=total, order_placed=False)

@app.route("/add_to_cart/<int:item_id>", methods=["POST"])
def add_to_cart(item_id):
    if not session.get('user_id'):
        flash("Login required")
        return redirect(url_for("login"))

    quantity = int(request.form.get('quantity',1))
    user_id = session['user_id']
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cart WHERE user_id=%s AND item_id=%s", (user_id,item_id))
    existing = cursor.fetchone()
    if existing:
        cursor.execute("UPDATE cart SET quantity=quantity+%s WHERE user_id=%s AND item_id=%s",
                       (quantity,user_id,item_id))
    else:
        cursor.execute("INSERT INTO cart (user_id,item_id,quantity) VALUES (%s,%s,%s)",
                       (user_id,item_id,quantity))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Item added to cart")
    return redirect(url_for("view_cart"))

@app.route("/update_cart/<int:cart_id>", methods=["POST"])
def update_cart(cart_id):
    if not session.get('user_id'):
        flash("Login required")
        return redirect(url_for("login"))
    quantity = int(request.form.get('quantity',1))
    conn = get_db()
    cursor = conn.cursor()
    if quantity>0:
        cursor.execute("UPDATE cart SET quantity=%s WHERE cart_id=%s", (quantity,cart_id))
    else:
        cursor.execute("DELETE FROM cart WHERE cart_id=%s", (cart_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Cart updated")
    return redirect(url_for("view_cart"))

@app.route("/remove_from_cart/<int:cart_id>", methods=["POST"])
def remove_from_cart(cart_id):
    if not session.get('user_id'):
        flash("Login required")
        return redirect(url_for("login"))
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cart WHERE cart_id=%s", (cart_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Item removed")
    return redirect(url_for("view_cart"))

@app.route("/checkout", methods=["POST","GET"])
def checkout():
    if not session.get('user_id'):
        flash("Login required")
        return redirect(url_for("login"))
    user_id = session['user_id']
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT c.*, m.name, m.price
        FROM cart c
        JOIN menu_items m ON c.item_id = m.item_id
        WHERE c.user_id=%s
    """, (user_id,))
    cart_items = cursor.fetchall()
    total = sum(item['price']*item['quantity'] for item in cart_items)
    if request.method=="POST":
        cursor.execute("INSERT INTO orders (user_id, total_amount) VALUES (%s,%s)", (user_id,total))
        order_id = cursor.lastrowid
        for item in cart_items:
            cursor.execute("""
                INSERT INTO order_items (order_id,item_id,quantity,price)
                VALUES (%s,%s,%s,%s)
            """, (order_id, item['item_id'], item['quantity'], item['price']))
        cursor.execute("SELECT * FROM delivery_staff WHERE status='available'")
        staff_list = cursor.fetchall()
        assigned = None
        if staff_list:
            assigned = random.choice(staff_list)
            cursor.execute("UPDATE orders SET staff_id=%s WHERE order_id=%s", (assigned['staff_id'], order_id))
            cursor.execute("UPDATE delivery_staff SET status='busy' WHERE staff_id=%s", (assigned['staff_id'],))
        cursor.execute("DELETE FROM cart WHERE user_id=%s", (user_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return render_template("cart.html", order_placed=True, order_id=order_id, ordered_items=cart_items,
                               order_total=total, assigned=assigned, cart_items=[])
    cursor.close()
    conn.close()
    return render_template("checkout.html", cart_items=cart_items, total=total)

# -------------------------
# EMPLOYEE DASHBOARD & MANAGEMENT
# -------------------------
@app.route("/employee_dashboard")
def employee_dashboard():
    if not session.get('emp_id'):
        flash("Access denied")
        return redirect(url_for("login"))
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    users_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM orders")
    orders_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM delivery_staff")
    staff_count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return render_template("employee_dashboard.html", users_count=users_count, orders_count=orders_count, staff_count=staff_count)

# --- Delivery staff CRUD ---
@app.route("/manage_delivery_staff")
def manage_delivery_staff():
    if not session.get('emp_id'):
        flash("Access denied")
        return redirect(url_for("login"))
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM delivery_staff")
    staff = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("manage_delivery.html", staff=staff)

@app.route("/add_delivery_staff", methods=["GET","POST"])
def add_delivery_staff():
    if not session.get('emp_id'):
        flash("Access denied")
        return redirect(url_for("login"))
    if request.method=="POST":
        name = request.form['name']
        phone = request.form.get('phone')
        vehicle = request.form.get('vehicle')
        location = request.form.get('location')
        status = request.form.get('status','available')
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO delivery_staff (name,phone_no,vehicle_type,current_loc,status) VALUES (%s,%s,%s,%s,%s)",
                       (name,phone,vehicle,location,status))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Delivery staff added")
        return redirect(url_for("manage_delivery_staff"))
    return render_template("add_edit_staff.html", action="Add", staff=None)

@app.route("/edit_delivery_staff/<int:staff_id>", methods=["GET","POST"])
def edit_delivery_staff(staff_id):
    if not session.get('emp_id'):
        flash("Access denied")
        return redirect(url_for("login"))
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM delivery_staff WHERE staff_id=%s", (staff_id,))
    staff = cursor.fetchone()
    if request.method=="POST":
        name = request.form['name']
        phone = request.form.get('phone')
        vehicle = request.form.get('vehicle')
        location = request.form.get('location')
        status = request.form.get('status','available')
        cursor.execute("UPDATE delivery_staff SET name=%s, phone_no=%s, vehicle_type=%s, current_loc=%s, status=%s WHERE staff_id=%s",
                       (name,phone,vehicle,location,status,staff_id))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Delivery staff updated")
        return redirect(url_for("manage_delivery_staff"))
    cursor.close()
    conn.close()
    return render_template("add_edit_staff.html", action="Edit", staff=staff)

@app.route("/delete_delivery_staff/<int:staff_id>", methods=["POST"])
def delete_delivery_staff(staff_id):
    if not session.get('emp_id'):
        flash("Access denied")
        return redirect(url_for("login"))
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM delivery_staff WHERE staff_id=%s", (staff_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Delivery staff deleted")
    return redirect(url_for("manage_delivery_staff"))

# --- Restaurants CRUD ---
@app.route("/manage_restaurants")
def manage_restaurants():
    if not session.get('emp_id'):
        flash("Access denied")
        return redirect(url_for("login"))
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM restaurants")
    restaurants = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("manage_restaurants.html", restaurants=restaurants)

@app.route("/add_restaurant", methods=["GET","POST"])
def add_restaurant():
    if not session.get('emp_id'):
        flash("Access denied")
        return redirect(url_for("login"))
    if request.method=="POST":
        name = request.form['name']
        owner = request.form.get('owner')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')
        cuisine = request.form.get('cuisine')
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO restaurants (name,owner_name,email,phone_no,address,cuisine_type) VALUES (%s,%s,%s,%s,%s,%s)",
                       (name,owner,email,phone,address,cuisine))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Restaurant added")
        return redirect(url_for("manage_restaurants"))
    return render_template("add_edit_restaurant.html", action="Add", restaurant=None)

@app.route("/edit_restaurant/<int:rest_id>", methods=["GET","POST"])
def edit_restaurant(rest_id):
    if not session.get('emp_id'):
        flash("Access denied")
        return redirect(url_for("login"))
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM restaurants WHERE restaurant_id=%s", (rest_id,))
    restaurant = cursor.fetchone()
    if request.method=="POST":
        name = request.form['name']
        owner = request.form.get('owner')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')
        cuisine = request.form.get('cuisine')
        cursor.execute("UPDATE restaurants SET name=%s,owner_name=%s,email=%s,phone_no=%s,address=%s,cuisine_type=%s WHERE restaurant_id=%s",
                       (name,owner,email,phone,address,cuisine,rest_id))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Restaurant updated")
        return redirect(url_for("manage_restaurants"))
    cursor.close()
    conn.close()
    return render_template("add_edit_restaurant.html", action="Edit", restaurant=restaurant)

@app.route("/delete_restaurant/<int:rest_id>", methods=["POST"])
def delete_restaurant(rest_id):
    if not session.get('emp_id'):
        flash("Access denied")
        return redirect(url_for("login"))
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM restaurants WHERE restaurant_id=%s", (rest_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Restaurant deleted")
    return redirect(url_for("manage_restaurants"))

# --- View users ---
@app.route("/employee_view_users")
def employee_view_users():
    if not session.get('emp_id'):
        flash("Access denied")
        return redirect(url_for("login"))
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("manage_users.html", users=users)

# --- Employee orders ---
@app.route("/employee_orders", methods=["GET","POST"])
def employee_orders():
    if not session.get('emp_id'):
        flash("Access denied")
        return redirect(url_for("login"))
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    if request.method=="POST":
        order_id = request.form['order_id']
        status = request.form['status']
        cursor.execute("UPDATE orders SET status=%s WHERE order_id=%s", (status, order_id))
        conn.commit()
        flash("Order status updated")
    cursor.execute("""
        SELECT o.*, u.name AS user_name
        FROM orders o
        JOIN users u ON o.user_id=u.user_id
    """)
    orders = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("employee_orders.html", orders=orders)

if __name__=="__main__":
    app.run(debug=True)
