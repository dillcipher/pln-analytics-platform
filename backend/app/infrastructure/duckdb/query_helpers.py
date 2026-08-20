"""
Shared helpers for building parameterized SQL fragments.
"""

from __future__ import annotations

from typing import Any


def build_equality_filters(
    filters: dict[str, Any],
    column_map: dict[str, str],
) -> tuple[str, list[Any]]:
    """
    Build SQL equality filters.

    Example

        filters:

            {
                "unitup": "ULP METRO",
                "tariff": "R1",
            }

    Result

        AND UNITUP = ?
        AND TARIF = ?

    Parameters are always returned separately.
    """

    clauses: list[str] = []
    params: list[Any] = []

    for key, value in filters.items():

        if value in (None, "", []):
            continue

        column = column_map.get(key)

        if column is None:
            continue

        clauses.append(
            f"{column} = ?"
        )

        params.append(
            value
        )

    if not clauses:
        return "", []

    return (
        " AND " + " AND ".join(clauses),
        params,
    )


def build_search_clause(
    search: str | None,
    columns: list[str],
) -> tuple[str, list[Any]]:
    """
    Build case-insensitive LIKE search.

    Example

        search = "metro"

        columns =

            IDPEL

            NAMA
    """

    if search is None:
        return "", []

    search = search.strip()

    if not search:
        return "", []

    like = f"%{search}%"

    clauses = [
        f"{column} ILIKE ?"
        for column in columns
    ]

    return (
        " AND ("
        + " OR ".join(clauses)
        + ")",
        [like] * len(columns),
    )


def paginate(
    page: int,
    page_size: int,
    max_page_size: int,
) -> tuple[int, int]:
    """
    Normalize pagination.

    Returns

        offset

        page_size
    """

    page = max(
        page,
        1,
    )

    page_size = max(
        1,
        min(
            page_size,
            max_page_size,
        ),
    )

    offset = (
        page - 1
    ) * page_size

    return (
        offset,
        page_size,
    )