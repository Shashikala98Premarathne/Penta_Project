import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="Penta Project – Full Rule Validator", layout="wide")
st.title("Penta Project – Survey Logic Checker")

uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

if uploaded_file:

    df = pd.read_excel(uploaded_file)

    # =====================================================
    # GLOBAL CLEANING
    # =====================================================

    df = df.replace(["#NULL!", "NULL", "null", ""], np.nan)
    df.columns = df.columns.str.strip()
    df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

    st.success("Excel uploaded and cleaned successfully")

    validation_errors = []

    def add_error(respid, rule_id, variable, actual_value, expected):
        validation_errors.append({
            "respid": respid,
            "RuleID": rule_id,
            "Variable": variable,
            "Actual_Value": actual_value,
            "Expected": expected
        })

    # =====================================================
    # VALUE DOMAIN DEFINITIONS
    # =====================================================

    value_rules = {
        "countryquestion": range(1,9),
        "region": [1,2,3,4],
        "sector":range(1,10),
        "decision_maker": [1],
        "industry": list(range(1,11)) + [99],
        "working_experience": range(0,30),
        "job_level":range(1,6),
        "hvo100_awareness": [1,2],
        "hvo100_future_intention":range(1,6),
        "preparation": range(1,7),
        "hvo100_perception_": list(range(1,11)) + [99],
        "hvo100_drivers_": [1,2],
        "bev_3": range(1,6),
        "rear_bev": [1,2,3],
        "crane_13": [1,2,3,4],
        "crane_22": [1,2,3,4],
        "main_make_model": list(range(1,18)) + [98]
    }

    # All 0/1 variables
    zero_one_prefixes = [
        "engines_",
        "fuel_types_",
        "fuel_awareness_",
        "fuel_future_intention_",
        "in_fleetcoded_",
        "barriers_",
        "truck_quantity_dk",
        "type_quantity_dk"
    ]

    # Matrix 1–5 validation
    matrix_prefixes = [
        "drivers_vf_13_",
        "drivers_vf_22_",
        "drivers_body_13_",
        "drivers_body_22_",
        "drivers_bus_13_",
        "drivers_bus_22_"
    ]

    body13_cols = [c for c in df.columns if c.startswith("body_type_13_")]
    body22_cols = [c for c in df.columns if c.startswith("body_type_22_")]

    # =====================================================
    # LOOP THROUGH RESPONDENTS
    # =====================================================

    for _, row in df.iterrows():

        respid = row.get("respid")

        # -----------------------------
        # GENERIC VALUE CHECK FUNCTION
        # -----------------------------

        def check_value(var, valid_values, rule_id):

            raw_val = row.get(var)
            val = pd.to_numeric(raw_val, errors="coerce")

            if pd.isna(val):
                return

            if val not in valid_values:
                add_error(
                    respid,
                    rule_id,
                    var,
                    raw_val,
                    f"Allowed values: {valid_values}"
                )

        # -----------------------------
        # APPLY FIXED VALUE RULES
        # -----------------------------

        for var, valid_vals in value_rules.items():
            if var in df.columns:
                check_value(var, valid_vals, "VALUE_CHECK")

        # -----------------------------
        # 0/1 VARIABLES
        # -----------------------------

        for col in df.columns:
            for prefix in zero_one_prefixes:
                if col.startswith(prefix):
                    raw_val = row.get(col)
                    val = pd.to_numeric(raw_val, errors="coerce")

                    if pd.isna(val):
                        continue

                    if val not in [0,1]:
                        add_error(
                            respid,
                            "VALUE_CHECK_01",
                            col,
                            raw_val,
                            "Allowed values: 0 or 1"
                        )

        # -----------------------------
        # MATRIX 1–5 VALIDATION
        # -----------------------------

        for col in df.columns:
            for prefix in matrix_prefixes:
                if col.startswith(prefix):
                    raw_val = row.get(col)
                    val = pd.to_numeric(raw_val, errors="coerce")

                    if pd.isna(val):
                        continue

                    if val not in range(1,6):
                        add_error(
                            respid,
                            "VALUE_CHECK_MATRIX",
                            col,
                            raw_val,
                            "Allowed values: 1–5"
                        )

        # -----------------------------
        # TRUCK QUANTITY 0–999
        # -----------------------------

        truck_q = pd.to_numeric(row.get("truck_quantity"), errors="coerce")

        if not pd.isna(truck_q):
            if truck_q < 0 or truck_q > 999:
                add_error(
                    respid,
                    "TRUCK_RANGE",
                    "truck_quantity",
                    truck_q,
                    "Allowed range: 0–999"
                )

        # -----------------------------
        # LOGIC VALIDATIONS (Existing)
        # -----------------------------

        tq1 = pd.to_numeric(row.get("type_quantity_1"), errors="coerce")
        tq2 = pd.to_numeric(row.get("type_quantity_2"), errors="coerce")

        tq1 = 0 if pd.isna(tq1) else tq1
        tq2 = 0 if pd.isna(tq2) else tq2
        truck_q = 0 if pd.isna(truck_q) else truck_q

        if truck_q > 0:

            if tq1 <= 0 and tq2 <= 0:
                add_error(
                    respid,
                    "LOGIC_TYPE",
                    "type_quantity_1/type_quantity_2",
                    f"{tq1}/{tq2}",
                    "At least one must be >0"
                )

            if tq1 + tq2 != truck_q:
                add_error(
                    respid,
                    "LOGIC_SUM",
                    "type_quantity_sum",
                    tq1 + tq2,
                    f"Must equal truck_quantity ({truck_q})"
                )

        # -----------------------------
        # BODY SUM CHECK
        # -----------------------------

        total_body13 = 0

        for c in body13_cols:
            val = pd.to_numeric(row.get(c), errors="coerce")
            if not pd.isna(val):
                total_body13 += val

        if tq2 > 0 and total_body13 != tq2:
            add_error(
                respid,
                "LOGIC_BODY13",
                "body_type_13_total",
                total_body13,
                f"Must equal type_quantity_2 ({tq2})"
            )

        total_body22 = 0

        for c in body22_cols:
            val = pd.to_numeric(row.get(c), errors="coerce")
            if not pd.isna(val):
                total_body22 += val

        if tq1 > 0 and total_body22 != tq1:
            add_error(
                respid,
                "LOGIC_BODY22",
                "body_type_22_total",
                total_body22,
                f"Must equal type_quantity_1 ({tq1})"
            )

    # =====================================================
    # BUILD REPORT
    # =====================================================

    report_df = pd.DataFrame(validation_errors)

    st.subheader("Validation Report")

    if report_df.empty:
        st.success("No validation errors found!")
    else:
        st.dataframe(report_df)

    # =====================================================
    # EXPORT
    # =====================================================

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        report_df.to_excel(writer, index=False, sheet_name="Validation_Report")

    st.download_button(
        "Download Validation Report",
        output.getvalue(),
        "Validation_Report.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )