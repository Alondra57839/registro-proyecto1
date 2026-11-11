import re
import pytesseract
from PIL import Image, ImageOps

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

PATRON_CURP = re.compile(r"[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d")
ETIQUETAS_FIN = ("CLAVE", "CURP", "ESTADO", "FECHA", "SEXO", "SECCION", "SECCIÓN", "VIGENCIA", "AÑO")

def _texto(ruta):
    img = Image.open(ruta)
    img = ImageOps.exif_transpose(img)              # corrige fotos giradas del celular
    img = ImageOps.grayscale(img)
    img = ImageOps.autocontrast(img)
    img = img.resize((img.width * 2, img.height * 2))  # agrandar mejora la lectura
    return pytesseract.image_to_string(img, lang="spa")

def _bloque_tras(lineas, etiqueta, max_lineas):
    """Devuelve las líneas que siguen a una etiqueta (NOMBRE, DOMICILIO)."""
    for i, l in enumerate(lineas):
        if etiqueta in l.upper():
            salida = []
            for sig in lineas[i + 1:i + 1 + max_lineas]:
                if any(sig.upper().startswith(e) for e in ETIQUETAS_FIN):
                    break
                salida.append(sig)
            return " ".join(salida)
    return "No encontrado"

def leer_ine(ruta):
    texto = _texto(ruta)
    lineas = [l.strip() for l in texto.splitlines() if l.strip()]

    compacto = re.sub(r"\s+", "", texto.upper())
    m = PATRON_CURP.search(compacto)

    return {
        "curp": m.group(0) if m else "No encontrado",
        "nombre": _bloque_tras(lineas, "NOMBRE", 3),
        "domicilio": _bloque_tras(lineas, "DOMICILIO", 3),
        "texto_crudo": texto,   # útil para depurar
    }