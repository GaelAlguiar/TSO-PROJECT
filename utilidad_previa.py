#!/usr/bin/env python3
# utilidad_previa.py
# ------------------------------------------------------------------
# Calcula los KPIs mensuales *previos* al algoritmo-mochila.
#
# 1. Detecta el mismo rango de fechas que prioridad_clientes_*.csv
# 2. Suma litros, utilidad, monto y costo en Pedidos.csv
# 3. ESTIMA los litros que habrías tenido que rentar:
#      · Capacidad propia = 1 920 000 L por día
#      · Litros rentados  = excedente / 64 000 L (pipa)  → redondeo arriba
# 4. Aplica una penalización económica del 5 % sobre la utilidad de
#    esos litros rentados (aproximación del costo de renta).
# 5. Exporta csv/utilidad_previa_<rango>.csv
# ------------------------------------------------------------------

import math
import re
import pandas as pd
from pathlib import Path
from datetime import datetime

# ------------ parámetros de negocio --------------------------------
CAP_PROPIA_DIA = 1_920_000          # litros propios/día
LITROS_PIPA    = 64_000             # capacidad pipa rentada
COSTO_RENTA    = 0.05               # penalización 5 %

# ------------ localizar archivos -----------------------------------
CSV_DIR   = Path("csv")
PEDIDOS   = CSV_DIR / "Pedidos.csv"
prior_csv = next(CSV_DIR.glob("prioridad_clientes*_A_*.csv"))

m = re.search(r'_(\d{4}-\d{2}-\d{2})_A_(\d{4}-\d{2}-\d{2})', prior_csv.stem, re.I)
ini_dt, fin_dt = map(datetime.fromisoformat, m.groups())

print("Archivo prioridades :", prior_csv.name)
print("Rango               :", ini_dt.date(), "→", fin_dt.date())

# ------------ cargar Pedidos.csv -----------------------------------
df = pd.read_csv(PEDIDOS, low_memory=False)
df['FECHA FACTURA VENTA'] = pd.to_datetime(
    df['FECHA FACTURA VENTA'],
    format='%d/%m/%Y',
    errors='coerce'
)

# filtrar al rango
df = df[
    (df['FECHA FACTURA VENTA'] >= ini_dt) &
    (df['FECHA FACTURA VENTA'] <= fin_dt)
]

# numéricos seguros
clean = lambda s: pd.to_numeric(
    s.astype(str).replace(r'[^0-9.\-]', '', regex=True),
    errors='coerce'
).fillna(0.0)

df['Litros']   = clean(df['LITROS REALES'])
df['Utilidad'] = clean(df.get('UTILIDAD', 0))
df['Monto']    = clean(df.get('MONTO',    0))
df['Costo']    = clean(df.get('COSTO',    0))

# ------------ litros rentados ESTIMADOS por mes --------------------
df['Año-Mes'] = df['FECHA FACTURA VENTA'].dt.to_period('M')

# Exceso sobre capacidad propia *diaria* (se asume 1 día simplificado)
exceso_mes = (
    df.groupby('Año-Mes')['Litros'].sum()
    - CAP_PROPIA_DIA
).clip(lower=0)

# Número de pipas rentadas al mes (ceil)
pipas_mes = (exceso_mes / LITROS_PIPA).apply(math.ceil)

# inicializo Litros_Rentados como float para no romper dtype
df['Litros_Rentados'] = 0.0

for per, n_pipas in pipas_mes.items():
    if n_pipas == 0:
        continue
    mask = df['Año-Mes'] == per
    litros_mes   = df.loc[mask, 'Litros'].sum()
    litros_renta = n_pipas * LITROS_PIPA
    # distribuyo proporcionalmente esos litros rentados
    df.loc[mask, 'Litros_Rentados'] = (
        df.loc[mask, 'Litros'] / litros_mes * litros_renta
    )

# penalización 5 % sobre la utilidad de los litros rentados
#    ganancia por litro = Utilidad / Litros
#    costo renta = Litros_Rentados * ganancia_x_litro * COSTO_RENTA
df['Ganancia_por_L'] = (df['Utilidad'] / df['Litros']).fillna(0.0)
df['Costo_Renta']    = df['Litros_Rentados'] * df['Ganancia_por_L'] * COSTO_RENTA
df['Utilidad_adj']   = df['Utilidad'] - df['Costo_Renta']

# ------------ agregación mensual -----------------------------------
agg = (
    df.groupby('Año-Mes')
      .agg(
        Total_Litros    = ('Litros',        'sum'),
        Litros_Rentados = ('Litros_Rentados','sum'),
        Total_Utilidad  = ('Utilidad_adj',  'sum')
      )
      .reset_index()
)
agg['Util_prom_litro'] = agg['Total_Utilidad'] / agg['Total_Litros']

# ------------ guardar ----------------------------------------------
out = CSV_DIR / f'utilidad_previa_{ini_dt:%Y-%m-%d}_A_{fin_dt:%Y-%m-%d}.csv'
agg.to_csv(out, index=False, float_format="%.6f")
print("✔ utilidad PREVIA guardada en", out)
