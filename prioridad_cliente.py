# -------------------------------------------------------------------
# Generador de Prioridades de Clientes
#
# Este script prepara el ranking de clientes para el algoritmo de mochila:
#  1. Carga Pedidos.csv y PedidosCancelados.csv en el rango indicado.
#  2. Normaliza nombres y agrupa por cliente:
#       • Suma litros facturados.
#       • Cuenta cancelaciones.
#  3. Aplica la regla de prioridad:
#       – Prioridad 1: ≥ 5 000 000 L históricos.
#       – Prioridad 3: (no 1) > 5 cancelaciones en el periodo.
#       – Prioridad 2: el resto.
#  4. Exporta prioridad_clientes_<rango>.csv con columnas:
#       CLIENTE, LitrosFacturados, Cancelaciones, Prioridad
#
# El CSV resultante alimenta el modelo de optimización tipo mochila,
# garantizando que los pedidos se asignen primero a los clientes con
# mayor valor estratégico y menor riesgo de cancelación.
# -------------------------------------------------------------------


import pandas as pd
import unicodedata, re
from pathlib import Path
from datetime import datetime

print("\n=== Generador de Prioridades de Clientes ===\n")
FMT = "%d/%m/%Y"

def ask_date(prompt: str):
    raw = input(prompt).strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, FMT)
    except ValueError:
        raise SystemExit("Formato incorrecto. Use dd/mm/yyyy, p. ej. 03/01/2024")

desde_dt = ask_date("Fecha DESDE (dd/mm/yyyy) o Enter para histórico: ")
hasta_dt = ask_date("Fecha HASTA (dd/mm/yyyy) o Enter para hoy: ")

# ------------------------------ Archivos ------------------------------------
PEDIDOS_FILE    = Path('csv/Pedidos.csv')
CANCELADOS_FILE = Path('csv/PedidosCancelados.csv')

print("\n→ Cargando CSV…")
pedidos_df    = pd.read_csv(PEDIDOS_FILE,    low_memory=False)
cancelados_df = pd.read_csv(CANCELADOS_FILE, low_memory=False)

# ------------------------------ Helpers -------------------------------------
normalize = lambda t: unicodedata.normalize('NFKD', str(t)).encode('ascii', 'ignore').decode().upper()
clean_key = lambda t: re.sub(r'[^A-Z0-9]', '', normalize(t))
num_clean  = lambda x: float(re.sub(r'[^0-9.\-]', '', str(x)) or 0)

# ------------------------------ Fechas --------------------------------------
FECHA_PEDIDOS_COLS = ['FECHA FACTURA VENTA', 'FECHA DE PEDIDO', 'FECHA DE ENTREGA']
fecha_ped_col = next((c for c in FECHA_PEDIDOS_COLS if c in pedidos_df.columns), None)
if not fecha_ped_col:
    raise ValueError('No se encontró columna de fecha en Pedidos.csv')

pedidos_df[fecha_ped_col] = pd.to_datetime(pedidos_df[fecha_ped_col], errors='coerce')
cancelados_df['fecha_fac'] = pd.to_datetime(cancelados_df['fecha_fac'], errors='coerce')

if desde_dt:
    pedidos_df    = pedidos_df[pedidos_df[fecha_ped_col] >= desde_dt]
    cancelados_df = cancelados_df[cancelados_df['fecha_fac'] >= desde_dt]
if hasta_dt:
    pedidos_df    = pedidos_df[pedidos_df[fecha_ped_col] <= hasta_dt]
    cancelados_df = cancelados_df[cancelados_df['fecha_fac'] <= hasta_dt]

# ------------------------------ Claves --------------------------------------
pedidos_df['CLIENTE_KEY']    = pedidos_df['CLIENTE'].apply(clean_key)
cancelados_df['CLIENTE_KEY'] = cancelados_df['cliente'].apply(clean_key)

# ------------------------------ Litros facturados ---------------------------
col_litros = next((c for c in pedidos_df.columns if all(k in clean_key(c) for k in ['LITROS', 'FACT'])), None) or 'LITROS REALES'
print(f"→ Columna de litros utilizada: {col_litros}")

pedidos_df[col_litros] = pedidos_df[col_litros].apply(num_clean)

litros_por_cliente = (
    pedidos_df.groupby('CLIENTE_KEY', as_index=False)[col_litros]
    .sum()
    .rename(columns={col_litros: 'LitrosFacturados'})
)

cancelaciones_por_cliente = (
    cancelados_df.groupby('CLIENTE_KEY').size().reset_index(name='Cancelaciones')
)

# ------------------------------ Unión ---------------------------------------
all_keys = pd.DataFrame({'CLIENTE_KEY': pd.unique(
    pd.concat([pedidos_df['CLIENTE_KEY'], cancelados_df['CLIENTE_KEY']])
)})

clientes_df = (
    all_keys
    .merge(litros_por_cliente,       on='CLIENTE_KEY', how='left')
    .merge(cancelaciones_por_cliente, on='CLIENTE_KEY', how='left')
)

# Sustituir NaN: numéricos → 0 ; texto → ""
clientes_df['LitrosFacturados'] = clientes_df['LitrosFacturados'].fillna(0).astype(float)
clientes_df['Cancelaciones']    = clientes_df['Cancelaciones'].fillna(0).astype(int)

# ------------------------------ Prioridad -----------------------------------
clientes_df['Prioridad'] = 2
clientes_df.loc[clientes_df['LitrosFacturados'] >= 5_000_000, 'Prioridad'] = 1
mask_p3 = (clientes_df['Prioridad'] != 1) & (clientes_df['Cancelaciones'] > 5)
clientes_df.loc[mask_p3, 'Prioridad'] = 3

# ------------------------------ Nombre original -----------------------------
map_orig = (
    pedidos_df[['CLIENTE_KEY', 'CLIENTE']].drop_duplicates('CLIENTE_KEY')
    .set_index('CLIENTE_KEY')['CLIENTE']
)
clientes_df['CLIENTE'] = clientes_df['CLIENTE_KEY'].map(map_orig).fillna(clientes_df['CLIENTE_KEY'])

# ------------------------------ Exportar ------------------------------------
# Construir nombre de archivo según rango
if desde_dt and hasta_dt:
    file_name = f"prioridad_clientes_{desde_dt.strftime('%Y-%m-%d')}_A_{hasta_dt.strftime('%Y-%m-%d')}.csv"
elif desde_dt and not hasta_dt:
    file_name = f"prioridad_clientes_desde_{desde_dt.strftime('%Y-%m-%d')}.csv"
elif hasta_dt and not desde_dt:
    file_name = f"prioridad_clientes_hasta_{hasta_dt.strftime('%Y-%m-%d')}.csv"
else:
    file_name = "prioridad_clientes.csv"

OUTPUT_FILE = Path(file_name)

out_cols = ['CLIENTE', 'LitrosFacturados', 'Cancelaciones', 'Prioridad']
clientes_df[out_cols].to_csv(OUTPUT_FILE, index=False)

print(f"\n✔ CSV generado sin NaN: {OUTPUT_FILE}  ({len(clientes_df)} clientes)")
