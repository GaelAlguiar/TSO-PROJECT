# ------------------------------------------------------------------
# Compara utilidad previa y posterior al algoritmo-mochila:
#  - Carga utilidad_previa_*.csv y utilidad_posterior_*.csv
#  - Renombra las columnas de utilidad por litro a nombres estándar
#  - Merge por Año-Mes
#  - Calcula Δ Utilidad, Δ Utilidad/Litro y % cambio
#  - Exporta utilidad_final_*.csv
# ------------------------------------------------------------------

import re
from pathlib import Path

import pandas as pd

CSV_DIR = Path("csv")

# 1) localizar los archivos de previa y posterior
prev_file = next(CSV_DIR.glob("utilidad_previa_*_A_*.csv"))
post_file = next(CSV_DIR.glob("utilidad_posterior_*_A_*.csv"))
print("Previo   :", prev_file.name)
print("Posterior:", post_file.name)

# 2) leerlos
prev = pd.read_csv(prev_file)
post = pd.read_csv(post_file)

# 3) detectar y renombrar las columnas de utilidad por litro
def find_util_litro_col(df):
    for c in df.columns:
        lc = c.lower()
        if "prom" in lc and "lit" in lc:
            return c
    raise KeyError("No se encontró columna de utilidad por litro")

u_prev = find_util_litro_col(prev)
u_post = find_util_litro_col(post)

prev = prev.rename(columns={
    u_prev:        "Util_x_L_prev",
    "Total_Litros": "Litros_prev",
    "Total_Utilidad":"Utilidad_prev"
})
post = post.rename(columns={
    u_post:         "Util_x_L_post",
    "Total_Litros":  "Litros_post",
    "Total_Utilidad":"Utilidad_post"
})

# 4) hacer merge
comp = pd.merge(
    prev[["Año-Mes", "Litros_prev", "Utilidad_prev", "Util_x_L_prev"]],
    post[["Año-Mes", "Litros_post", "Utilidad_post", "Util_x_L_post"]],
    on="Año-Mes",
    how="outer",
    validate="one_to_one"
)

# 5) calcular métricas de comparación
comp["Δ Utilidad"]      = comp["Utilidad_post"] - comp["Utilidad_prev"]
comp["Δ Utilidad/L"]    = comp["Util_x_L_post"] - comp["Util_x_L_prev"]
comp["% Δ Utilidad"]    = (comp["Δ Utilidad"] / comp["Utilidad_prev"] * 100).fillna(0)

# 6) totalizar al final
tot = pd.DataFrame({
    "Año-Mes":       ["TOTAL"],
    "Litros_prev":   [comp["Litros_prev"].sum()],
    "Litros_post":   [comp["Litros_post"].sum()],
    "Utilidad_prev": [comp["Utilidad_prev"].sum()],
    "Utilidad_post": [comp["Utilidad_post"].sum()],
    "Util_x_L_prev": [ (comp["Utilidad_prev"].sum() / comp["Litros_prev"].sum())
                       if comp["Litros_prev"].sum() else 0 ],
    "Util_x_L_post": [ (comp["Utilidad_post"].sum() / comp["Litros_post"].sum())
                       if comp["Litros_post"].sum() else 0 ]
})
tot["Δ Utilidad"]   = tot["Utilidad_post"] - tot["Utilidad_prev"]
tot["Δ Utilidad/L"] = tot["Util_x_L_post"] - tot["Util_x_L_prev"]
tot["% Δ Utilidad"] = (tot["Δ Utilidad"] / tot["Utilidad_prev"] * 100).fillna(0)

# 7) concatenar y exportar
final = pd.concat([comp, tot], ignore_index=True)
suf = re.search(r'_(\d{4}-\d{2}-\d{2}_A_\d{4}-\d{2}-\d{2})', prev_file.stem).group(1)
out = CSV_DIR / f"utilidad_final_{suf}.csv"
final.to_csv(out, index=False, float_format="%.6f")

print("✔ utilidad FINAL guardada en", out)
