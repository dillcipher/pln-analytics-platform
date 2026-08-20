from app.infrastructure.duckdb.connection import dataset_exists

names = [
    "fact_anev",
    "fact_pengecekan",
    "suspect_main",
    "suspect_summary",
    "suspect_detail",
]

for name in names:
    print(f"{name:20} = {dataset_exists(name)}")
