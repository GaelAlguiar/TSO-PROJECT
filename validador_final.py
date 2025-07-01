# -------------------------------------------------------------------
# Valida que tu asignación nunca exceda la capacidad propia más
# el bloque de pipas rentadas, y comprueba la coherencia de
# Litros_Rentados vs. pipas calculadas.
# -------------------------------------------------------------------

import sys
import math
import pandas as pd
from pathlib import Path

# ---------------------- Parámetros de negocio ----------------------
CAP_PROPIA = 1_920_000   # litros propios/día
CAP_PIPA   =   64_000    # capacidad pipa rentada

# ---------------------- Localizar archivo --------------------------
CSV_DIR    = Path("csv")
prog_files = sorted(CSV_DIR.glob("programacion_*.csv"))
if not prog_files:
    sys.exit("No se encontró ningún programacion_<rango>.csv en csv/")
prog_file  = prog_files[-1]   # toma el más reciente
print(f"Validando capacidad usando: {prog_file.name}\n")

# ---------------------- Cargar datos --------------------------------
df = pd.read_csv(prog_file, parse_dates=["FECHA_ASIGNADA"])
if df["FECHA_ASIGNADA"].isna().all():
    sys.exit("Todas las FECHA_ASIGNADA están vacías; revisa tu algoritmo.")

# ---------------------- Agrupar por día ------------------------------
res = []
for fecha, grupo in df.groupby("FECHA_ASIGNADA"):
    total_litros     = grupo["LITROS"].sum()
    litros_rentados  = grupo["LITROS_RENTADOS"].sum()

    # cuántas pipas es necesario alquilar
    exceso = max(0, total_litros - CAP_PROPIA)
    pipas_necesarias = math.ceil(exceso / CAP_PIPA)

    # capacidad total provista por pipas rentadas
    capacidad_rentada = pipas_necesarias * CAP_PIPA

    # validación: que la cobertura en litros alcance los 'litros_rentados'
    renta_valida = litros_rentados <= capacidad_rentada

    res.append({
        "Fecha":                   fecha.date(),
        "Total_Litros_Diarios":    total_litros,
        "Litros_Asignados_Renta":  litros_rentados,
        "Pipas_Necesarias":        pipas_necesarias,
        "Capacidad_Rentada_L":     capacidad_rentada,
        "Validación_Renta_OK":     renta_valida
    })

df_res = pd.DataFrame(res).sort_values("Fecha")

# Mostrar en pantalla
print(df_res.to_string(index=False))

# ---------------------- Guardar resultados --------------------------
out_file = CSV_DIR / f"validador_diario_{prog_file.stem}.csv"
df_res.to_csv(out_file, index=False)
print(f"\nResultados de validación guardados en {out_file}")
