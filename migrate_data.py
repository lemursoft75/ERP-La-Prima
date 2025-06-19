# SCRIPT DE MIGRACIÓN DE DATOS (EJECUTAR SOLO UNA VEZ)
# Agrega esto temporalmente a tu app.py o a un script separado
# y ejecútalo solo cuando sea necesario.

from firebase_admin import firestore

from app import db


# Asegúrate de que Firebase ya está inicializado (cred, db)

def migrate_sales_data():
    print("Iniciando migración de datos de ventas...")
    sales_ref = db.collection('sales')

    # Obtener todas las ventas
    all_sales = sales_ref.stream()

    updated_count = 0
    for sale_doc in all_sales:
        sale_id = sale_doc.id
        sale_data = sale_doc.to_dict()

        needs_update = False

        # Verificar si faltan campos de pago
        if "cantidad_pagada" not in sale_data:
            sale_data["cantidad_pagada"] = 0.0
            needs_update = True

        if "saldo_a_pagar" not in sale_data:
            # Si el saldo a pagar no existe, asume que es el total de la venta
            # o si ya está pagado (cantidad_pagada == total) entonces 0
            total = float(sale_data.get("total", 0.0))
            cantidad_pagada_existente = float(sale_data.get("cantidad_pagada", 0.0))
            sale_data["saldo_a_pagar"] = max(0.0, total - cantidad_pagada_existente)
            needs_update = True

        # Opcional: Asegurarse de que el campo 'folio' exista y sea el ID del documento
        if "folio" not in sale_data:
            sale_data["folio"] = sale_id
            needs_update = True

        if "pagos_realizados" not in sale_data:
            sale_data["pagos_realizados"] = []
            needs_update = True

        if needs_update:
            try:
                sales_ref.document(sale_id).set(sale_data)  # Actualiza el documento
                updated_count += 1
                print(f"  Documento {sale_id} actualizado.")
            except Exception as e:
                print(f"  Error al actualizar el documento {sale_id}: {e}")

    print(f"Migración completada. Se actualizaron {updated_count} documentos de venta.")

# Llamar a la función de migración (¡solo una vez, o cuando necesites arreglar datos!)
# Puedes descomentar la siguiente línea para ejecutarla, luego vuelve a comentarla.
# if __name__ == "__main__":
#     # Asegúrate de que Flask no se ejecute en el mismo proceso si usas esto en app.py directamente
#     # O crea un script separado para ejecutar solo la migración.
#     migrate_sales_data()
#     app.run(debug=True)