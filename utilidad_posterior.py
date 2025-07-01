# -------------------------------------------------------------------
# Calcula la utilidad posterior mensual tras aplicar el algoritmo
# de mochila y la penalización por litros rentados.
# 'Utilidad_adj' refleja la utilidad neta después de descontar
# el costo de renta (5 %) aplicado solo a los litros asignados
# a pipas rentadas, permitiendo comparar la rentabilidad real
# antes y después de la optimización.
# -------------------------------------------------------------------

import pandas as pd, re
from pathlib import Path
from datetime import datetime

CSV_DIR = Path("csv")
prog_csv = next(CSV_DIR.glob("programacion_*_A_*.csv"))

# rango usado en prioridades
m = re.search(r'_(\d{4}-\d{2}-\d{2})_A_(\d{4}-\d{2}-\d{2})', prog_csv.stem, re.I)
ini, fin = map(datetime.fromisoformat, m.groups())

df = pd.read_csv(prog_csv, parse_dates=['FECHA_ASIGNADA'])
df = df[(df['FECHA_ASIGNADA'] >= ini) & (df['FECHA_ASIGNADA'] <= fin)]

num = lambda s: pd.to_numeric(s, errors='coerce').fillna(0)
df['Litros']        = num(df['LITROS'])
df['Utilidad_adj']  = num(df['GANANCIA_AJUST'])
df['Litros_Rentados'] = num(df['LITROS_RENTADOS'])

df['Año-Mes'] = df['FECHA_ASIGNADA'].dt.to_period('M')
agg = (df.groupby('Año-Mes')
         .agg(Total_Litros=('Litros','sum'),
              Total_Utilidad=('Utilidad_adj','sum'),
              Litros_Rentados=('Litros_Rentados','sum'))
         .reset_index())
agg['Util_prom_litro'] = agg['Total_Utilidad']/agg['Total_Litros']

out = CSV_DIR / f'utilidad_posterior_{ini:%Y-%m-%d}_A_{fin:%Y-%m-%d}.csv'
agg.to_csv(out, index=False)
print("✔ utilidad POSTERIOR guardada en", out)
