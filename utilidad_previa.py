import pandas as pd, re
from pathlib import Path
from datetime import datetime

CSV_DIR      = Path('csv')
PEDIDOS_FILE = CSV_DIR / 'Pedidos.csv'

# localizar prioridad_clientes…
prior_files = sorted(CSV_DIR.glob('prioridad_clientes*.csv'))
if not prior_files:
    raise SystemExit("No se encontró prioridad_clientes*.csv")
prior_file = prior_files[0]

def parse_rango(stem):
    s = stem.lower()
    m = re.search(r'_(\d{4}-\d{2}-\d{2})_a_(\d{4}-\d{2}-\d{2})', s)
    if m: return datetime.fromisoformat(m.group(1)), datetime.fromisoformat(m.group(2))
    m = re.search(r'_desde_(\d{4}-\d{2}-\d{2})', s);  from_d = m and datetime.fromisoformat(m.group(1))
    m = re.search(r'_hasta_(\d{4}-\d{2}-\d{2})', s);  to_d   = m and datetime.fromisoformat(m.group(1))
    return from_d, to_d

desde_dt, hasta_dt = parse_rango(prior_file.stem)

# cargar Pedidos
df = pd.read_csv(PEDIDOS_FILE, low_memory=False)

fecha_col = 'FECHA FACTURA VENTA'
if fecha_col not in df.columns:
    raise SystemExit("FECHA FACTURA VENTA no está en Pedidos.csv")

# ✔ conversión robusta: dd/mm/yyyy exacto
df[fecha_col] = pd.to_datetime(df[fecha_col].str.strip(),
                               format="%d/%m/%Y",
                               errors="coerce")

# filtrar rango
if desde_dt: df = df[df[fecha_col] >= desde_dt]
if hasta_dt: df = df[df[fecha_col] <= hasta_dt]

# numéricas
num = lambda s: pd.to_numeric(s.astype(str).replace(r'[^0-9.\-]', '', regex=True),
                              errors='coerce').fillna(0.0)
df['Litros']   = num(df['LITROS REALES'])
df['Utilidad'] = num(df['UTILIDAD'])
df['Monto']    = num(df['MONTO'])  if 'MONTO'  in df.columns else 0
df['Costo']    = num(df['COSTO'])  if 'COSTO'  in df.columns else 0

# agrupación mensual
df['Año-Mes'] = df[fecha_col].dt.to_period('M')
agg = (df.groupby('Año-Mes')
         .agg(Total_Litros   = ('Litros', 'sum'),
              Total_Monto    = ('Monto', 'sum'),
              Total_Costo    = ('Costo', 'sum'),
              Total_Utilidad = ('Utilidad', 'sum'))
         .reset_index())

agg['Costo_prom_litro'] = agg['Total_Costo']    / agg['Total_Litros']
agg['Util_prom_litro']  = agg['Total_Utilidad'] / agg['Total_Litros']

sufijo = prior_file.stem.replace('prioridad_clientes', '').lstrip('_')
outfile = CSV_DIR / f'utilidad_previa_{sufijo}.csv'
agg.to_csv(outfile, index=False)
print(f'✔ CSV mensual guardado → {outfile}')
