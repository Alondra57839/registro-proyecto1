import csv
import difflib
import os
import re
import sys
import unicodedata
import cv2
import pytesseract
 
 
# Ajusta esta ruta si Tesseract está instalado en otra carpeta.
RUTA_TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(RUTA_TESSERACT):
    pytesseract.pytesseract.tesseract_cmd = RUTA_TESSERACT
 
CARPETA = os.path.dirname(os.path.abspath(__file__))
RUTA_IMAGEN = os.path.join(CARPETA, "uploads", "mi_ine.jpg")
RUTA_COLONIAS = os.path.join(CARPETA, "colonias_cortazar.csv")  # opcional
 
# Fracción izquierda de la credencial que se descarta (ahí está la foto).
# Si tu foto de la INE incluye mucho fondo, recórtala antes o ajusta esto.
RECORTE_IZQ = 0.30
GUARDAR_DEBUG = True  # guarda debug_*.png para ver lo que "ve" Tesseract
 
ETIQUETAS_FIN = [
    "DOMICILIO", "CLAVE DE ELECTOR", "CURP", "FECHA DE NACIMIENTO",
    "ANO DE REGISTRO", "SECCION", "VIGENCIA", "EMISION", "LOCALIDAD",
    "MUNICIPIO",
]
 
 
def preparar_variantes(ruta):
    """Devuelve varias versiones de la imagen; se prueba OCR en todas."""
    imagen = cv2.imread(ruta)
    if imagen is None:
        raise FileNotFoundError(
            f"No se pudo abrir la imagen: {ruta}\n"
            "Revisa que exista y que el nombre sea mi_ine.jpg."
        )
 
    # Normaliza el tamaño: Tesseract rinde mejor con texto de ~30 px de alto.
    ancho = imagen.shape[1]
    escala = 2000 / ancho
    interp = cv2.INTER_AREA if escala < 1 else cv2.INTER_CUBIC
    imagen = cv2.resize(imagen, None, fx=escala, fy=escala,
                        interpolation=interp)
 
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    gris = gris[:, int(gris.shape[1] * RECORTE_IZQ):]
 
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contraste = clahe.apply(gris)
    suave = cv2.medianBlur(contraste, 3)
    adaptativa = cv2.adaptiveThreshold(
        suave, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 41, 15
    )
 
    variantes = [("contraste", contraste), ("adaptativa", adaptativa)]
    if GUARDAR_DEBUG:
        for nombre, img in variantes:
            cv2.imwrite(os.path.join(CARPETA, f"debug_{nombre}.png"), img)
    return variantes
 
 
def obtener_texto(imagen, psm):
    configuracion = f"--oem 3 --psm {psm}"
    try:
        return pytesseract.image_to_string(
            imagen, lang="spa", config=configuracion
        )
    except pytesseract.TesseractNotFoundError:
        raise RuntimeError("No se encontró Tesseract. Revisa RUTA_TESSERACT.")
    except pytesseract.TesseractError as error:
        raise RuntimeError(
            "No se pudo ejecutar Tesseract. Comprueba que el idioma "
            "español (spa) esté instalado. Detalle: " + str(error)
        )
 
 
# ----------------------------------------------------------------- texto
def normalizar(texto):
    """Mayúsculas y sin acentos (conserva la Ñ)."""
    texto = texto.upper().replace("Ñ", "\0")
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto.replace("\0", "Ñ")
 
 
def limpiar_lineas(texto):
    lineas = []
    for linea in normalizar(texto).splitlines():
        linea = re.sub(r"[^A-ZÑ0-9 .,#/:\-]", " ", linea)
        linea = re.sub(r"\s+", " ", linea).strip(" .,:-")
        if len(linea) >= 3:
            lineas.append(linea)
    return lineas
 
 
def contiene_etiqueta(linea, etiqueta, umbral=0.78):
    """Busca una etiqueta tolerando errores del OCR (DOMICILI0, NOMBRF...)."""
    palabras = linea.split()
    n = len(etiqueta.split())
    for i in range(len(palabras) - n + 1):
        trozo = " ".join(palabras[i:i + n])
        if difflib.SequenceMatcher(None, trozo, etiqueta).ratio() >= umbral:
            return True
    return False
 
 
def bloque_despues(lineas, etiqueta, max_lineas=4):
    """Líneas que siguen a una etiqueta, hasta la siguiente etiqueta."""
    for i, linea in enumerate(lineas):
        if contiene_etiqueta(linea, etiqueta):
            bloque = []
            for otra in lineas[i + 1:i + 1 + max_lineas]:
                if any(contiene_etiqueta(otra, f) for f in ETIQUETAS_FIN):
                    break
                bloque.append(otra)
            return bloque
    return []

def extraer_seccion(lineas):
    """Busca la etiqueta SECCION seguida de 4 dígitos (tolera O->0, I->1)."""
    tabla = str.maketrans("OISBZ", "01582")
    directo = re.search(r"SECCI[O0]N\W*(\d{4})(?!\d)", " ".join(lineas))
    if directo:
        return directo.group(1)
    for linea in lineas:
        palabras = linea.split()
        for i, palabra in enumerate(palabras):
            similar = difflib.SequenceMatcher(None, palabra, "SECCION").ratio()
            if similar < 0.78:
                continue
            # Los 4 dígitos pueden venir pegados o en la palabra siguiente.
            resto = palabra[len("SECCION"):] if palabra.startswith("SECCION") else ""
            candidatos = ([resto] if resto else []) + palabras[i + 1:i + 3]
            for candidato in candidatos:
                candidato = candidato.strip(".:,-").translate(tabla)
                if re.fullmatch(r"\d{4}", candidato):
                    return candidato
    return ""
 
 
def buscar_cp(lineas):
    """Busca 5 dígitos corrigiendo confusiones típicas (O->0, I->1...)."""
    tabla = str.maketrans("OISBZ", "01582")
    for linea in lineas:
        for token in linea.replace(",", " ").split():
            if len(token) == 5:
                candidato = token.translate(tabla)
                digitos = sum(c.isdigit() for c in token)
                if candidato.isdigit() and digitos >= 3:
                    return candidato
    return ""
 
def parece_inicio_domicilio(linea):
    return bool(re.match(
        r"^(C\.?\s|CALLE\b|AV\.?\s|AVENIDA\b|BLVD\b|PRIV\b|"
        r"COL\.?\s|COLONIA\b|DOMICILIO\b)", linea
    ))
 
 
def buscar_cp(lineas):
    """Busca 5 dígitos corrigiendo confusiones típicas (O->0, I->1...)."""
    tabla = str.maketrans("OISBZ", "01582")
    for linea in lineas:
        for token in linea.replace(",", " ").split():
            if len(token) == 5:
                candidato = token.translate(tabla)
                digitos = sum(c.isdigit() for c in token)
                if candidato.isdigit() and digitos >= 3:
                    return candidato
    return ""
 
 
def extraer_curp(texto):
    texto_unido = re.sub(r"\s+", "", normalizar(texto))
    patron = (
        r"[A-Z][AEIOUX][A-Z]{2}\d{6}[HM][A-Z]{2}"
        r"[B-DF-HJ-NP-TV-Z]{3}[A-Z0-9]\d"
    )
    coincidencia = re.search(patron, texto_unido)
    return coincidencia.group(0) if coincidencia else ""
 
 
def cargar_colonias(ruta=RUTA_COLONIAS):
    """Catálogo opcional (columnas: colonias, cp, TIPO)."""
    if not os.path.exists(ruta):
        return []
    filas = None
    for codificacion in ("utf-8-sig", "latin-1"):
        try:
            with open(ruta, encoding=codificacion, newline="") as archivo:
                filas = list(csv.DictReader(archivo))
            break
        except UnicodeDecodeError:
            continue
    if filas is None:
        return []
 
    catalogo = []
    for fila in filas:
        f = {(k or "").strip().lower(): (v or "").strip()
             for k, v in fila.items()}
        if f.get("colonias"):
            catalogo.append((normalizar(f["colonias"]), f.get("cp", "")))
    return catalogo
 
 
def ajustar_con_catalogo(lineas_dom, cp, catalogo):
    """Corrige colonia y CP comparando contra el catálogo del municipio."""
    if not catalogo:
        return "", cp
    candidatos = [c for c in catalogo if c[1] == cp] or catalogo
 
    mejor, mejor_ratio = None, 0.0
    for linea in lineas_dom:
        texto = re.sub(r"\d{5}", "", linea)
        texto = re.sub(r"^(COL\.?|COLONIA)\s+", "", texto).strip(" .,-")
        if len(texto) < 4:
            continue
        for colonia, cp_cat in candidatos:
            ratio = difflib.SequenceMatcher(None, texto, colonia).ratio()
            if ratio > mejor_ratio:
                mejor, mejor_ratio = (colonia, cp_cat), ratio
 
    if mejor and mejor_ratio >= 0.75:
        return mejor[0], (cp or mejor[1])
    return "", cp
 
 
def extraer_domicilio(lineas, catalogo):
    """
    Frente de la INE:
        DOMICILIO
        CALLE Y NUMERO
        COL. COLONIA  CP
        MUNICIPIO, ESTADO
    """
    bloque = bloque_despues(lineas, "DOMICILIO", max_lineas=4)[:3]
    cp = buscar_cp(bloque)
    colonia, cp = ajustar_con_catalogo(bloque, cp, catalogo)
 
    # Si la etiqueta no se detectó, el CP se busca en todo el texto.
    if not cp:
        cp = buscar_cp(lineas)
 
    domicilio = ", ".join(bloque)
    return domicilio, cp, colonia
 
 
# ------------------------------------------------------------------- main
def interpretar(texto, catalogo):
    lineas = limpiar_lineas(texto)
    domicilio, cp, colonia = extraer_domicilio(lineas, catalogo)
    datos.update(
        curp=extraer_curp(texto),
        codigo_postal=cp,
        colonia=colonia,
        domicilio=domicilio,
    )
    return datos
 
 
def puntaje(datos):
    return (len(datos["nombre_completo"]) + len(datos["domicilio"])
            + (10 if datos["curp"] else 0)
            + (5 if datos["codigo_postal"] else 0))
 
 
def leer_ine(ruta=RUTA_IMAGEN):
    catalogo = cargar_colonias()
    mejor_datos, mejor_texto, mejor_puntaje = None, "", -1
 
    # Se prueban varias versiones de la imagen y modos de página;
    # se queda el resultado que recupere más información.
    for _, imagen in preparar_variantes(ruta):
        for psm in (6, 4):
            texto = obtener_texto(imagen, psm)
            datos = interpretar(texto, catalogo)
            p = puntaje(datos)
            if p > mejor_puntaje:
                mejor_datos, mejor_texto, mejor_puntaje = datos, texto, p
 
    return mejor_datos, mejor_texto
 
 
if __name__ == "__main__":
    try:
        datos, texto = leer_ine()
 
        print("Datos detectados de la ine")
        for campo, valor in datos.items():
            print(f"{campo}: {valor if valor else '(no detectado)'}")
 
        print("Texto reconocido")
        print(texto)
 
        print("\nRevisa los datos antes de utilizarlos o guardarlos.")
    except Exception as error:
        print("\nERROR:", error)
        sys.exit(1)