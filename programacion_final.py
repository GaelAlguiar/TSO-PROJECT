#-------------------------------------------------------------------
# Genera un cronograma diario de entregas con asignación
# pipa propia vs. rentada, PipaID formateado y litros por pipa.
# Incluye además fecha de pedido y fecha límite de entrega.
#
# Lee:
#   • programacion_<rango>.csv   — tu asignación de mochila
# Parámetros de negocio:
#   • CAP_PROPIA: litros/día propios
#   • CAP_PIPA:   litros por pipa rentada
# -------------------------------------------------------------------

import math
import re
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime

# --- Parámetros de negocio ---
CAP_PROPIA = 1_920_000    # litros propios/día
CAP_PIPA   =    64_000    # litros por pipa rentada

# --- Localizar archivo de programación ---
CSV_DIR    = Path("csv")
prog_files = sorted(CSV_DIR.glob("programacion_*.csv"))
if not prog_files:
    sys.exit("No se encontró ningún archivo programacion_<rango>.csv en la carpeta csv/")
prog_file = prog_files[-1]
print(f"Generando detalle desde: {prog_file.name}")

# --- Extraer rango para el nombre de salida ---
m = re.search(r'_(\d{4}-\d{2}-\d{2})_A_(\d{4}-\d{2}-\d{2})', prog_file.stem)
if not m:
    sys.exit("El nombre del archivo de programación no contiene un rango válido.")
ini_dt, fin_dt = map(datetime.fromisoformat, m.groups())

# --- Cargar datos ---
df = pd.read_csv(prog_file, parse_dates=["FECHA_ASIGNADA", "FECHA", "FECHA_ENTREGA"])
# Filtrar solo dentro del rango de asignación
df = df[(df.FECHA_ASIGNADA >= ini_dt) & (df.FECHA_ASIGNADA <= fin_dt)]

# --- Preparar estructuras ---
pipas_por_dia = {}
rows = []

for fecha, grupo in df.groupby("FECHA_ASIGNADA"):
    dia = fecha.date()
    prop_usado = 0
    total_dia  = grupo["LITROS"].sum()
    extra      = max(0, total_dia - CAP_PROPIA)
    rented_needed = math.ceil(extra / CAP_PIPA)
    pipas_por_dia[dia] = rented_needed

    # Orden greedy por prioridad y litros
    ent = grupo.sort_values(["PRIORIDAD","LITROS"], ascending=[True,True])
    rent_loaded = 0  # acumula litros en rentada

    for _, p in ent.iterrows():
        litros = p["LITROS"]
        # Asignar a propia o rentada?
        if prop_usado + litros <= CAP_PROPIA:
            tipo = "PROPIA"
            pid  = (prop_usado // (CAP_PROPIA // 30)) + 1
            prop_usado += litros
        else:
            tipo = "RENTADA"
            pid_index = rent_loaded // CAP_PIPA
            pid       = 31 + pid_index
            rent_loaded += litros

        pid = int(pid)
        pipa_id = f"PIP{pid:02d}"
        litros_pipa = litros

        rows.append({
            "FechaAsignada":   dia,
            "PedidoID":        p["ID"],
            "Cliente":         p["CLIENTE"],
            "Prioridad":       p["PRIORIDAD"],
            "Valor":           p["VALOR"],
            "TipoPipa":        tipo,
            "PipaID":          pipa_id,
            "Litros_Pipa":     litros_pipa,
            "Litros_Rentados": p["LITROS_RENTADOS"],
            "Ganancia_Ajust":  p.get("GANANCIA_AJUST", p.get("UTILIDAD", 0))
        })

# --- Guardar detalle ---
det_df   = pd.DataFrame(rows)
out_file = CSV_DIR / f"programacion_detallada_{ini_dt:%Y-%m-%d}_A_{fin_dt:%Y-%m-%d}.csv"
det_df.to_csv(out_file, index=False)
print(f"Cronograma detallado guardado en: {out_file}")

# --- Resumen pipas rentadas por día ---
print("\nPipas rentadas por día:")
for dia, n in sorted(pipas_por_dia.items()):
    print(f"{dia}: {n} pipas")
