import inspect

from app.application.use_cases.suspect_use_cases import GetSuspectDetail
from app.infrastructure.duckdb.suspect_repository import DuckDbSuspectRepository

print("=" * 80)
print("GET SUSPECT DETAIL USE CASE")
print("=" * 80)
print(inspect.getsource(GetSuspectDetail))

print()
print("=" * 80)
print("REPOSITORY METHODS")
print("=" * 80)

repo = DuckDbSuspectRepository()

for name in dir(repo):
    if "detail" in name.lower():
        print(name)

