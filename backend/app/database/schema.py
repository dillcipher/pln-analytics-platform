from __future__ import annotations


CREATE_TABLES = [

"""
CREATE TABLE IF NOT EXISTS fact_anev (

    id BIGINT,

    unitupi TEXT,

    unitap TEXT,

    unitup TEXT,

    location_code TEXT,

    location_name TEXT,

    tariff TEXT,

    power INTEGER,

    read_date DATE,

    suspect_name TEXT,

    current_l1 DOUBLE,

    current_l2 DOUBLE,

    current_l3 DOUBLE,

    current_n DOUBLE,

    voltage_l1 DOUBLE,

    voltage_l2 DOUBLE,

    voltage_l3 DOUBLE,

    dataset TEXT,

    source_file TEXT,

    period TEXT

);
""",

"""
CREATE TABLE IF NOT EXISTS fact_dlpd (

    idpel TEXT,

    customer_name TEXT,

    billing_period TEXT,

    dlpd DOUBLE,

    dataset TEXT,

    period TEXT

);
""",

"""
CREATE TABLE IF NOT EXISTS fact_pengecekan (

    idpel TEXT,

    status TEXT,

    update_status TEXT,

    description TEXT,

    dataset TEXT,

    period TEXT

);
"""

]