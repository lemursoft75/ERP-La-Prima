import sys
from flask import Flask, render_template, request, redirect, session, jsonify, send_file
import json
import pandas as pd
import os
from datetime import datetime
from openpyxl.workbook import Workbook
import io
import matplotlib
matplotlib.use('Agg')  # <-- Añade estas dos líneas
import matplotlib.pyplot as plt
import base64
from io import BytesIO
import threading
import time
import webbrowser


app = Flask(__name__, template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates'))
app.secret_key = "supersecreto"


# Abre directo la app en el Navegador
def open_browser():
    time.sleep(1)  # Espera un poco para que el servidor se inicie
    webbrowser.open_new_tab("http://127.0.0.1:5000")



#CARGA DE DATOS Y GUARDADO

# Cargar datos desde JSON manteniendo usuarios y productos separados
DATA_FOLDER = "data"


# Crea carpeta para guardar datos
def get_app_folder():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))


# Crea ubicacion de la carpeta
def get_data_path(filename):
    app_folder = get_app_folder()
    data_path = os.path.join(app_folder, DATA_FOLDER)
    os.makedirs(data_path, exist_ok=True)
    return os.path.join(data_path, filename)

# Carga de datos
def load_json(filename):
    filepath = get_data_path(filename)
    try:
        with open(filepath, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}


# Guardado de datos
def save_json(filename, data):
    filepath = get_data_path(filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as file:
        json.dump(data, file, indent=4)


# Recuperacion de datos
def get_uploads_folder():
    """ Get absolute path to uploads folder, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    uploads_path = os.path.join(base_path, "uploads")
    os.makedirs(uploads_path, exist_ok=True)
    return uploads_path


# Carga de datos (productos)
@app.route("/upload-excel", methods=["POST"])
def upload_excel():
    if "file" not in request.files:
        return render_template("register_product.html", message="❌ Error: No se proporcionó un archivo.")

    file = request.files["file"]
    uploads_folder = get_uploads_folder()
    file_path = os.path.join(uploads_folder, file.filename)
    try:
        file.save(file_path)

        df = pd.read_excel(file_path, engine="openpyxl")
        products = load_json("products.json")  # Cargar productos existentes

        for _, row in df.iterrows():
            new_product = {
                "clave": row["Clave"],
                "articulo": row["Artículo"],
                "marca": row["Marca"],
                "categoria": row["Categoria"],
                "tamaño": row["Tamaño"],
                "observaciones": row["Observaciones"]
            }
            # Asegurar que no se dupliquen productos
            if not any(p["clave"] == new_product["clave"] for p in products.get("products", [])):
                products.setdefault("products", []).append(new_product)

        save_json("products.json", products)
        os.remove(file_path)

        return render_template("register_product.html", message="✅ Base actualizada correctamente.")

    except Exception as e:
        return render_template("register_product.html", message=f"❌ Error procesando archivo: {e}")



# ACCESO CON CREDENCIALES

# Página de inicio de sesión
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        users = load_json("users.json")  # Ahora carga solo usuarios
        username = request.form["username"]
        password = request.form["password"]

        if username in users and users[username]["password"] == password:
            session["user"] = username
            return redirect("/dashboard")
        else:
            return "Credenciales incorrectas, intenta de nuevo"

    return render_template("login.html")



# Página de registro de usuario nuevo
@app.route("/register", methods=["GET", "POST"])
def register():
    users = load_json("users.json")  # Cargar usuarios
    message = None

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        question = request.form["question"]
        answer = request.form["answer"]

        if username in users:
            message = "❌ El usuario ya existe. Prueba otro nombre."
        else:
            users[username] = {
                "password": password,
                "security_question": question,
                "security_answer": answer
            }
            save_json("users.json", users)  # Guardar nuevo usuario
            return redirect("/")

    return render_template("register.html", message=message)



# Página de cambio de contraseña
@app.route("/change-password", methods=["GET", "POST"])
def change_password():
    if request.method == "POST":
        users = load_json("users.json")  # Cargar solo usuarios
        username = request.form["username"]
        question = request.form["question"]
        answer = request.form["answer"]
        new_password = request.form["new_password"]

        if username in users and users[username]["security_question"] == question and users[username]["security_answer"].lower() == answer.lower():
            users[username]["password"] = new_password
            save_json("users.json", users)  # Guardar cambios en `users.json`
            return "✅ Contraseña cambiada exitosamente. Ahora puedes iniciar sesión con la nueva contraseña."
        else:
            return "❌ Datos incorrectos. No se pudo cambiar la contraseña."

    return render_template("change_password.html")



# MENU PRINCIPAL Y MODULOS

# Página principal del ERP (requiere login)
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")
    return render_template("dashboard.html", user=session["user"])


#PRODUCTOS

# Página de registro de productos
@app.route("/register-product", methods=["GET", "POST"])
def register_product():
    message = None

    if request.method == "POST":
        products = load_json("products.json")  # Cargar productos
        new_product = {
            "clave": request.form["clave"],
            "articulo": request.form["articulo"],
            "marca": request.form["marca"],
            "categoria": request.form["categoria"],
            "tamaño": request.form["tamaño"],
            "observaciones": request.form["observaciones"]
        }
        products.setdefault("products", []).append(new_product)
        save_json("products.json", products)  # Guardar en el archivo de productos
        message = "Producto registrado correctamente."

    return render_template("register_product.html", message=message)



# Busqueda de productos
@app.route("/search-product", methods=["POST"])
def search_product():
    products_data = load_json("products.json")  # Cargar productos
    inventory_data = load_json("inventory.json")  # Cargar inventario
    clave = request.form["search_clave"]

    # Buscar el producto en la lista de productos
    product = next((p for p in products_data.get("products", []) if p["clave"] == clave), None)

    if product:
        # Buscar existencias en inventario y agregarlas al producto
        product["existencias"] = next((item.get("existencias", 0) for item in inventory_data.get("inventory", []) if item["clave"] == clave), 0)

        return render_template("edit_product.html", product=product, message="✅ Producto encontrado.")

    return render_template("register_product.html", message="❌ Producto no encontrado.")



# Ver productos
@app.route("/get-product", methods=["GET"])
def get_product():
    clave = request.args.get("clave")
    products = load_json("products.json")
    inventory = load_json("inventory.json")

    # Buscar el producto en products.json
    for product in products.get("products", []):
        if product["clave"] == clave:
            existencias = 0  # Inicializar existencias en 0
            precio_unitario = 0  # Inicializar precio en 0

            # Buscar existencias y precio en inventory.json
            for item in inventory.get("inventory", []):
                if item["clave"] == clave:
                    existencias = item.get("existencias", 0)
                    precio_unitario = item.get("precio_unitario", 0)

            return {
                "found": True,
                "articulo": product["articulo"],
                "marca": product["marca"],
                "categoria": product["categoria"],
                "tamaño": product["tamaño"],
                "observaciones": product.get("observaciones", ""),
                "existencias": existencias,  # Agregamos existencias
                "precio_unitario": precio_unitario
            }

    return {"found": False}



# Pagina de modificacion de productos
@app.route("/edit-product", methods=["POST", "GET"])
def edit_product():
    products = load_json("products.json")
    inventory = load_json("inventory.json")
    clave = request.form.get("clave") if request.method == "POST" else request.args.get("clave")

    product = next((p for p in products.get("products", []) if p["clave"] == clave), None)

    if request.method == "POST" and product:
        print("Datos recibidos:", request.form)  # 🔍 Depuración para ver los datos enviados

        product["articulo"] = request.form["articulo"]
        product["marca"] = request.form["marca"]
        product["categoria"] = request.form["categoria"]
        product["tamaño"] = request.form["tamaño"]
        product["observaciones"] = request.form["observaciones"]

        existencias_nuevas = int(request.form.get("existencias", 0))
        for item in inventory.get("inventory", []):
            if item["clave"] == clave:
                item["existencias"] = existencias_nuevas

        save_json("products.json", products)
        save_json("inventory.json", inventory)

        product["existencias"] = existencias_nuevas

        return render_template("edit_product.html", product=product, message="✅ Cambios guardados correctamente.")

    if product:
        product["existencias"] = next((item.get("existencias", 0) for item in inventory.get("inventory", []) if item["clave"] == clave), 0)

        return render_template("edit_product.html", product=product)

    return render_template("register_product.html", message="❌ Producto no encontrado.")



# Eliminar productos
@app.route("/delete-product", methods=["POST"])
def delete_product():
    products_data = load_json("products.json")  # Cargar productos
    clave = request.form["clave"]

    productos_antes = len(products_data.get("products", []))

    # Filtrar productos y eliminar el que coincide con la clave
    products_data["products"] = [p for p in products_data.get("products", []) if p["clave"] != clave]

    save_json("products.json", products_data)  # Guardar cambios

    if len(products_data.get("products", [])) < productos_antes:
        return redirect("/dashboard?message=✅ Producto eliminado correctamente.")
    else:
        return "❌ Error al eliminar producto."




# CLIENTES

# Registro de clientes
@app.route("/register-client", methods=["GET", "POST"])
def register_client():
    message = None

    if request.method == "POST":
        clients = load_json("clientes.json")  # Cargar clientes existentes

        new_client = {
            "clave": request.form["clave"],  # Ahora la clave viene del formulario
            "nombre": request.form["nombre"],
            "apellido": request.form["apellido"],
            "direccion": request.form["direccion"],
            "telefono": request.form["telefono"],
            "correo": request.form["correo"],
            "credito_autorizado": request.form["credito_autorizado"]
        }

        clients.setdefault("clients", []).append(new_client)
        save_json("clientes.json", clients)  # Guardar en el archivo de clientes
        message = "Cliente registrado correctamente."

    return render_template("registro_clientes.html", message=message)



# Busqueda de clientes
@app.route("/search-client", methods=["POST"])
def search_client():
    clients_data = load_json("clientes.json")  # Cargar clientes
    clave_busqueda = request.form["search_clave"]

    # Buscar el cliente en la lista de clientes
    client = next((c for c in clients_data.get("clients", []) if c["clave"] == clave_busqueda), None)
    saldo_actual_cliente = None

    if client:
        saldo_actual_cliente = calcular_saldo_cliente(client["clave"])
        return render_template("edit_client.html", client=client, saldo_actual=saldo_actual_cliente, message="✅ Cliente encontrado.")
    else:
        return render_template("registro_clientes.html", message="❌ Cliente no encontrado.")



# Calculo de saldos
def calcular_saldo_cliente(clave_cliente):
    ventas_data = load_json("ventas.json")
    clientes_data = load_json("clientes.json")
    cliente = next((c for c in clientes_data.get("clients", []) if c["clave"] == clave_cliente), None)
    credito_autorizado = 0.0
    saldo_pendiente_total = 0.0

    if cliente:
        try:
            credito_autorizado = float(cliente.get("credito_autorizado", 0))
        except ValueError:
            credito_autorizado = 0.0

        if ventas_data and ventas_data.get("ventas"):
            for venta in ventas_data["ventas"]:
                if venta.get("cliente_clave") == clave_cliente:
                    try:
                        saldo_pendiente_total += float(venta.get("saldo_a_pagar", 0.0))
                    except ValueError:
                        pass

    saldo_actual = credito_autorizado - saldo_pendiente_total
    return saldo_actual


# Encontrar Clientes
@app.route("/get-client", methods=["GET"])
def get_client():
    clave = request.args.get("clave")
    clients = load_json("clientes.json")

    # Buscar el cliente en clientes.json
    for client in clients.get("clients", []):
        if client["clave"] == clave:
            saldo_actual = calcular_saldo_cliente(clave)  # Calcular el saldo actual
            return {
                "found": True,
                "nombre": client["nombre"],
                "apellido": client["apellido"],
                "direccion": client["direccion"],
                "telefono": client["telefono"],
                "correo": client["correo"],
                "credito_autorizado": client["credito_autorizado"],
                "saldo_actual": saldo_actual  # Devolver el saldo actual
            }

    return {"found": False}



# Pagina de editar clientes
@app.route("/edit-client", methods=["POST", "GET"])
def edit_client():
    clients = load_json("clientes.json")
    clave = request.form.get("clave") if request.method == "POST" else request.args.get("clave")

    client = next((c for c in clients.get("clients", []) if c["clave"] == clave), None)

    if request.method == "POST" and client:
        print("Datos recibidos:", request.form)  # 🔍 Depuración para ver los datos enviados

        client["nombre"] = request.form["nombre"]
        client["apellido"] = request.form["apellido"]
        client["direccion"] = request.form["direccion"]
        client["telefono"] = request.form["telefono"]
        client["correo"] = request.form["correo"]
        client["credito_autorizado"] = request.form["credito_autorizado"]

        save_json("clientes.json", clients)  # Guardar cambios

        return render_template("edit_client.html", client=client, message="✅ Cambios guardados correctamente.")

    if client:
        return render_template("edit_client.html", client=client)

    return render_template("registro_clientes.html", message="❌ Cliente no encontrado.")




# INVENTARIOS

# Pagina de entradas
@app.route("/inventory-entry", methods=["GET", "POST"])
def inventory_entry():
    inventory_data = load_json("inventory.json")  # Cargar inventario
    message = None

    if request.method == "POST":
        clave = request.form["clave"]
        cantidad = float(request.form["cantidad"])  # Permitir decimales
        costo_unitario = float(request.form["costo_unitario"])
        precio_unitario = float(request.form["precio_unitario"])
        fecha_hora_entrada = datetime.now().isoformat()  # Obtiene la fecha y hora actual de la entrada

        # Buscar si el producto ya está en inventario
        for item in inventory_data.get("inventory", []):
            if item["clave"] == clave:
                # Asegurarse de que exista una lista de entradas para este producto
                if "entradas" not in item:
                    item["entradas"] = []

                item["entradas"].append({
                    "fecha_hora": fecha_hora_entrada,
                    "cantidad": cantidad,
                    "costo_unitario": costo_unitario,
                    "precio_unitario": precio_unitario
                })

                item["existencias"] = item.get("existencias", 0) + cantidad
                item["costo_unitario"] = costo_unitario  # Actualizar costo
                item["precio_unitario"] = precio_unitario # Actualizar precio
                save_json("inventory.json", inventory_data)
                message = f"✅ Entrada registrada el {datetime.fromisoformat(fecha_hora_entrada).strftime('%Y-%m-%d %H:%M:%S')}. Existencias actuales: {item['existencias']}."
                break
        else:
            # Si el producto es nuevo, agregarlo
            new_entry = {
                "clave": clave,
                "existencias": cantidad,
                "costo_unitario": costo_unitario,
                "precio_unitario": precio_unitario,
                "entradas": [{  # Inicializa la lista de entradas para el nuevo producto
                    "fecha_hora": fecha_hora_entrada,
                    "cantidad": cantidad,
                    "costo_unitario": costo_unitario,
                    "precio_unitario": precio_unitario
                }]
            }
            inventory_data.setdefault("inventory", []).append(new_entry)
            save_json("inventory.json", inventory_data)
            message = f"✅ Entrada registrada el {datetime.fromisoformat(fecha_hora_entrada).strftime('%Y-%m-%d %H:%M:%S')}. Existencias actuales: {new_entry['existencias']}."

    return render_template("inventory_entry.html", message=message)  # Permitir acceso por GET



# Pagina de Salidas y Devoluciones
@app.route("/inventory-management")
def inventory_management_page():
    return render_template("inventory_management.html")


# Salidas
@app.route("/inventory-exit", methods=["POST"])
def inventory_exit():
    inventory_data = load_json("inventory.json")  # Cargar inventario
    message = None

    if request.method == "POST":
        clave = request.form["clave_salida"]
        cantidad_salida = float(request.form["cantidad_salida"])
        motivo_salida = request.form.get("motivo_salida", "Sin motivo") # Obtener el motivo, con un valor por defecto
        fecha_hora_salida = datetime.now().isoformat()  # Obtiene la fecha y hora actual de la salida

        # Buscar el producto en el inventario
        for item in inventory_data.get("inventory", []):
            if item["clave"] == clave:
                if item.get("existencias", 0) >= cantidad_salida:
                    # Asegurarse de que exista una lista de salidas para este producto
                    if "salidas" not in item:
                        item["salidas"] = []

                    item["salidas"].append({
                        "fecha_hora": fecha_hora_salida,
                        "cantidad": cantidad_salida,
                        "motivo": motivo_salida
                    })

                    item["existencias"] -= cantidad_salida
                    save_json("inventory.json", inventory_data)
                    message = f"📤 Salida de {cantidad_salida} unidades de '{clave}' registrada el {datetime.fromisoformat(fecha_hora_salida).strftime('%Y-%m-%d %H:%M:%S')}. Existencias actuales: {item['existencias']}."
                else:
                    message = f"⚠️ No hay suficientes existencias de '{clave}' para realizar la salida (disponibles: {item.get('existencias', 0)})."
                break
        else:
            message = f"❌ No se encontró el producto con clave '{clave}' en el inventario."

    return render_template("inventory_management.html", message=message) # Puedes redirigir a otra página si lo prefieres


# Devoluciones
@app.route("/inventory-return", methods=["POST"])
def inventory_return():
    inventory_data = load_json("inventory.json")  # Cargar inventario
    message = None

    if request.method == "POST":
        clave_devolucion = request.form["clave_devolucion"]
        cantidad_devolucion = float(request.form["cantidad_devolucion"])
        motivo_devolucion = request.form.get("motivo_devolucion", "Sin motivo") # Obtener el motivo
        fecha_hora_devolucion = datetime.now().isoformat()  # Obtiene la fecha y hora actual de la devolución

        # Buscar el producto en el inventario
        for item in inventory_data.get("inventory", []):
            if item["clave"] == clave_devolucion:
                # Asegurarse de que exista una lista de devoluciones para este producto
                if "devoluciones" not in item:
                    item["devoluciones"] = []

                item["devoluciones"].append({
                    "fecha_hora": fecha_hora_devolucion,
                    "cantidad": cantidad_devolucion,
                    "motivo": motivo_devolucion
                })

                item["existencias"] = item.get("existencias", 0) + cantidad_devolucion
                save_json("inventory.json", inventory_data)
                message = f"🔄 Devolución de {cantidad_devolucion} unidades de '{clave_devolucion}' registrada el {datetime.fromisoformat(fecha_hora_devolucion).strftime('%Y-%m-%d %H:%M:%S')}. Existencias actuales: {item['existencias']}."
                break
        else:
            message = f"❌ No se encontró el producto con clave '{clave_devolucion}' en el inventario."

    return render_template("inventory_management.html", message=message) # Puedes redirigir a otra página si lo prefieres



# VENTAS

# Pagina de ventas
@app.route("/sales", methods=["GET", "POST"])
def sales():
    message = None
    clients = load_json("clientes.json").get("clients", [])  # Cargar clientes
    products = load_json("products.json").get("products", [])  # Cargar productos
    sales_data = load_json("ventas.json")  # Cargar ventas

    if request.method == "POST":
        # Clave de venta ingresada por el usuario
        clave_venta = request.form["venta_id"]

        # Buscar la venta existente
        venta_existente = next((v for v in sales_data.get("ventas", []) if v["venta_id"] == clave_venta), None)

        if venta_existente:
            # Si existe, cargar los datos de la venta desde JSON
            cliente = next((c for c in clients if c["clave"] == venta_existente["cliente_clave"]), None)
            productos = []
            for item in venta_existente["productos"]:
                producto = next((p for p in products if p["clave"] == item["clave"]), None)
                if producto:
                    productos.append({
                        "clave": item["clave"],
                        "descripcion": producto["articulo"],
                        "cantidad": item["cantidad"],
                        "precio_unitario": item["precio_unitario"],
                        "descuento": item["descuento"],
                        "impuesto": item["impuesto"],
                        "total": item["total"]
                    })

            return render_template("sales.html", client=cliente, products=productos, message="✅ Venta encontrada.")

        else:
            message = "❌ Venta no encontrada."

    return render_template("sales.html", clients=clients, products=products, message=message)



# Procesar venta
@app.route("/process-sale", methods=["POST"])
def process_sale():
    sales_data = load_json("ventas.json")
    clientes_data = load_json("clientes.json").get("clients", [])
    inventory_data = load_json("inventory.json").get("inventory", [])  # Cargar datos de inventario

    cliente_clave = request.form.get("cliente_clave")
    metodo_pago = request.form.get("metodo_pago")
    total_venta = float(request.form.get("total", "0"))  # Obtener el total al principio
    notas = request.form.get("notas", "").strip()  # Capturar notas

    # Verificar el saldo de crédito si el método de pago es 'credito'
    if metodo_pago.lower() == 'credito':
        saldo_disponible = calcular_saldo_cliente(cliente_clave)
        if saldo_disponible < total_venta:
            return render_template("sales.html", message=f"❌ Error: Saldo de crédito insuficiente. Saldo disponible: {saldo_disponible:.2f}, Total de la venta: {total_venta:.2f}")

    productos_vendidos = []
    productos = request.form.getlist("clave[]")
    cantidades_str = request.form.getlist("cantidad[]")  # Obtener cantidades como string
    precios = request.form.getlist("precio[]")
    descuentos = request.form.getlist("descuento[]")
    impuestos = request.form.getlist("impuesto[]")
    cantidad_pagada = request.form.get("cantidad_pagada", "0")
    saldo_a_pagar = request.form.get("saldo_a_pagar", "0")

    try:
        cantidad_pagada = float(cantidad_pagada)
        saldo_a_pagar = float(saldo_a_pagar)
    except ValueError:
        return render_template("sales.html", message="❌ Error: Los valores numéricos de la venta no son válidos.")

    folio_venta = "VENTA-" + str(len(sales_data.get("ventas", [])) + 1)
    fecha_hora_venta = datetime.now().isoformat()

    # Buscar información del cliente
    nombre_cliente = ""
    apellido_cliente = ""
    for cliente in clientes_data:
        if cliente.get("clave") == cliente_clave:
            nombre_cliente = cliente.get("nombre", "")
            apellido_cliente = cliente.get("apellido", "")
            break

    nueva_venta = {
        "folio": folio_venta,
        "fecha_hora": fecha_hora_venta,
        "cliente_clave": cliente_clave,
        "nombre_cliente": nombre_cliente,
        "apellido_cliente": apellido_cliente,
        "productos": [],
        "total": total_venta,
        "metodo_pago": metodo_pago,
        "cantidad_pagada": cantidad_pagada,
        "saldo_a_pagar": saldo_a_pagar,
        "notas": notas  # Agregar notas a la venta
    }

    for i in range(len(productos)):
        clave_producto = productos[i]
        try:
            cantidad_solicitada = float(cantidades_str[i])  # Convertir cantidad a decimal
        except ValueError:
            return render_template("sales.html", message=f"❌ Error: La cantidad para el producto {clave_producto} no es válida.")

        nombre_articulo = ""
        existencias_producto = 0
        for item in inventory_data:  # Iterar sobre los datos de inventario
            if item.get("clave") == clave_producto:
                nombre_articulo_inv = ""
                products_data_local = load_json("products.json").get("products", [])  # Cargar products.json para obtener el nombre del artículo
                for prod in products_data_local:
                    if prod.get("clave") == clave_producto:
                        nombre_articulo_inv = prod.get("articulo", "")
                        break
                nombre_articulo = nombre_articulo_inv
                try:
                    existencias_producto = float(item.get("existencias", 0))  # Manejar existencias con decimales
                except ValueError:
                    return render_template("sales.html", message=f"❌ Error: Las existencias para el producto {clave_producto} no son válidas.")
                break
        else:
            return render_template("sales.html", message=f"❌ Error: No se encontró el producto {clave_producto} en el inventario.")

        if cantidad_solicitada > existencias_producto:
            return render_template("sales.html", message=f"❌ Error: No hay suficientes existencias para el producto {nombre_articulo} ({clave_producto}). Solicitado: {cantidad_solicitada}, Disponible: {existencias_producto}")

        producto_detalle = {
            "clave": clave_producto,
            "nombre_articulo": nombre_articulo,
            "cantidad": cantidades_str[i],
            "precio_unitario": precios[i],
            "descuento": descuentos[i],
            "impuesto": impuestos[i]
        }
        nueva_venta["productos"].append(producto_detalle)
        productos_vendidos.append({"clave": clave_producto, "cantidad": cantidades_str[i]})

    sales_data.setdefault("ventas", []).append(nueva_venta)
    save_json("ventas.json", sales_data)

    # Actualizar el inventario después de guardar la venta
    for item_vendido in productos_vendidos:
        update_inventory(item_vendido["clave"], item_vendido["cantidad"])

    return render_template("sales.html", message=f"✅ Venta procesada exitosamente. Folio: {folio_venta}")



# Ver informacion ventas
@app.route("/get-sale", methods=["GET"])
def get_sale():
    clave_venta = request.args.get("clave")
    sales_data = load_json("ventas.json")
    clients = load_json("clientes.json").get("clients", [])
    products = load_json("products.json").get("products", [])

    venta = next((v for v in sales_data.get("ventas", []) if v["venta_id"] == clave_venta), None)

    if venta:
        cliente = next((c for c in clients if c["clave"] == venta["cliente_clave"]), None)
        productos = []
        for item in venta["productos"]:
            producto = next((p for p in products if p["clave"] == item["clave"]), None)
            if producto:
                productos.append({
                    "clave": item["clave"],
                    "descripcion": producto["articulo"],
                    "existencias": producto.get("existencias", 0),
                    "cantidad": item["cantidad"],
                    "precio_unitario": item["precio_unitario"],
                    "descuento": item["descuento"],
                    "impuesto": item["impuesto"]
                })

        return jsonify({
            "found": True,
            "cliente_clave": venta["cliente_clave"],
            "metodo_pago": venta["metodo_pago"],
            "productos": productos
        })

    return jsonify({"found": False})


# Actualizar existencias
def update_inventory(clave_producto, cantidad_vendida):
    inventory_data = load_json("inventory.json")
    if 'inventory' in inventory_data:
        for item in inventory_data['inventory']:
            if item['clave'] == clave_producto:
                item['existencias'] = float(item['existencias']) - float(cantidad_vendida)
                save_json("inventory.json", inventory_data)
                return True
    return False



# COBRANZA

# Pagina de Cobranza
@app.route("/billing")
def billing():
    if 'user' in session:
        return render_template("cobranza.html")


# Devolver datos del cliente
@app.route("/get-client-debts", methods=["GET"])
def get_client_debts():
    clave_cliente = request.args.get("clave")
    clients_data = load_json("clientes.json")
    ventas_data = load_json("ventas.json")
    cliente = next((c for c in clients_data.get("clients", []) if c["clave"] == clave_cliente), None)

    if not cliente:
        return {"found": False}

    ventas_pendientes = []
    saldo_pendiente_total = 0.0

    if ventas_data and ventas_data.get("ventas"):
        for venta in ventas_data["ventas"]:
            if venta.get("cliente_clave") == clave_cliente and venta.get("saldo_a_pagar", 0.0) > 0:
                ventas_pendientes.append({
                    "folio": venta["folio"],
                    "saldo_a_pagar": venta["saldo_a_pagar"]
                })
                saldo_pendiente_total += venta["saldo_a_pagar"]

    return {
        "found": True,
        "nombre": cliente["nombre"],
        "apellido": cliente["apellido"],
        "saldo_pendiente_total": saldo_pendiente_total,
        "ventas_pendientes": ventas_pendientes
    }


# Procesar pagos
@app.route("/process-payment", methods=["POST"])
def process_payment():
    data = request.get_json()
    cliente_clave = data.get("cliente_clave")
    pagos = data.get("pagos", {})

    if not cliente_clave or not pagos:
        return {"success": False, "message": "Error: Faltan datos para procesar el pago."}

    ventas_data = load_json("ventas.json")
    if ventas_data and ventas_data.get("ventas"):
        for venta in ventas_data["ventas"]:
            if venta.get("cliente_clave") == cliente_clave and venta["folio"] in pagos:
                cantidad_pagada = pagos[venta["folio"]]
                fecha_hora_pago = datetime.now().isoformat()  # Obtiene la fecha y hora actual del pago

                # Asegurarse de que exista una lista de pagos para esta venta
                if "pagos_realizados" not in venta:
                    venta["pagos_realizados"] = []

                venta["pagos_realizados"].append({
                    "fecha_hora": fecha_hora_pago,
                    "monto": cantidad_pagada
                })

                venta["cantidad_pagada"] = float(venta.get("cantidad_pagada", 0)) + cantidad_pagada
                venta["saldo_a_pagar"] = float(venta.get("saldo_a_pagar", 0)) - cantidad_pagada
                if venta["saldo_a_pagar"] < 0:
                    venta["saldo_a_pagar"] = 0.0 # Evitar saldos negativos

        save_json("ventas.json", ventas_data)
        return {"success": True, "message": "Pago procesado exitosamente."}
    else:
        return {"success": False, "message": "Error: No se encontraron ventas."}



# REPORTES

# Ir Pagina de Reportes
@app.route('/reportes')
def reportes():
    return render_template('reportes.html')


# Exportar Ventas con Notas
@app.route('/reportes/export/ventas')
def export_sales_excel():
    ventas_data = load_json("ventas.json").get("ventas", [])

    wb = Workbook()
    ws = wb.active
    ws.append(['Folio', 'Fecha y Hora', 'Cliente', 'Artículos Vendidos', 'Total', 'Método de Pago', 'Notas'])  # Agregar columna de notas

    for venta in ventas_data:
        articulos_vendidos = [producto.get('nombre_articulo', '') for producto in venta.get('productos', [])]
        nombres_articulos = "\n".join(articulos_vendidos)  # Unir los nombres con saltos de línea
        notas = venta.get('notas', '')  # Obtener las notas de la venta

        ws.append([
            venta.get('folio', ''),
            venta.get('fecha_hora', ''),
            venta.get('cliente_clave', ''),
            nombres_articulos,  # Agregar la lista de nombres de artículos
            venta.get('total', ''),
            venta.get('metodo_pago', ''),
            notas  # Agregar la columna de notas
        ])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(output, download_name='reporte_ventas.xlsx', as_attachment=True)



# Exportar Existencias
@app.route('/reportes/export/existencias')
def export_inventory_excel():
    inventory_data = load_json("inventory.json").get("inventory", [])
    products_data = load_json("products.json").get("products", [])
    productos_dict = {producto['clave']: producto['articulo'] for producto in products_data}

    wb = Workbook()
    ws = wb.active
    ws.append(['Clave', 'Artículo', 'Existencias', 'Costo Unitario', 'Precio Unitario'])  # Nuevo encabezado

    for item in inventory_data:
        clave_producto = item.get('clave', '')
        nombre_articulo = productos_dict.get(clave_producto, 'No encontrado')

        ws.append([
            clave_producto,
            nombre_articulo,
            item.get('existencias', ''),
            item.get('costo_unitario', ''),
            item.get('precio_unitario', '')
        ])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(output, download_name='reporte_existencias.xlsx', as_attachment=True)


# Exportar Saldos de Clientes
@app.route('/reportes/export/saldos')
def export_balances_excel():
    ventas_data = load_json("ventas.json").get("ventas", [])
    clientes_data = load_json("clientes.json").get("clients", []) # Cargar datos de clientes
    clientes_dict = {cliente['clave']: {'nombre': cliente.get('nombre', ''), 'apellido': cliente.get('apellido', '')} for cliente in clientes_data}

    wb = Workbook()
    ws = wb.active
    ws.append(['Cliente', 'Folio de Venta', 'Total Venta', 'Cantidad Pagada', 'Saldo Pendiente'])

    for venta in ventas_data:
        cliente_clave = venta.get('cliente_clave', '')
        cliente_info = clientes_dict.get(cliente_clave, {'nombre': 'No encontrado', 'apellido': ''})
        nombre_completo_cliente = f"{cliente_info['nombre']} {cliente_info.get('apellido', '')}".strip()

        ws.append([
            nombre_completo_cliente,
            venta.get('folio', ''),
            venta.get('total', ''),
            venta.get('cantidad_pagada', ''),
            venta.get('saldo_a_pagar', '')
        ])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(output, download_name='reporte_saldos_clientes.xlsx', as_attachment=True)


# Exportar Catalogo de Productos
@app.route('/reportes/export/productos')
def export_products_excel():
    products_data = load_json("products.json").get("products", [])

    wb = Workbook()
    ws = wb.active
    ws.append(['Clave', 'Artículo', 'Marca', 'Categoría', 'Tamaño', 'Observaciones'])  # Encabezados actualizados
    for product in products_data:
        ws.append([
            product.get('clave', ''),
            product.get('articulo', ''),  # Usar 'articulo' en lugar de 'nombre'
            product.get('marca', ''),
            product.get('categoria', ''),
            product.get('tamaño', ''),
            product.get('observaciones', '')
        ])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(output, download_name='catalogo_productos.xlsx', as_attachment=True)


#  Exportar Base de Clientes
@app.route('/reportes/export/clientes')
def export_clients_excel():
    clients_data = load_json("clientes.json").get("clients", [])  # Usar "clients" (plural)

    wb = Workbook()
    ws = wb.active
    ws.append(['Clave', 'Nombre', 'Apellido', 'Dirección', 'Teléfono', 'Correo', 'Crédito Autorizado'])
    for client in clients_data:
        ws.append([
            client.get('clave', ''),
            client.get('nombre', ''),
            client.get('apellido', ''),
            client.get('direccion', ''),
            client.get('telefono', ''),
            client.get('correo', ''),
            client.get('credito_autorizado', '')
        ])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(output, download_name='base_de_clientes.xlsx', as_attachment=True)



# Carga de ventas y genera gráfica de importes por día
def generate_sales_graph(start_date=None, end_date=None):
    # Lógica para cargar y filtrar datos de ventas por fecha
    ventas_data = load_json("ventas.json").get("ventas", [])
    if start_date and end_date:
        # Filtrar ventas por el rango de fechas (pendiente de implementar)
        ventas_filtradas = []
        for venta in ventas_data:
            fecha_venta = venta.get('fecha_hora').split('T')[0]
            if start_date <= fecha_venta <= end_date:
                ventas_filtradas.append(venta)
        ventas_data = ventas_filtradas

    # Agrupar ventas por fecha y sumar los totales
    sales_by_date = {}
    for venta in ventas_data:
        fecha_venta = venta.get('fecha_hora').split('T')[0]
        total_venta = float(venta.get('total', 0))
        sales_by_date[fecha_venta] = sales_by_date.get(fecha_venta, 0) + total_venta

    dates_sorted = sorted(sales_by_date.keys())
    total_sales = [sales_by_date[date] for date in dates_sorted]

    plt.figure(figsize=(10, 6))
    plt.plot(dates_sorted, total_sales, marker='o')
    plt.title('Importe Total de Ventas por Día')
    plt.xlabel('Fecha')
    plt.ylabel('Importe Total de Ventas')
    plt.grid(True)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    # Guardar la gráfica en un formato que se pueda mostrar en HTML
    img = BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode('utf8')
    plt.close()

    return plot_url


# Generador de graficos de ventas
@app.route('/reportes/grafica/ventas')
def view_sales_graph():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    plot_url = generate_sales_graph(start_date, end_date)
    return render_template('graph_viewer.html', plot_url=plot_url, report_title='Gráfica del Importe Total de Ventas por Día')



# Carga de inventarios
def generate_inventory_graph():
    # Lógica para cargar datos de inventario
    inventory_data = load_json("inventory.json").get("inventory", [])
    # Lógica para generar la gráfica (ejemplo: cantidad de productos en stock)
    product_names = [item.get('clave') for item in inventory_data]
    stock_levels = [item.get('existencias') for item in inventory_data]

    plt.figure(figsize=(10, 6))
    plt.bar(product_names, stock_levels)
    plt.title('Niveles de Existencia por Producto')
    plt.xlabel('Producto')
    plt.ylabel('Cantidad en Stock')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    img = BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode('utf8')
    plt.close()

    return plot_url


#Grafico de Existencias
@app.route('/reportes/grafica/inventario')
def view_inventory_graph():
    plot_url = generate_inventory_graph()
    return render_template('graph_viewer.html', plot_url=plot_url, report_title='Gráfica de Niveles de Existencia')


#Carga de Saldos
def generate_balances_graph():
    # Lógica para cargar datos de saldos de clientes
    ventas_data = load_json("ventas.json").get("ventas", [])
    balances = {}
    for venta in ventas_data:
        cliente = venta.get('cliente_clave')
        saldo = float(venta.get('saldo_a_pagar', 0))
        balances[cliente] = balances.get(cliente, 0) + saldo

    clients = list(balances.keys())
    saldo_pendiente = list(balances.values())

    plt.figure(figsize=(10, 6))
    plt.bar(clients, saldo_pendiente)
    plt.title('Saldos Pendientes por Cliente')
    plt.xlabel('Cliente')
    plt.ylabel('Saldo Pendiente')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    img = BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode('utf8')
    plt.close()

    return plot_url


# Grafico de Saldos
@app.route('/reportes/grafica/saldos')
def view_balances_graph():
    plot_url = generate_balances_graph()
    return render_template('graph_viewer.html', plot_url=plot_url, report_title='Gráfica de Saldos Pendientes por Cliente')


# Ir a pagina de graficos
@app.route('/graph_viewer')
def graph_viewer():
    plot_url = request.args.get('plot_url', '')
    report_title = request.args.get('report_title', 'Gráfica')
    return render_template('graph_viewer.html', plot_url=plot_url, report_title=report_title)



if __name__ == "__main__":
    if getattr(sys, 'frozen', False):
        # Ejecutándose como un ejecutable empaquetado
        threading.Thread(target=open_browser, daemon=True).start()
        app.run(debug=False, use_reloader=False)
    else:
        # Ejecutándose como un script de Python normal (en desarrollo)
        app.run(debug=True)