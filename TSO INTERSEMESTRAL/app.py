from pathlib import Path
from datetime import datetime, timedelta
from flask import Flask, json, jsonify, render_template, request, send_file, url_for
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd, re, io, os
from subcarpeta import algoritmo_mochila

app = Flask(__name__)

DATA_FOLDER = os.path.join(os.path.dirname(__file__), 'data')
BASE_DIR = os.path.dirname(__file__)
DETALLE_DIR = os.path.join(BASE_DIR, 'csv')

@app.route('/')
def index():
    return render_template('index.html')

def generar_grafica(nombre_archivo, titulo, columna_x, columna_y):
    ruta_archivo = os.path.join(DATA_FOLDER, nombre_archivo)
    if not os.path.exists(ruta_archivo):
        return f"Archivo {nombre_archivo} no encontrado en /data", 404

    try:
        df = pd.read_csv(ruta_archivo)
        if 'fecha' in columna_x.lower():
            df[columna_x] = pd.to_datetime(df[columna_x], dayfirst=True, errors='coerce')
            df = df.dropna(subset=[columna_x])

        if columna_x not in df.columns or columna_y not in df.columns:
            return f"Las columnas '{columna_x}' o '{columna_y}' no existen en {nombre_archivo}.", 400

        x = df[columna_x]
        y = pd.to_numeric(df[columna_y], errors='coerce')
        mask = y.notna()
        x, y = x[mask], y[mask]

        if not pd.api.types.is_datetime64_any_dtype(x):
            x = x.astype(str)

    except Exception as e:
        return f"Error al procesar {nombre_archivo}: {e}", 500

    plt.figure(figsize=(10, 5))
    plt.plot(x, y, marker='o', linestyle='--')
    plt.title(titulo)
    plt.xlabel(columna_x.capitalize())
    plt.ylabel(columna_y.capitalize())
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.tight_layout()

    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plt.close()

    return send_file(img, mimetype='image/png')

@app.route('/ver_resultados', methods=['POST'])
def ver_resultados():
    fecha_str = request.form.get('fecha')
    if not fecha_str:
        return "⚠️ No se proporcionó fecha", 400

    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        archivo = f"detalle_mochila_{fecha}.csv"
        ruta = os.path.join(DETALLE_DIR, archivo)

        if not os.path.exists(ruta):
            algoritmo_mochila.ejecutar()
            archivos = sorted(Path(DETALLE_DIR).glob("programacion_*.csv"), reverse=True)
            if not archivos:
                return "❌ No hay ningún archivo de programación generado."

            df_total = pd.read_csv(archivos[0])
            df_total.columns = (df_total.columns
                        .str.replace(' ', '_')
                        .str.upper())

            if 'FECHA_ASIGNADA' not in df_total.columns:
                print(df_total.columns.tolist())  # Depuración correcta
                raise ValueError("Columna FECHA_ASIGNADA no encontrada")


            df_total["FECHA_ASIGNADA"] = pd.to_datetime(df_total["FECHA_ASIGNADA"], errors="coerce")
            df_dia = df_total[df_total["FECHA_ASIGNADA"].dt.date == fecha]
            if df_dia.empty:
                return f"❌ No se encontró programación para la fecha {fecha}.", 404

            cols = [c for c in ["ID", "CLIENTE", "FECHA", "PRIORIDAD", "LITROS", "GANANCIA", "GANANCIA_AJUST", "LITROS_RENTADOS"] if c in df_dia.columns]
            df_dia[cols].to_csv(ruta, index=False)

        df = pd.read_csv(ruta)
        return render_template('resultado.html', mensaje=f"Resultados para {fecha}", tabla=df.to_html(classes='table', index=False))

    except Exception as e:
        return f"❌ Error al procesar la fecha: {e}", 500
    
@app.route('/programacion_detallada')
def ver_programacion_detallada():
    """
    Muestra el CSV más reciente que empiece con
    'programacion_detallada_' usando el mismo template 'resultado.html'.
    """
    archivos = sorted(
        Path(DETALLE_DIR).glob("programacion_detallada_*.csv"),
        reverse=True
    )
    if not archivos:
        return "❌ No existe ningún archivo programacion_detallada_*.csv", 404

    ruta = archivos[0]              # el más nuevo
    try:
        df = pd.read_csv(ruta)
    except Exception as e:
        return f"❌ Error al leer {ruta.name}: {e}", 500

    mensaje = f"Programación Detallada: {ruta.name}"
    return render_template(
        "resultado.html",
        mensaje=mensaje,
        tabla=df.to_html(classes='table', index=False)
    )

@app.route('/api/utilidad_previa')
def api_utilidad_previa():
    ruta_archivo = os.path.join(DATA_FOLDER, 'Utilidad_previa.csv')
    if not os.path.exists(ruta_archivo):
        return jsonify({"error": "CSV no encontrado"}), 404

    df = pd.read_csv(ruta_archivo)
    df.columns = [c.strip() for c in df.columns]

    if 'Año-Mes' not in df.columns or 'Total_Utilidad' not in df.columns:
        return jsonify({"error": "Columnas requeridas no encontradas"}), 400

    return jsonify({
        "labels": df['Año-Mes'].astype(str).tolist(),
        "data"  : df['Total_Utilidad'].tolist()
    })

@app.route('/grafica/utilidad_previa')
def grafica_utilidad_previa():
    # Solo renderiza la plantilla (no pasa datos)
    return render_template('grafica_js.html', titulo='Utilidad Previa')

@app.route('/api/utilidad_posterior')
def api_utilidad_posterior():
    ruta_archivo = os.path.join(DATA_FOLDER, 'Utilidad_posterior.csv')
    if not os.path.exists(ruta_archivo):
        return jsonify({"error": "CSV no encontrado"}), 404

    df = pd.read_csv(ruta_archivo)
    df.columns = [c.strip() for c in df.columns]

    if 'Año-Mes' not in df.columns or 'Total_Utilidad' not in df.columns:
        return jsonify({"error": "Columnas requeridas no encontradas"}), 400

    return jsonify({
        "labels": df['Año-Mes'].astype(str).tolist(),
        "data"  : df['Total_Utilidad'].tolist()
    })

@app.route('/grafica/utilidad_posterior')
def grafica_utilidad_posterior_html():
    return render_template(
        'grafica_js.html',
        titulo='Utilidad Posterior',
        api_url=url_for('api_utilidad_posterior')
    )

@app.route('/api/utilidad_comparada')
def api_utilidad_comparada():
    fn_prev = os.path.join(DATA_FOLDER, 'Utilidad_previa.csv')
    fn_post = os.path.join(DATA_FOLDER, 'Utilidad_posterior.csv')

    if not (os.path.exists(fn_prev) and os.path.exists(fn_post)):
        return jsonify({"error": "Alguno de los CSV no existe"}), 404

    # Leer CSV → normalizar encabezados
    prev  = pd.read_csv(fn_prev)
    post  = pd.read_csv(fn_post)
    for df in (prev, post):
        df.columns = [c.strip() for c in df.columns]

    # Verificar columnas requeridas
    for df,n in ((prev,'previa'),(post,'posterior')):
        if not {'Año-Mes','Total_Utilidad'}.issubset(df.columns):
            return jsonify({"error": f"Columnas faltantes en {n}"}), 400

    # Combinar por 'Año-Mes'
    df = prev.merge(
        post, on='Año-Mes', how='outer',
        suffixes=('_PREV','_POST')
    ).sort_values('Año-Mes')

    return jsonify({
        "labels"    : df['Año-Mes'].astype(str).tolist(),
        "prev_data" : df['Total_Utilidad_PREV'].fillna(0).tolist(),
        "post_data" : df['Total_Utilidad_POST'].fillna(0).tolist()
    })

@app.route('/grafica/utilidad_comparada')
def grafica_utilidad_comparada():
    return render_template(
        'grafica_comparada_js.html',
        titulo='Utilidad Previa vs Posterior',
        api_url=url_for('api_utilidad_comparada')
    )

def tabla_json(pattern):
    """Devuelve JSON {columns, rows} del CSV más reciente que coincida."""
    archivos = sorted(Path(DETALLE_DIR).glob(pattern), reverse=True)
    if not archivos:
        return None

    # detectar si el separador es ; o ,
    with open(archivos[0], encoding="utf-8") as fh:
        sample = fh.read(2048)
        sep = ";" if sample.count(";") > sample.count(",") else ","

    df = pd.read_csv(archivos[0], sep=sep)
    # NaN/Nat -> null
    rows = json.loads(df.to_json(orient="records"))
    return jsonify({"columns": list(df.columns), "rows": rows})

@app.route("/api/pedidos_limpios")
def api_pedidos_limpios():
    data = tabla_json("[Pp]edidos_limpios_*.csv")
    return data if data else jsonify({"error": "CSV no encontrado"}), 404

@app.route("/api/pedidos_cancelados")
def api_pedidos_cancelados():
    data = tabla_json("[Pp]edidosCancelados.csv")   # admite guion bajo
    return data if data else jsonify({"error": "CSV no encontrado"}), 404


# Páginas Tabulator
@app.route("/tabla/pedidos_limpios")
def tabla_pedidos_limpios():
    return render_template("tabla_js.html",
                           titulo="Pedidos Limpios",
                           api_url=url_for("api_pedidos_limpios"))

@app.route("/tabla/pedidos_cancelados")
def tabla_pedidos_cancelados():
    return render_template("tabla_js.html",
                           titulo="Pedidos Cancelados",
                           api_url=url_for("api_pedidos_cancelados"))


@app.route('/ejecutar_mochila', methods=['POST'])
def ejecutar_mochila():
    mensaje = algoritmo_mochila.ejecutar()
    return render_template('resultado.html', mensaje=mensaje)

if __name__ == '__main__':
    app.run(debug=True)