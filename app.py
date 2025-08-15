from flask import Flask, render_template, request, redirect, jsonify, session, send_from_directory
from datetime import datetime
from mysql.connector import connect, Error
import hashlib
import jwt as PyJWT
import os

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = 'q34rh483q7r'
app.secret_key = 'your_secret_key'
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

DB_CONFIG = {
    'host': 'localhost',
    'database': 'auth_db',
    'user': 'root',
    'password': 'qaz123',
    'port': '3306',
    'auth_plugin': 'mysql_native_password'
}

def get_db_connection():
    try:
        conn = connect(**DB_CONFIG)
        return conn
    except Error as e:
        print(f"Ошибка подключения к базе данных: {e}")
        return None

def generate_token(username, password):
    payload = {'username': username, 'password': password}
    return PyJWT.encode(payload, app.config['JWT_SECRET_KEY'], algorithm='HS256')

def verify_token(token):
    try:
        payload = PyJWT.decode(token, app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
        return payload
    except PyJWT.InvalidTokenError:
        return False

@app.route("/")
def root():
    return redirect("/login")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Не удалось подключиться к базе данных"}), 500
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, password, token FROM users WHERE username=%s AND password=%s",
                           (username, hashed_password))
            user = cursor.fetchone()
            if user:
                user_id, _, _, token = user
                if token and verify_token(token):
                    session['token'] = token
                else:
                    token = generate_token(username, password)
                    cursor.execute("UPDATE users SET token=%s WHERE id=%s", (token, user_id))
                    conn.commit()
                    session['token'] = token
                return redirect('/table')
            else:
                return jsonify({"error": "Неверные учетные данные"}), 401
        except Error as e:
            return jsonify({"error": f"Ошибка базы данных: {e}"}), 500
        finally:
            cursor.close()
            conn.close()
    return render_template("login.html")

@app.route("/table")
def show_table():
    token = session.get('token')
    if not token or not verify_token(token):
        return redirect('/login')
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Не удалось подключиться к базе данных"}), 500
    try:
        cursor = conn.cursor()
        id_filter = request.args.get('id')
        color_filter = request.args.get('color')
        if id_filter:
            cursor.execute("SELECT * FROM balances WHERE id=%s", (id_filter,))
        elif color_filter:
            colors = color_filter.split(',')
            query = " UNION ALL ".join([f"SELECT * FROM balances WHERE color LIKE '%{c.strip()}%'" for c in colors])
            cursor.execute(query)
        else:
            cursor.execute("SELECT * FROM balances")
        rows = cursor.fetchall()
        return render_template("table.html", rows=rows, current_user=verify_token(token)['username'])
    except Error as e:
        return jsonify({"error": f"Ошибка базы данных {e}"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/employees")
def show_employees():
    token = session.get('token')
    if not token or not verify_token(token):
        return redirect('/login')

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Не удалось подключиться к базе данных"}), 500

    try:
        cursor = conn.cursor()
        full_name_filter = request.args.get('full_name')
        department_filter = request.args.get('department')
        position_filter = request.args.get('position')

        if full_name_filter:
            cursor.execute("SELECT * FROM employees WHERE full_name LIKE %s", (f"%{full_name_filter}%",))
        elif department_filter:
            cursor.execute("SELECT * FROM employees WHERE department = %s", (department_filter,))
        elif position_filter:
            cursor.execute("SELECT * FROM employees WHERE position = %s", (position_filter,))
        else:
            cursor.execute("SELECT * FROM employees")

        employees = cursor.fetchall()
        return render_template("employees.html", employees=employees, datetime=datetime)
    except Error as e:
        return jsonify({"error": f"Ошибка базы данных: {e}"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/add_employee", methods=["GET", "POST"])
def add_employee():
    if request.method == "POST":
        if not session.get('token') or not verify_token(session.get('token')):
            return redirect('/login')
        data = {
            'employee_number': request.form.get("employee_number"),
            'full_name': request.form.get("full_name"),
            'birth_date': request.form.get("birth_date"),
            'gender': request.form.get("gender"),
            'address': request.form.get("address"),
            'email': request.form.get("email"),
            'passport_series_number': request.form.get("passport_series_number"),
            'snils': request.form.get("snils"),
            'inn': request.form.get("inn"),
            'hire_date': request.form.get("hire_date"),
            'position': request.form.get("position"),
            'department': request.form.get("department"),
            'phone': request.form.get("phone"),
        }
        photo = request.files.get("photo")
        if photo:
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], photo.filename)
            photo.save(photo_path)
            data['photo'] = photo_path
        else:
            data['photo'] = None
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Не удалось подключиться к базе данных"}), 500
        try:
            cursor = conn.cursor()
            query = """
            INSERT INTO employees (employee_number, full_name, birth_date, gender, address, email, passport_series_number, snils, inn, hire_date, position, department, phone, photo)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query, tuple(data.values()))
            conn.commit()
            return redirect("/employees")
        except Error as e:
            return jsonify({"error": f"Ошибка добавления записи: {e}"}), 500
        finally:
            cursor.close()
            conn.close()
    return render_template("add_employee.html")

@app.route("/edit_employee", methods=["POST"])
def edit_employee():
    if not session.get('token') or not verify_token(session.get('token')):
        return redirect('/login')

    employee_id = request.form.get("employee_id")
    data = {
        'employee_number': request.form.get("employee_number"),
        'full_name': request.form.get("full_name"),
        'birth_date': request.form.get("birth_date"),
        'gender': request.form.get("gender"),
        'address': request.form.get("address"),
        'email': request.form.get("email"),
        'passport_series_number': request.form.get("passport_series_number"),
        'snils': request.form.get("snils"),
        'inn': request.form.get("inn"),
        'hire_date': request.form.get("hire_date"),
        'position': request.form.get("position"),
        'department': request.form.get("department"),
        'phone': request.form.get("phone"),
    }

    photo = request.files.get("photo")
    if photo and photo.filename:
        photo_path = os.path.join(app.config['UPLOAD_FOLDER'], photo.filename)
        photo.save(photo_path)
        data['photo'] = photo_path
    else:
        data['photo'] = request.form.get("existing_photo")

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Не удалось подключиться к базе данных"}), 500
    try:
        cursor = conn.cursor()
        query = """
        UPDATE employees SET
            employee_number=%s, full_name=%s, birth_date=%s, gender=%s, address=%s, email=%s,
            passport_series_number=%s, snils=%s, inn=%s, hire_date=%s, position=%s, department=%s, phone=%s, photo=%s
        WHERE id=%s
        """
        cursor.execute(query, (
            data['employee_number'], data['full_name'], data['birth_date'], data['gender'], data['address'], data['email'],
            data['passport_series_number'], data['snils'], data['inn'], data['hire_date'],
            data['position'], data['department'], data['phone'], data['photo'], employee_id
        ))
        conn.commit()
        return redirect("/employees")
    except Error as e:
        return jsonify({"error": f"Ошибка редактирования записи: {e}"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/get_employee_data")
def get_employee_data():
    employee_number = request.args.get('employee_number')
    if not employee_number:
        return jsonify({"error": "Табельный номер не указан"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Не удалось подключиться к базе данных"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT full_name, position FROM employees WHERE employee_number = %s", (employee_number,))
        employee_data = cursor.fetchone()
        if employee_data:
            return jsonify(employee_data), 200
        else:
            return jsonify({"error": "Сотрудник не найден"}), 404
    except Error as e:
        return jsonify({"error": f"Ошибка базы данных: {e}"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/phone_directory")
def show_phone_directory():
    token = session.get('token')
    if not token or not verify_token(token):
        return redirect('/login')

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Не удалось подключиться к базе данных"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT employee_number, full_name, position, internal_phone, city_phone, mobile_phone, home_phone, email
            FROM phone_directory
        """)
        phone_directory = cursor.fetchall()

        cursor.execute("SELECT employee_number, full_name, position FROM employees")
        employees = cursor.fetchall()

        return render_template("phone_directory.html", phone_directory=phone_directory, employees=employees)
    except Error as e:
        return jsonify({"error": f"Ошибка базы данных: {e}"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/get_phone_directory")
def get_phone_directory():
    employee_number = request.args.get('employee_number')
    token = session.get('token')
    if not token or not verify_token(token):
        return jsonify({"error": "Неверный или отсутствующий токен"}), 401
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Не удалось подключиться к базе данных"}), 500
    try:
        cursor = conn.cursor(dictionary=True)
        if employee_number:
            cursor.execute("""
                SELECT employee_number, full_name, position, internal_phone, city_phone, mobile_phone, home_phone, email
                FROM phone_directory WHERE employee_number = %s
            """, (employee_number,))
        else:
            cursor.execute("""
                SELECT employee_number, full_name, position, internal_phone, city_phone, mobile_phone, home_phone, email
                FROM phone_directory
            """)
        phone_directory = cursor.fetchall()
        return jsonify(phone_directory if phone_directory else {}), 200
    except Error as e:
        return jsonify({"error": f"Ошибка базы данных: {e}"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/add_phone_directory", methods=["POST"])
def add_phone_directory():
    if not session.get('token') or not verify_token(session.get('token')):
        return redirect('/login')

    data = {
        'employee_number': request.form.get("employee_number"),
        'full_name': request.form.get("full_name"),
        'position': request.form.get("position"),
        'internal_phone': request.form.get("internal_phone"),
        'city_phone': request.form.get("city_phone"),
        'mobile_phone': request.form.get("mobile_phone"),
        'home_phone': request.form.get("home_phone"),
        'email': request.form.get("email")
    }

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Не удалось подключиться к базе данных"}), 500

    try:
        cursor = conn.cursor()
        query = """
        INSERT INTO phone_directory (employee_number, full_name, position, internal_phone, city_phone, mobile_phone, home_phone, email)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, tuple(data.values()))
        conn.commit()
        return redirect("/phone_directory")
    except Error as e:
        return jsonify({"error": f"Ошибка добавления записи: {e}"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/update_phone_directory', methods=['POST'])
def update_phone_directory():
    if not session.get('token') or not verify_token(session.get('token')):
        return redirect('/login')

    employee_number = request.form.get('employee_number', '').strip()
    full_name = request.form.get('full_name', '')
    position = request.form.get('position', '')
    internal_phone = request.form.get('internal_phone') or None
    city_phone = request.form.get('city_phone') or None
    mobile_phone = request.form.get('mobile_phone') or None
    home_phone = request.form.get('home_phone') or None
    email = request.form.get('email') or None

    if not employee_number:
        print("❌ Ошибка: employee_number не указан")
        return jsonify({"error": "Табельный номер не указан"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Не удалось подключиться к базе данных"}), 500

    try:
        cursor = conn.cursor()

        query = """
            UPDATE phone_directory SET
                full_name = %s,
                position = %s,
                internal_phone = %s,
                city_phone = %s,
                mobile_phone = %s,
                home_phone = %s,
                email = %s
            WHERE employee_number = %s
        """
        cursor.execute(query, (
            full_name, position, internal_phone, city_phone,
            mobile_phone, home_phone, email, employee_number
        ))

        if cursor.rowcount == 0:
            print(f"⚠️ Запись с employee_number={employee_number} не найдена для обновления")
            return jsonify({"error": "Запись не найдена"}), 404

        conn.commit()
        print(f"✅ Успешно обновлена запись для {employee_number}")
        return redirect('/phone_directory')

    except Exception as e:
        print(f"❌ Ошибка при обновлении: {e}")
        return jsonify({"error": f"Ошибка базы данных: {e}"}), 500

    finally:
        cursor.close()
        conn.close()

@app.route("/add", methods=["GET", "POST"])
def add_record():
    if request.method == "POST":
        if not session.get('token') or not verify_token(session.get('token')):
            return redirect('/login')
        data = {
            'articul': request.form.get("article"),
            'build_name': request.form.get("name"),
            'color': request.form.get("color"),
            'row_by_row': request.form.get("row_count"),
            'quantity_in_row': request.form.get("count_in_row"),
            'dwh': request.form.get("dimensions"),
            'mass': request.form.get("mass"),
            'production_date': request.form.get("production_date"),
            'expiration_date': request.form.get("expiration_date"),
            'storage_area': request.form.get("storage_location"),
            'quantity_pp': request.form.get("package_count"),
            'quantity_production': request.form.get("item_count"),
            'total_weight_pp': request.form.get("total_mass")
        }
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Не удалось подключиться к базе данных"}), 500
        try:
            cursor = conn.cursor()
            query = """
            INSERT INTO balances (Articul, BuildName, Color, RowByRow, quantityinrow, dwh, mass,
                                 productiondate, expirationdate, storagearea, quantitypp,
                                 quantityproduction, totalweightpp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query, tuple(data.values()))
            conn.commit()
            return redirect("/table")
        except Error as e:
            return jsonify({"error": f"Ошибка добавления записи: {e}"}), 500
        finally:
            cursor.close()
            conn.close()
    return render_template("add.html")

@app.route("/add_quantity", methods=["POST"])
def add_quantity():
    if not session.get('token') or not verify_token(session.get('token')):
        return redirect('/login')
    row_id = request.form.get("row_id")
    add_qty = request.form.get("add_quantity")
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Не удалось подключиться к базе данных"}), 500
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE balances SET quantityproduction = quantityproduction + %s WHERE id = %s",
                       (add_qty, row_id))
        conn.commit()
        return redirect("/table")
    except Error as e:
        return jsonify({"error": f"Ошибка обновления: {e}"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/registration", methods=["GET", "POST"])
def handle_registration():
    if request.method == "POST":
        username = request.form.get("username")
        password = hashlib.sha256(request.form.get("password").encode()).hexdigest()
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Не удалось подключиться к базе данных"}), 500
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
            conn.commit()
            cursor.execute("SELECT LAST_INSERT_ID()")
            user_id = cursor.fetchone()[0]
            token = generate_token(username, request.form.get("password"))
            cursor.execute("UPDATE users SET token=%s WHERE id=%s", (token, user_id))
            conn.commit()
            return redirect("/login?success=1")
        except Error as e:
            return jsonify({"error": f"Ошибка регистрации: {e}"}), 500
        finally:
            cursor.close()
            conn.close()
    return render_template("registration.html")

@app.route("/write_off", methods=["POST"])
def write_off():
    if not session.get('token') or not verify_token(session.get('token')):
        return redirect('/login')
    row_id = request.form.get("row_id")
    write_off_qty = request.form.get("write_off_quantity")
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Не удалось подключиться к базе данных"}), 500
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE balances SET quantityproduction = quantityproduction - %s WHERE id = %s",
                       (write_off_qty, row_id))
        conn.commit()
        return redirect("/table")
    except Error as e:
        return jsonify({"error": f"Ошибка списания: {e}"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/edit", methods=["POST"])
def edit_record():
    if not session.get('token') or not verify_token(session.get('token')):
        return redirect('/login')
    data = {
        'row_id': request.form.get("row_id"),
        'articul': request.form.get("articul"),
        'build_name': request.form.get("build_name"),
        'color': request.form.get("color"),
        'row_by_row': request.form.get("row_by_row"),
        'quantity_in_row': request.form.get("quantity_in_row"),
        'dwh': request.form.get("dwh"),
        'mass': request.form.get("mass"),
        'production_date': request.form.get("production_date"),
        'expiration_date': request.form.get("expiration_date"),
        'storage_area': request.form.get("storage_area"),
        'quantity_pp': request.form.get("quantity_pp"),
        'quantity_production': request.form.get("quantity_production"),
        'total_weight_pp': request.form.get("total_weight_pp")
    }
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Не удалось подключиться к базе данных"}), 500
    try:
        cursor = conn.cursor()
        query = """
        UPDATE balances SET Articul=%s, BuildName=%s, Color=%s, RowByRow=%s, quantityinrow=%s,
                            dwh=%s, mass=%s, productiondate=%s, expirationdate=%s, storagearea=%s,
                            quantitypp=%s, quantityproduction=%s, totalweightpp=%s
        WHERE id=%s
        """
        cursor.execute(query, (data['articul'], data['build_name'], data['color'], data['row_by_row'],
                               data['quantity_in_row'], data['dwh'], data['mass'], data['production_date'],
                               data['expiration_date'], data['storage_area'], data['quantity_pp'],
                               data['quantity_production'], data['total_weight_pp'], data['row_id']))
        conn.commit()
        return redirect("/table")
    except Error as e:
        return jsonify({"error": f"Ошибка редактирования: {e}"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/delete", methods=["POST"])
def delete_record():
    if not session.get('token') or not verify_token(session.get('token')):
        return redirect('/login')
    row_id = request.form.get("row_id")
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Не удалось подключиться к базе данных"}), 500
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM balances WHERE id = %s", (row_id,))
        conn.commit()
        return redirect("/table")
    except Error as e:
        return jsonify({"error": f"Ошибка удаления: {e}"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"error": "Отсутствуют username или password"}), 400
    username = data['username']
    password = data['password']
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Не удалось подключиться к базе данных"}), 500
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, password, token FROM users WHERE username=%s AND password=%s",
                       (username, hashed_password))
        user = cursor.fetchone()
        if user:
            user_id, _, _, token = user
            if not token or not verify_token(token):
                token = generate_token(username, password)
                cursor.execute("UPDATE users SET token=%s WHERE id=%s", (token, user_id))
                conn.commit()   
            return jsonify({"token": token}), 200
        else:
            return jsonify({"error": "Неверные учетные данные"}), 401
    except Error as e:
        return jsonify({"error": f"Ошибка базы данных: {e}"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/api/balances", methods=["GET", "POST"])
def api_balances():
    token = request.headers.get('Authorization')
    if not token or not verify_token(token):
        return jsonify({"error": "Неверный или отсутствующий токен"}), 401
    if request.method == "GET":
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Не удалось подключиться к базе данных"}), 500
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM balances")
            rows = cursor.fetchall()
            balances = [
                {
                    "id": row[0],
                    "articul": row[1],
                    "build_name": row[2],
                    "color": row[3],
                    "row_by_row": row[4],
                    "quantity_in_row": row[5],
                    "dwh": row[6],
                    "mass": float(row[7]) if row[7] is not None else 0.0,
                    "production_date": str(row[8]) if row[8] else "",
                    "expiration_date": str(row[9]) if row[9] else "",
                    "storage_area": row[10],
                    "quantity_pp": row[11],
                    "quantity_production": row[12],
                    "total_weight_pp": float(row[13]) if row[13] is not None else 0.0
                } for row in rows
            ]
            return jsonify(balances), 200
        except Error as e:
            return jsonify({"error": f"Ошибка базы данных: {e}"}), 500
        finally:
            cursor.close()
            conn.close()
    elif request.method == "POST":
        data = request.get_json()
        if not data:
            return jsonify({"error": "Отсутствуют данные"}), 400
        required_fields = [
            "articul", "build_name", "color", "row_by_row", "quantity_in_row",
            "dwh", "mass", "production_date", "expiration_date", "storage_area",
            "quantity_pp", "quantity_production", "total_weight_pp"
        ]
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Отсутствуют обязательные поля"}), 400
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Не удалось подключиться к базе данных"}), 500
        try:
            cursor = conn.cursor()
            query = """
            INSERT INTO balances (Articul, BuildName, Color, RowByRow, quantityinrow, dwh, mass,
                                 productiondate, expirationdate, storagearea, quantitypp,
                                 quantityproduction, totalweightpp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query, (
                data["articul"], data["build_name"], data["color"], data["row_by_row"],
                data["quantity_in_row"], data["dwh"], data["mass"], data["production_date"],
                data["expiration_date"], data["storage_area"], data["quantity_pp"],
                data["quantity_production"], data["total_weight_pp"]
            ))
            conn.commit()
            return jsonify({"message": "Запись успешно добавлена"}), 201
        except Error as e:
            return jsonify({"error": f"Ошибка добавления: {e}"}), 500
        finally:
            cursor.close()
            conn.close()

@app.route("/api/write_off", methods=["POST"])
def api_write_off():
    token = request.headers.get('Authorization')
    if not token or not verify_token(token):
        return jsonify({"error": "Неверный или отсутствующий токен"}), 401
    data = request.get_json()
    if not data or 'row_id' not in data or 'write_off_quantity' not in data:
        return jsonify({"error": "Отсутствуют row_id или write_off_quantity"}), 400
    row_id = data['row_id']
    write_off_qty = data['write_off_quantity']
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Не удалось подключиться к базе данных"}), 500
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE balances SET quantityproduction = quantityproduction - %s WHERE id = %s",
            (write_off_qty, row_id)
        )
        conn.commit()
        return jsonify({"message": "Остаток успешно добавлен"}), 200
    except Error as e:
        return jsonify({"error": f"Ошибка базы данных: {e}"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/api/add_quantity", methods=["POST"])
def api_add_quantity():
    token = request.headers.get('Authorization')
    if not token or not verify_token(token):
        return jsonify({"error": "Неверный или отсутствующий токен"}), 401
    data = request.get_json()
    if not data or 'row_id' not in data or 'add_quantity' not in data:
        return jsonify({"error": "Отсутствуют row_id или add_quantity"}), 400
    row_id = data['row_id']
    add_qty = data['add_quantity']
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Не удалось подключиться к базе данных"}), 500
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE balances SET quantityproduction = quantityproduction + %s WHERE id = %s",
            (add_qty, row_id)
        )
        conn.commit()
        return jsonify({"message": "Остаток успешно добавлен"}), 200
    except Error as e:
        return jsonify({"error": f"Ошибка базы данных: {e}"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/api/edit", methods=["POST"])
def api_edit():
    token = request.headers.get('Authorization')
    if not token or not verify_token(token):
        return jsonify({"error": "Неверный или отсутствующий токен"}), 401
    data = request.get_json()
    if not data or 'id' not in data:
        return jsonify({"error": "Отсутствует id записи"}), 400
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Не удалось подключиться к базе данных"}), 500
    try:
        cursor = conn.cursor()
        query = """
        UPDATE balances SET
            Articul=%s, BuildName=%s, Color=%s, RowByRow=%s, quantityinrow=%s,
            dwh=%s, mass=%s, productiondate=%s, expirationdate=%s, storagearea=%s,
            quantitypp=%s, quantityproduction=%s, totalweightpp=%s
        WHERE id=%s
        """
        cursor.execute(query, (
            data.get("articul"), data.get("build_name"), data.get("color"), data.get("row_by_row"),
            data.get("quantity_in_row"), data.get("dwh"), data.get("mass"), data.get("production_date"),
            data.get("expiration_date"), data.get("storage_area"), data.get("quantity_pp"),
            data.get("quantity_production"), data.get("total_weight_pp"), data["id"]
        ))
        conn.commit()
        return jsonify({"message": "Запись успешно обновлена"}), 200
    except Error as e:
        return jsonify({"error": f"Ошибка базы данных: {e}"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/api/profile", methods=["GET", "POST"])
def handle_profile():
    token = session.get('token')
    if not token or not verify_token(token):
        return jsonify({"error": "Неверный или отсутствующий токен"}), 401
    username = verify_token(token)['username']
    if request.method == "GET":
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Не удалось подключиться к базе данных"}), 500
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT full_name, email, phone, photo FROM users WHERE username = %s", (username,))
            user_info = cursor.fetchone()
            if user_info:
                return jsonify(user_info), 200
            else:
                return jsonify({}), 200
        except Error as e:
            return jsonify({"error": f"Ошибка базы данных: {e}"}), 500
        finally:
            cursor.close()
            conn.close()
    elif request.method == "POST":
        data = request.form
        full_name = data.get("fullName")
        email = data.get("email")
        phone = data.get("phone")
        photo = request.files.get("photo")
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Не удалось подключиться к базе данных"}), 500
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT photo FROM users WHERE username = %s", (username,))
            user_photo = cursor.fetchone()
            current_photo_url = user_photo['photo'] if user_photo else None
            if photo and photo.filename:
                photo_path = os.path.join(app.config['UPLOAD_FOLDER'], photo.filename)
                photo.save(photo_path)
                photo_url = photo_path
            else:
                photo_url = current_photo_url
            cursor.execute("""
                UPDATE users
                SET full_name = %s, email = %s, phone = %s, photo = %s
                WHERE username = %s
            """, (full_name, email, phone, photo_url, username))
            conn.commit()
            return jsonify({"message": "Профиль успешно обновлен"}), 200
        except Error as e:
            return jsonify({"error": f"Ошибка базы данных: {e}"}), 500
        finally:
            cursor.close()
            conn.close()

@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == "__main__":
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)
