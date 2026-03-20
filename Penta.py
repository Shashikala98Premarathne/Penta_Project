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
    df = df.apply(lambda col: col.map(lambda x: x.strip() if isinstance(x, str) else x))

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
    # VALUE RULES
    # =====================================================

    value_rules = {
        "countryquestion": range(1,10),
        "region": range(1,5),
        "sector": range(1,7),
        "decision_maker": [1],
        "working_experience": range(0,60),
        "job_level": range(1,6),
        "hvo100_awareness": [1,2],
        "hvo100_future_intention": [1,2,3,4,5],
        "hvo100_barriers":[1,2],
        "hvo100_key_drivers": range(1,12),
        "hvo100_key_barriers": range(1,16),
        "hvo100_cost_comparison": list(range(1,7)) + [99],
        "environmental_targets": [1,2,99],
        "environmental_targets_depth": [1,2,3,99],
        "hvo100_other_companies": [1,2,3,4],
        "hvo100_communication": [1,2]
    }

    zero_one_prefixes = [
        "engines_",
        "fuel_types_",
        "fuels_awareness_",
        "fuel_future_intention_"
    ]

    split_prefix = "fuel_usage_split_"
    program_prefix = "environmental_program_"

    # =====================================================
    # COLUMN DETECTION
    # =====================================================

    fuel_cols = [c for c in df.columns if c.startswith("fuel_types_")]
    split_cols = [c for c in df.columns if c.startswith(split_prefix)]
    hvo_cols = [c for c in df.columns if c.startswith("hvo100_")]
    program_cols = [c for c in df.columns if c.startswith(program_prefix)]

    engine_cols = [c for c in df.columns if c.startswith("engines_")and not c.endswith("_other")]
    fuel_awareness_cols = [c for c in df.columns if c.startswith("fuels_awareness_")]
    fuel_future_cols = [c for c in df.columns if c.startswith("fuel_future_intention_")]
    hvo_perception_cols = [c for c in df.columns if c.startswith("hvo100_perception_")]
    hvo_driver_cols = [c for c in df.columns if c.startswith("hvo100_drivers_")]
    hvo_barrier_cols = [c for c in df.columns if c.startswith("hvo100_barriers_")]

    required_vars = [
        "countryquestion","region","sector","l",
        "decision_maker","working_experience",
        "job_level","fleet_size",
        "environmental_targets","hvo100_other_companies"
    ]

    # =====================================================
    # LOOP THROUGH RESPONDENTS
    # =====================================================

    for _, row in df.iterrows():

        respid = row.get("respid")

        # =====================================================
        # REQUIRED VARIABLES
        # =====================================================

        for var in required_vars:
            if var in df.columns and pd.isna(row.get(var)):
                add_error(respid, "MISSING_REQUIRED", var, None, "Must not be empty")

        # =====================================================
        # STRICT GRID (NO EMPTY CELLS)
        # =====================================================

        strict_grids = (
            engine_cols +
            fuel_cols +
            fuel_awareness_cols +
            fuel_future_cols
        )

        if "fuel_main_choice" in df.columns:
            strict_grids.append("fuel_main_choice")

        for col in strict_grids:
            if col in df.columns and pd.isna(row.get(col)):
                add_error(respid, "MISSING_GRID", col, None, "Must not be empty")

        # =====================================================
        # VALUE VALIDATION
        # =====================================================

        for var, allowed in value_rules.items():
            if var in df.columns:
                val = pd.to_numeric(row.get(var), errors="coerce")
                if not pd.isna(val) and val not in allowed:
                    add_error(respid, "VALUE_CHECK", var, row.get(var), f"Allowed: {allowed}")

        # =====================================================
        # 0/1 VALIDATION
        # =====================================================

        for col in df.columns:
            for prefix in zero_one_prefixes:
                if col.startswith(prefix):
                    val = pd.to_numeric(row.get(col), errors="coerce")
                    if not pd.isna(val) and val not in [0,1]:
                        add_error(respid, "VALUE_CHECK_01", col, row.get(col), "0 or 1 only")

        # =====================================================
        # FLEET SIZE
        # =====================================================

        fleet = pd.to_numeric(row.get("fleet_size"), errors="coerce")
        if not pd.isna(fleet):
            if fleet <= 0 or fleet > 999:
                add_error(respid, "FLEET_RANGE", "fleet_size", fleet, "1–999 only")

        # =====================================================
        # JOB LEVEL
        # =====================================================

        job_level = pd.to_numeric(row.get("job_level"), errors="coerce")
        exp = pd.to_numeric(row.get("working_experience"), errors="coerce")

        if job_level == 1:
            add_error(respid, "JOBLEVEL_INVALID", "job_level", job_level, "Cannot be 1")

        if job_level == 2 and not pd.isna(exp) and exp < 3:
            add_error(respid, "JOBLEVEL_EXP", "working_experience", exp, "≥3 required")

        # =====================================================
        # FUEL SPLIT
        # =====================================================

        fuel_count = sum(pd.to_numeric(row.get(c), errors="coerce") == 1 for c in fuel_cols)
        splits = [pd.to_numeric(row.get(c), errors="coerce") for c in split_cols if not pd.isna(row.get(c))]

        if fuel_count == 0 and splits:
            add_error(respid, "FUEL_SPLIT_LOGIC", "split", None, "No splits allowed")

        if fuel_count > 1 and sum(splits) != 100:
            add_error(respid, "FUEL_SPLIT_SUM", "split_total", sum(splits), "Must equal 100")

        # =====================================================
        # HVO CONDITIONAL LOGIC
        # =====================================================

        awareness = pd.to_numeric(row.get("hvo100_awareness"), errors="coerce")
        future = pd.to_numeric(row.get("hvo100_future_intention"), errors="coerce")
        fuel_awareness_2 = pd.to_numeric(row.get("fuels_awareness_2"), errors="coerce")

        if fuel_awareness_2 == 0 and pd.isna(awareness):
            add_error(respid, "MISSING_LOGIC", "hvo100_awareness", None, "Required when fuels_awareness_2=0")

        if awareness == 1 and pd.isna(future):
            add_error(respid, "MISSING_LOGIC", "hvo100_future_intention", None, "Required when awareness=1")

        if future in [1,2] and pd.isna(row.get("hvo100_oe_barriers")):
            add_error(respid, "MISSING_LOGIC", "hvo100_oe_barriers", None, "Required when future=1,2")

        if future in [3,4,5] and pd.isna(row.get("hvo100_oe_drivers")):
            add_error(respid, "MISSING_LOGIC", "hvo100_oe_drivers", None, "Required when future=3,4,5")

        if awareness == 1:

            for c in hvo_perception_cols + hvo_driver_cols + hvo_barrier_cols:
                if pd.isna(row.get(c)):
                    add_error(respid, "MISSING_HVO_BLOCK", c, None, "Required when awareness=1")

            driver_selected = any(
                pd.to_numeric(row.get(c), errors="coerce") == 1
                for c in hvo_driver_cols
            )

            if driver_selected and pd.isna(row.get("hvo100_key_drivers")):
                add_error(respid, "MISSING_KEY_DRIVER", "hvo100_key_drivers", None, "Required when driver selected")

            if pd.isna(row.get("hvo100_key_barriers")):
                add_error(respid, "MISSING_KEY_BARRIER", "hvo100_key_barriers", None, "Required when awareness=1")

            for var in ["hvo100_cost_comparison", "hvo100_operational_changes_OE"]:
                if pd.isna(row.get(var)):
                    add_error(respid, "MISSING_HVO_FIELD", var, None, "Required when awareness=1")

        # =====================================================
        # ENVIRONMENT
        # =====================================================

        env = pd.to_numeric(row.get("environmental_targets"), errors="coerce")

        if env == 1:

            if pd.isna(row.get("environmental_targets_depth")):
                add_error(respid, "MISSING_ENV", "environmental_targets_depth", None, "Required")

            for c in program_cols:
                if pd.isna(row.get(c)):
                    add_error(respid, "MISSING_ENV_PROGRAM", c, None, "Required")

        # =====================================================
        # COMMUNICATION
        # =====================================================

        other = pd.to_numeric(row.get("hvo100_other_companies"), errors="coerce")

        if other in [1,2] and pd.isna(row.get("hvo100_communication")):
            add_error(respid, "MISSING_COMM", "hvo100_communication", None, "Required")

    # =====================================================
    # REPORT
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