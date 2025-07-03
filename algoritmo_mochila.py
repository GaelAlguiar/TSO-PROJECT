# ---------------------------------------------------------------
# • Knapsack exacto OR-Tools (API nueva)               ✔
# • biblioteca de código abierto desarrollada por Google que 
# • incluye algoritmos avanzados de optimización —desde programación lineal
# • y entera hasta rutas de vehículos y problemas de rango restringido como la “mochila” (knapsack)
# • Back-log: reintenta hasta MAX_DIAS_ESPERA días      ✔
# • Penalización 5 % a litros rentados                 ✔
# • Pipas rentadas por día y validación de capacidad   ✔
# • Respeta FECHA_ENTREGA como deadline                 ✚
# • Fragmenta pedidos > CAP_PROPIA en sub-pedidos       ✚
# ---------------------------------------------------------------

import pandas as pd, re, math, sys
from pathlib import Path
from datetime import datetime, timedelta
from ortools.algorithms.python import knapsack_solver

# --------------- parámetros de negocio --------------------------
CSV_DIR         = Path("csv")
CAP_PROPIA      = 1_920_000          # litros propios/día
CAP_PIPA        = 64_000             # capacidad de pipa rentada
PENALIZ         = 0.05               # 5 % a litros rentados
MAX_DIAS_ESPERA = 2                  # días antes de forzar renta
VALOR_MAP       = {1: 3, 2: 2, 3: 1} # pesos estratégicos

# --------------- localizar archivos ------------------------------
prior_csv = next(CSV_DIR.glob("prioridad_clientes*_A_*.csv"))
# pedidos_limpios ya incluye columna UTILIDAD
ped_csv   = CSV_DIR / f"pedidos_limpios{prior_csv.stem.replace('prioridad_clientes','')}.csv"

m = re.search(r'_(\d{4}-\d{2}-\d{2})_A_(\d{4}-\d{2}-\d{2})', prior_csv.stem, re.I)
if not m: sys.exit("El nombre de prioridad debe contener rango _YYYY-MM-DD_A_YYYY-MM-DD")
desde_dt, hasta_dt = map(datetime.fromisoformat, m.groups())

print("Prioridades :", prior_csv.name)
print("Pedidos     :", ped_csv.name)

# --------------- cargar y fragmentar ------------------------------
prio_map = pd.read_csv(prior_csv).set_index("CLIENTE")["Prioridad"]

raw = pd.read_csv(ped_csv, parse_dates=["FECHA"])
# si existe FECHA_ENTREGA la usamos como deadline
if "FECHA ENTREGA" in raw.columns:
    raw["FECHA_ENTREGA"] = pd.to_datetime(raw["FECHA ENTREGA"], dayfirst=True, errors="coerce")
else:
    raw["FECHA_ENTREGA"] = pd.Timestamp.max  # sin restricción

# Fragmentar pedidos > CAP_PROPIA
fragmentos = []
for _, r in raw.iterrows():
    litros = r["LITROS"]
    partes = math.ceil(litros / CAP_PROPIA)
    for i in range(partes):
        frag = r.copy()
        frag["LITROS"] = CAP_PROPIA if i < partes-1 else litros - CAP_PROPIA*(partes-1)
        frag["ID"]     = f"{r['ID']}-{i+1}"
        fragmentos.append(frag)
df = pd.DataFrame(fragmentos)

# --------------- inicializar columnas -----------------------------
df["GANANCIA"]        = pd.to_numeric(df["UTILIDAD"], errors="coerce").fillna(0)
df["FECHA_DISP"]      = df["FECHA"] + timedelta(days=5)
df["PRIORIDAD"]       = df["PRIORIDAD"].fillna(df["CLIENTE"].map(prio_map)).astype(int)
df["VALOR"]           = df["PRIORIDAD"].map(VALOR_MAP)
df["FECHA_ASIGNADA"]  = pd.NaT
df["LITROS_RENTADOS"] = 0
df["GANANCIA_AJUST"]  = df["GANANCIA"]
df["ESPERA_DIAS"]     = 0

pend = df.to_dict("records")
pipas_rentadas = {}
fecha = desde_dt

# --------------- knapsack helper -------------------------------
def solve_knapsack(cands, capacidad):
    pesos   = [int(p['LITROS']) for p in cands]
    valores = [int(p['VALOR'])  for p in cands]
    solver = knapsack_solver.KnapsackSolver(
        knapsack_solver.SolverType.KNAPSACK_DYNAMIC_PROGRAMMING_SOLVER, "knap")
    solver.init(valores, [pesos], [capacidad])
    solver.solve()
    return [i for i in range(len(cands)) if solver.best_solution_contains(i)]

def penalizar(p, rentados):
    if rentados <= 0: return p["GANANCIA"]
    gxl = p["GANANCIA"]/p["LITROS"] if p["LITROS"] else 0
    return p["GANANCIA"] - rentados * gxl * PENALIZ

# --------------- simulación diaria -------------------------------
while any(pd.isna(p["FECHA_ASIGNADA"]) for p in pend):
    hoy = [p for p in pend
           if pd.isna(p["FECHA_ASIGNADA"])
           and p["FECHA_DISP"] <= fecha
           and fecha <= p["FECHA_ENTREGA"] ]  # <— respeta deadline

    if not hoy:
        fecha += timedelta(days=1)
        continue

    # contar días de espera
    for p in hoy: p["ESPERA_DIAS"] += 1

    # candidatos que aún pueden esperar
    cand = [p for p in hoy if p["ESPERA_DIAS"] <= MAX_DIAS_ESPERA]

    # llenar propia
    idx_sel = solve_knapsack(cand, CAP_PROPIA)
    sel_set  = {id(cand[i]) for i in idx_sel}
    for p in cand:
        if id(p) in sel_set:
            p["FECHA_ASIGNADA"] = fecha

    # resto → rentada
    rent_total = 0
    for p in hoy:
        if pd.notna(p["FECHA_ASIGNADA"]): continue
        p["FECHA_ASIGNADA"]  = fecha
        p["LITROS_RENTADOS"] = p["LITROS"]
        rent_total          += p["LITROS"]
        p["GANANCIA_AJUST"]  = penalizar(p, p["LITROS"])
    pipas_rentadas[fecha.date()] = math.ceil(rent_total / CAP_PIPA)
    fecha += timedelta(days=1)

# --------------- exportar ----------------------------------------
sel_df = pd.DataFrame(pend)
suf    = f"{desde_dt:%Y-%m-%d}_A_{hasta_dt:%Y-%m-%d}"
sel_df.to_csv(CSV_DIR/f"programacion_{suf}.csv", index=False)
sel_df[pd.isna(sel_df["FECHA_ASIGNADA"])]\
      .to_csv(CSV_DIR/f"pendientes_{suf}.csv", index=False)

print("\nPipas rentadas por día:")
for d,n in pipas_rentadas.items():
    print(f"{d}: {n} pipas")

print(f"✓ Programación guardada. Fragmentos={len(fragmentos)}. Espera máx={MAX_DIAS_ESPERA}d, respetando FECHA_ENTREGA.")

# --------------- exportar detalle por día (múltiples fechas) ------------------------
fechas_disponibles = sel_df["FECHA_ASIGNADA"].dropna().dt.date.unique()
print("\n📅 Fechas con pedidos asignados:")
print(", ".join(str(f) for f in sorted(fechas_disponibles)))

while True:
    fecha_input = input("\n📆 Ingrese una fecha asignada (YYYY-MM-DD) para exportar mochila de ese día (o escriba 'salir'): ").strip()
    if fecha_input.lower() == "salir":
        break
    if not fecha_input:
        print("⚠️ No se ingresó ninguna fecha.")
        continue
    try:
        fecha_obj = pd.to_datetime(fecha_input).date()
        detalles_dia = sel_df[sel_df["FECHA_ASIGNADA"].dt.date == fecha_obj]

        if detalles_dia.empty:
            print(f"⚠️ No hay pedidos asignados el {fecha_obj}.")
        else:
            cols = ["ID", "CLIENTE", "FECHA", "PRIORIDAD", "LITROS", "GANANCIA", "GANANCIA_AJUST", "LITROS_RENTADOS"]
            out_path = CSV_DIR / f"detalle_mochila_{fecha_obj}.csv"
            detalles_dia[cols].to_csv(out_path, index=False)
            print(f"✅ Exportado: {out_path.name} ({len(detalles_dia)} pedidos)")
            ganancia_total = detalles_dia["GANANCIA_AJUST"].sum()
            print(f"💰 Ganancia total ajustada del {fecha_obj}: ${ganancia_total:,.2f}")
    except Exception as e:
        print(f"⚠️ Error al interpretar la fecha: {e}")
