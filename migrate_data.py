# migrate_data.py (o donde lo hayas puesto)

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from datetime import datetime
import sys

# --- INICIALIZACIÓN DE FIREBASE ---
try:
    cred = credentials.Certificate('firebase_credentials.json')
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase inicializado correctamente para migración.")
except Exception as e:
    print(f"Error al inicializar Firebase para migración: {e}")
    sys.exit(1)
# --- FIN INICIALIZACIÓN DE FIREBASE ---


def migrate_sales_data():
    print("Iniciando migración de datos de ventas...")
    sales_ref = db.collection('sales')

    all_sales_docs = sales_ref.stream()

    updated_count = 0
    for sale_doc in all_sales_docs:
        sale_id = sale_doc.id
        sale_data = sale_doc.to_dict()

        needs_update = False

        # --- Asegurar 'folio' ---
        if "folio" not in sale_data:
            sale_data["folio"] = sale_id
            needs_update = True

        # --- Asegurar 'cantidad_pagada' como número ---
        if "cantidad_pagada" not in sale_data or not isinstance(sale_data["cantidad_pagada"], (int, float)):
            try:
                sale_data["cantidad_pagada"] = float(sale_data.get("cantidad_pagada", 0.0))
            except ValueError:
                sale_data["cantidad_pagada"] = 0.0
            needs_update = True

        # --- Asegurar 'saldo_a_pagar' como número ---
        if "saldo_a_pagar" not in sale_data or not isinstance(sale_data["saldo_a_pagar"], (int, float)):
            try:
                total = float(sale_data.get("total", 0.0))
                # Usar el valor ya asegurado de cantidad_pagada para el cálculo
                sale_data["saldo_a_pagar"] = max(0.0, total - sale_data.get("cantidad_pagada", 0.0))
            except ValueError:
                sale_data["saldo_a_pagar"] = 0.0
            needs_update = True

        # --- Asegurar 'pagos_realizados' como lista ---
        if "pagos_realizados" not in sale_data or not isinstance(sale_data["pagos_realizados"], list):
            temp_pagos_realizados = []
            # Si ya había una cantidad pagada inicial, y no es 0, añádela como el primer pago
            if sale_data.get("cantidad_pagada", 0.0) > 0 and sale_data.get("metodo_pago", "").lower() != 'credito': # No agregar si es credito y no se pagó nada
                 temp_pagos_realizados.append({
                     "fecha_hora": sale_data.get("fecha_hora", datetime.now().isoformat()),
                     "monto": sale_data["cantidad_pagada"]
                 })
            sale_data["pagos_realizados"] = temp_pagos_realizados
            needs_update = True

        # --- Asegurar campos numéricos dentro de 'productos' ---
        if "productos" in sale_data and isinstance(sale_data["productos"], list):
            for prod in sale_data["productos"]:
                for field in ["cantidad", "precio_unitario", "descuento", "impuesto", "total_linea"]:
                    if field in prod and not isinstance(prod[field], (int, float)):
                        try:
                            prod[field] = float(prod[field])
                            needs_update = True
                        except ValueError:
                            prod[field] = 0.0
                            needs_update = True


        if needs_update:
            try:
                sales_ref.document(sale_id).set(sale_data) # Actualiza el documento
                updated_count += 1
                print(f"  Documento {sale_id} actualizado.")
            except Exception as e:
                print(f"  Error al actualizar el documento {sale_id}: {e}")

    print(f"Migración completada. Se actualizaron {updated_count} documentos de venta.")

if __name__ == "__main__":
    migrate_sales_data()