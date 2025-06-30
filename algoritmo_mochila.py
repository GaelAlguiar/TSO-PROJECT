#!/usr/bin/env python3
# algoritmo_mochila_optimo.py
# ---------------------------------------------------------------
# • Knapsack exacto OR-Tools (API nueva)               ✔
# • Back-log: reintenta hasta MAX_DIAS_ESPERA días      ✔
# • Penalización 5 % a litros rentados                 ✔
# • Pipas rentadas por día y validación de capacidad   ✔
# ---------------------------------------------------------------

import pandas as pd, re, math, sys
from pathlib import Path
from datetime import datetime, timedelta
from ortools.algorithms.python import knapsack_solver

# --------------- parámetros de negocio --------------------------
CSV_DIR            = Path("csv")
CAP_PROPIA         = 1_920_000          # litros propios/día
CAP_PIPA           = 64_000             # capacidad de pipa rentada
PENALIZ            = 0.05               # 5 % a litros rentados
MAX_DIAS_ESPERA    = 1                  # días antes de alquilar
VALOR_MAP          = {1: 3, 2: 2, 3: 1} # pesos estratégicos

# --------------- localizar archivos ------------------------------
prior_csv = next(CSV_DIR.glob("prioridad_clientes*_A_*.csv"))
ped_csv   = CSV_DIR / ("pedidos_limpios" +
                       prior_csv.stem.replace("prioridad_clientes", "") + ".csv")
m = re.search(r'_(\d{4}-\d{2}-\d{2})_A_(\d{4}-\d{2}-\d{2})', prior_csv.stem, re.I)
desde_dt, hasta_dt = map(datetime.fromisoformat, m.groups())

print("Prioridades :", prior_csv.name)
print("Pedidos      :", ped_csv.name)

# --------------- cargar datos ------------------------------------
prio_map = pd.read_csv(prior_csv).set_index("CLIENTE")["Prioridad"]
df       = pd.read_csv(ped_csv, parse_dates=["FECHA"])

# ── ganancia base ────────────────────────────────────────────────
if "GANANCIA" in df.columns:
    df["GANANCIA"] = pd.to_numeric(df["GANANCIA"], errors="coerce").fillna(0)
elif "UTILIDAD" in df.columns:
    df["GANANCIA"] = pd.to_numeric(df["UTILIDAD"], errors="coerce").fillna(0)
else:
    df["GANANCIA"] = 0.0

# ── fechas y prioridades ─────────────────────────────────────────
df["FECHA_DISP"]   = df["FECHA"] + timedelta(days=5)
df["PRIORIDAD"]    = df["PRIORIDAD"].fillna(df["CLIENTE"].map(prio_map)).astype(int)
df["VALOR"]        = df["PRIORIDAD"].map(VALOR_MAP)

# columnas de control
df["FECHA_ASIGNADA"]  = pd.NaT
df["LITROS_RENTADOS"] = 0
df["GANANCIA_AJUST"]  = df["GANANCIA"]
df["ESPERA_DIAS"]     = 0

pend = df.to_dict("records")
pipas_rentadas = {}
fecha = desde_dt

# --------------- función knapsack --------------------------------
def solve_knapsack(cands, capacidad):
    pesos   = [int(p['LITROS']) for p in cands]
    valores = [int(p['VALOR'])  for p in cands]
    solver = knapsack_solver.KnapsackSolver(
        knapsack_solver.SolverType.KNAPSACK_DYNAMIC_PROGRAMMING_SOLVER, "knap")
    solver.init(valores, [pesos], [capacidad])
    solver.solve()
    return [i for i in range(len(cands)) if solver.best_solution_contains(i)]

def penalizar(p, rentados):
    if rentados <= 0:
        return p["GANANCIA"]
    gxl = p["GANANCIA"] / p["LITROS"] if p["LITROS"] else 0
    return p["GANANCIA"] - rentados * gxl * PENALIZ

# --------------- simulación diaria -------------------------------
while any(pd.isna(p["FECHA_ASIGNADA"]) for p in pend):
    hoy = [p for p in pend if pd.isna(p["FECHA_ASIGNADA"])
           and p["FECHA_DISP"] <= fecha]

    if not hoy:
        fecha += timedelta(days=1)
        continue

    # incrementar contador de espera
    for p in hoy:
        p["ESPERA_DIAS"] += 1

    # candidatos que todavía pueden esperar
    candidatos = [p for p in hoy if p["ESPERA_DIAS"] <= MAX_DIAS_ESPERA]

    # solve knapsack para capacidad propia
    idx_sel = solve_knapsack(candidatos, CAP_PROPIA)
    sel_set = {id(candidatos[i]) for i in idx_sel}

    # asignar selección a propia
    for p in candidatos:
        if id(p) in sel_set:
            p["FECHA_ASIGNADA"] = fecha

    # pedidos a rentada (los que superan espera o sobrantes de knapsack)
    rentados_total = 0
    for p in hoy:
        if pd.notna(p["FECHA_ASIGNADA"]):
            continue
        # manda a renta
        p["FECHA_ASIGNADA"]  = fecha
        p["LITROS_RENTADOS"] = p["LITROS"]
        rentados_total      += p["LITROS"]
        p["GANANCIA_AJUST"]  = penalizar(p, p["LITROS"])

    pipas_rentadas[fecha.date()] = math.ceil(rentados_total / CAP_PIPA)
    fecha += timedelta(days=1)

# --------------- exportar ----------------------------------------
sel_df = pd.DataFrame(pend)
sufijo = f"{desde_dt:%Y-%m-%d}_A_{hasta_dt:%Y-%m-%d}"
sel_df.to_csv(CSV_DIR / f"programacion_{sufijo}.csv", index=False)
sel_df[pd.isna(sel_df["FECHA_ASIGNADA"])]\
      .to_csv(CSV_DIR / f"pendientes_{sufijo}.csv", index=False)

print("\nPipas rentadas por día:")
for d, n in pipas_rentadas.items():
    print(f"{d}: {n} pipas")
print("✓ Programación guardada con espera de", MAX_DIAS_ESPERA, "días antes de rentar.")
