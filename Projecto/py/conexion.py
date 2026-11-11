import mysql.connector

try:
    conexion = mysql.connector.connect(
        host="localhost",       
        user="root",            
        password="root12", 
        database="apoyos"
    )

    if conexion.is_connected():
        print("¡Conexión exitosa con la base de datos apoyos!")

        # Crear un cursor para ejecutar consultas SQL
        cursor = conexion.cursor()
        cursor.execute("SELECT DATABASE();")
        registro = cursor.fetchone()
        print(f"Conectado a la BD: {registro[0]}")

        # Cerrar cursor y conexión
        cursor.close()
        conexion.close()
        print("Conexión cerrada.")

except mysql.connector.Error as error:
    print(f"Error al conectar a MySQL: {error}")
