#!/usr/bin/env python3
# make_pedidos_knapsack.py
# -------------------------------------------------------------
# 1. Lee prioridad_clientes_<rango>.csv  (histórica + cancelaciones)
# 2. Lee Pedidos.csv
# 3. Calcula prioridad trimestral previa (>= 2.5 M L → 1)
# 4. Combina reglas → PRIORIDAD final 1 / 2 / 3
# 5. Devuelve CSV mínimo con VALOR 3 / 2 / 1
# -------------------------------------------------------------

import pandas as pd, re
from pathlib import Path
from datetime import datetime

CSV_DIR      = Path('csv')
PEDIDOS_CSV  = CSV_DIR / 'Pedidos.csv'

# ---------- localizar archivo de prioridades -----------------
prior_csv = next(CSV_DIR.glob('prioridad_clientes*_A_*.csv'))

# ---------- rango de fechas ----------------------------------
m = re.search(r'_(\d{4}-\d{2}-\d{2})_A_(\d{4}-\d{2}-\d{2})', prior_csv.stem, re.I)
desde_dt, hasta_dt = map(datetime.fromisoformat, m.groups())

# ---------- mapa de prioridades históricas (1/2/3) ----------
hist_prio = pd.read_csv(prior_csv).set_index('CLIENTE')['Prioridad']

# ---------- cargar Pedidos -----------------------------------
df = pd.read_csv(PEDIDOS_CSV, low_memory=False)
df['FECHA DE PEDIDO'] = pd.to_datetime(df['FECHA DE PEDIDO'],
                                       format='%d/%m/%Y', errors='coerce')

# filtrar rango global
df = df[(df['FECHA DE PEDIDO'] >= desde_dt) & (df['FECHA DE PEDIDO'] <= hasta_dt)]

# ---------- prioridad trimestral previa (> 2.5 M) -------------
if 'FECHA FACTURA VENTA' in df.columns:
    df['FECHA FACTURA VENTA'] = pd.to_datetime(df['FECHA FACTURA VENTA'],
                                               format='%d/%m/%Y', errors='coerce')
    df['ANIO'] = df['FECHA FACTURA VENTA'].dt.year
    df['TRIM'] = df['FECHA FACTURA VENTA'].dt.month.sub(1).floordiv(3).add(1)
    df['PERIODO'] = df['ANIO'].astype(str) + '-' + df['TRIM'].astype(str)

    litros_trim = (df.groupby(['CLIENTE', 'PERIODO'])['LITROS REALES']
                     .sum()
                     .reset_index())

    # convertir a numérico antes de construir el diccionario
    litros_trim['LITROS REALES'] = pd.to_numeric(litros_trim['LITROS REALES'],
                                                 errors='coerce').fillna(0)

    litros_trim['PERIODO_VAL'] = litros_trim['PERIODO'].apply(
        lambda p: int(p.split('-')[0]) * 10 + int(p.split('-')[1]))

    litros_dict = {
        (r['CLIENTE'], r['PERIODO_VAL']): r['LITROS REALES']
        for _, r in litros_trim.iterrows()
    }

    # función prioridad trimestral
    def prio_trim(cliente, periodo_val):
        prev = litros_dict.get((cliente, periodo_val - 1), 0)
        return 1 if prev > 2_500_000 else 2

    df['PERIODO_VAL'] = (df['ANIO'].astype(int) * 10 + df['TRIM'].astype(int))
    df['PRIO_TRIM'] = df.apply(
        lambda r: prio_trim(r['CLIENTE'], r['PERIODO_VAL']),
        axis=1)
else:
    df['PRIO_TRIM'] = 2

# ---------- combinar reglas -----------------------------------
def prioridad_final(cliente, prio_trim):
    hist = hist_prio.get(cliente, 2)
    if hist == 1 or prio_trim == 1:
        return 1
    if hist == 3:
        return 3
    return 2

df['PRIORIDAD'] = df.apply(
    lambda r: prioridad_final(r['CLIENTE'], r['PRIO_TRIM']),
    axis=1)

# ---------- limpiar litros y utilidad -------------------------------
df['LITROS'] = pd.to_numeric(
    df['LITROS REALES'].astype(str).replace(r'[^0-9.\-]', '', regex=True),
    errors='coerce').fillna(0)

df['UTILIDAD'] = pd.to_numeric(
    df.get('UTILIDAD', 0).astype(str).replace(r'[^0-9.\-]', '', regex=True),
    errors='coerce').fillna(0)

df['VALOR']  = df['PRIORIDAD'].map({1:3, 2:2, 3:1})
df['ID']     = df.get('IDPEDIDO', df.get('PEDIDO', range(len(df))))
df['FECHA']  = df['FECHA DE PEDIDO']

# ---------- exportar -------------------------------------------------
out_cols = ['ID', 'CLIENTE', 'FECHA', 'LITROS',
               'PRIORIDAD', 'VALOR', 'UTILIDAD']   # ← añadida

clean_df = df[out_cols]
sufijo   = f"{desde_dt:%Y-%m-%d}_A_{hasta_dt:%Y-%m-%d}"
outfile  = CSV_DIR / f'pedidos_limpios_{sufijo}.csv'
clean_df.to_csv(outfile, index=False)

print(f"✔ pedidos_limpios_{sufijo}.csv  ({len(clean_df)} filas)")
