import pandas as pd, re
from pathlib import Path
from datetime import datetime

CSV_DIR      = Path("csv")
PEDIDOS_CSV  = CSV_DIR / "Pedidos.csv"

# VALOR = {1: 100, 2: 10, 3: 1} algoritmo Greedy
# (ordenar por VALOR y tomar pedidos mientras quepan) garantiza que siempre se llenen primero los de
# Prioridad 1, luego Prioridad 2 y por último Prioridad 3.

VALOR = {1: 100, 2: 10, 3: 1}

# ---------------- localizar prioridad_clientes*.csv -----------------
prior_files = sorted(CSV_DIR.glob("prioridad_clientes*.csv"))
if not prior_files:
    raise SystemExit("No hay prioridad_clientes*.csv en /csv")
prior_csv = prior_files[0]
print("Prioridades:", prior_csv.name)

# ---------------- extraer rango del nombre --------------------------
m = re.search(r"_(\d{4}-\d{2}-\d{2})_a_(\d{4}-\d{2}-\d{2})", prior_csv.stem, re.I)
if not m:
    raise SystemExit("El nombre debe contener _YYYY-MM-DD_A_YYYY-MM-DD")
desde, hasta = map(datetime.fromisoformat, m.groups())
print(f"Rango: {desde.date()} → {hasta.date()}")

# ---------------- cargar prioridades -------------------------------
prio_map = (
    pd.read_csv(prior_csv, usecols=["CLIENTE", "Prioridad"])
      .set_index("CLIENTE")["Prioridad"]
)

# ---------------- cargar Pedidos.csv -------------------------------
raw = pd.read_csv(PEDIDOS_CSV, low_memory=False)

# fecha exacta dd/mm/yyyy
raw["FECHA DE PEDIDO"] = pd.to_datetime(
    raw["FECHA DE PEDIDO"].astype(str).str.strip(),
    format="%d/%m/%Y",
    errors="coerce"
)

# filtrar rango
ped = raw[(raw["FECHA DE PEDIDO"] >= desde) &
          (raw["FECHA DE PEDIDO"] <= hasta)].copy()

# columnas indispensables
ped["ID"]      = ped.get("IDPEDIDO", ped.get("PEDIDO", range(len(ped))))
ped["CLIENTE"] = ped["CLIENTE"]
ped["FECHA"]   = ped["FECHA DE PEDIDO"]

# limpiar litros
ped["LITROS"] = pd.to_numeric(
    ped["LITROS REALES"].astype(str).replace(r"[^0-9.\-]", "", regex=True),
    errors="coerce"
).fillna(0)

# asignar prioridad y valor
ped["PRIORIDAD"] = ped["CLIENTE"].map(prio_map).fillna(2).astype(int)
ped["VALOR"]     = ped["PRIORIDAD"].map(VALOR)

# seleccionar y ordenar columnas
out_cols = ["ID", "CLIENTE", "FECHA", "LITROS", "PRIORIDAD", "VALOR"]
clean_df = ped[out_cols]

# ---------------- guardar -----------------
sufijo   = f"{desde:%Y-%m-%d}_A_{hasta:%Y-%m-%d}"
outfile  = CSV_DIR / f"pedidos_limpios_{sufijo}.csv"
clean_df.to_csv(outfile, index=False)

print(f"✔ Archivo listo para la mochila → {outfile}  ({len(clean_df)} filas)")
