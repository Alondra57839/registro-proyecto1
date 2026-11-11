from getpass import getpass
from werkzeug.security import check_password_hash
from app import obtener_conexion

usuario = "atencion"

contrasena = getpass("Escribe la contraseña de atencion: ")

conexion = obtener_conexion()

try:
    cuenta = conexion.execute(
        "SELECT contrasena FROM usuarios WHERE usuario = ?",
        (usuario,)
    ).fetchone()

    if cuenta:
        if check_password_hash(cuenta["contrasena"], contrasena):
            print("La contraseña SÍ coincide.")
        else:
            print("La contraseña NO coincide.")
    else:
        print("El usuario no existe.")

finally:
    conexion.close() 