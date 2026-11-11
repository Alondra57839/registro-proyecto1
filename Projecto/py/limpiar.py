import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUTA_BASE_DATOS = os.path.join(BASE_DIR, "registro_apoyos.db")

conexion = sqlite3.connect(RUTA_BASE_DATOS)

total = conexion.execute("SELECT COUNT(*) FROM apoyos").fetchone()[0]
print(f"Hay {total} registros en total.")

respuesta = input("¿Borrar TODOS los registros de la tabla apoyos? (si/no): ")

if respuesta.strip().lower() == "si":
    conexion.execute("DELETE FROM apoyos")
    conexion.execute("DELETE FROM sqlite_sequence WHERE name = 'apoyos'")
    conexion.commit()
    print("Listo, se borraron todos los registros y se reinició el contador de id.")
else:
    print("Cancelado, no se borró nada.")

conexion.close()