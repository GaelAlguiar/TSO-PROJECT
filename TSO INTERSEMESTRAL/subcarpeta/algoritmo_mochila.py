import pandas as pd, re, math, sys
from pathlib import Path
from datetime import datetime, timedelta
from ortools.algorithms.python import knapsack_solver

# ---------------- Parámetros del negocio ----------------
CSV_DIR         = Path("csv")
CAP_PROPIA      = 1_920_000
CAP_PIPA        = 64_000
PENALIZ         = 0.05
MAX_DIAS_ESPERA = 2
VALOR_MAP       = {1: 3, 2: 2, 3: 1}

def ejecutar():
    try:
        # Buscar archivo de prioridad
        prior_csv = next(CSV_DIR.glob("prioridad_clientes*_A_*.csv"))
        ped_csv   = CSV_DIR / f"pedidos_limpios{prior_csv.stem.replace('prioridad_clientes','')}.csv"

        # Extraer fechas del nombre
        m = re.search(r'_(\d{4}-\d{2}-\d{2})_A_(\d{4}-\d{2}-\d{2})', prior_csv.stem, re.I)
        if not m:
            return "❌ El nombre de prioridad debe contener rango _YYYY-MM-DD_A_YYYY-MM-DD"
        desde_dt, hasta_dt = map(datetime.fromisoformat, m.groups())

        # Cargar prioridad
        prio_map = pd.read_csv(prior_csv).set_index("CLIENTE")["Prioridad"]

        # Cargar pedidos
        raw = pd.read_csv(ped_csv, parse_dates=["FECHA"])
        if "FECHA ENTREGA" in raw.columns:
            raw["FECHA_ENTREGA"] = pd.to_datetime(raw["FECHA ENTREGA"], dayfirst=True, errors="coerce")
        else:
            raw["FECHA_ENTREGA"] = pd.Timestamp.max

        # Fragmentar pedidos grandes
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

        # Inicializar columnas
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

        # Algoritmo mochila helper
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

        # Simulación diaria
        while any(pd.isna(p["FECHA_ASIGNADA"]) for p in pend):
            hoy = [p for p in pend if pd.isna(p["FECHA_ASIGNADA"]) and p["FECHA_DISP"] <= fecha and fecha <= p["FECHA_ENTREGA"]]
            if not hoy:
                fecha += timedelta(days=1)
                continue

            for p in hoy: p["ESPERA_DIAS"] += 1
            cand = [p for p in hoy if p["ESPERA_DIAS"] <= MAX_DIAS_ESPERA]

            idx_sel = solve_knapsack(cand, CAP_PROPIA)
            sel_set  = {id(cand[i]) for i in idx_sel}
            for p in cand:
                if id(p) in sel_set:
                    p["FECHA_ASIGNADA"] = fecha

            rent_total = 0
            for p in hoy:
                if pd.notna(p["FECHA_ASIGNADA"]): continue
                p["FECHA_ASIGNADA"]  = fecha
                p["LITROS_RENTADOS"] = p["LITROS"]
                rent_total          += p["LITROS"]
                p["GANANCIA_AJUST"]  = penalizar(p, p["LITROS"])
            pipas_rentadas[fecha.date()] = math.ceil(rent_total / CAP_PIPA)
            fecha += timedelta(days=1)

        # Exportar archivos
        sel_df = pd.DataFrame(pend)
        suf = f"{desde_dt:%Y-%m-%d}_A_{hasta_dt:%Y-%m-%d}"
        sel_df.to_csv(CSV_DIR/f"programacion_{suf}.csv", index=False)
        sel_df[pd.isna(sel_df["FECHA_ASIGNADA"])]\
              .to_csv(CSV_DIR/f"pendientes_{suf}.csv", index=False)
        
        sel_df[pd.notna(sel_df["FECHA_ASIGNADA"])]\
        .to_csv(CSV_DIR / f"programacion_detallada_{suf}.csv", index=False)

        return f"✓ Programación terminada. Fragmentos: {len(fragmentos)}. Pipas rentadas: {sum(pipas_rentadas.values())}"

    except StopIteration:
        return "❌ No se encontró ningún archivo 'prioridad_clientes*_A_*.csv' en la carpeta csv/"
    except Exception as e:
        return f"❌ Error en la ejecución del algoritmo: {e}"
