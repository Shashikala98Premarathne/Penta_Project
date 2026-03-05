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
    # VALUE DOMAIN RULES
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
    # COLUMN DETECTION (performance improvement)
    # =====================================================

    fuel_cols = [c for c in df.columns if c.startswith("fuel_types_")]
    split_cols = [c for c in df.columns if c.startswith(split_prefix)]
    hvo_cols = [c for c in df.columns if c.startswith("hvo100_")]
    program_cols = [c for c in df.columns if c.startswith(program_prefix)]

    # =====================================================
    # LOOP THROUGH RESPONDENTS
    # =====================================================

    for _, row in df.iterrows():

        respid = row.get("respid")

        # =====================================================
        # BASIC VALUE VALIDATION
        # =====================================================

        for var, allowed in value_rules.items():

            if var in df.columns:

                val = pd.to_numeric(row.get(var), errors="coerce")

                if not pd.isna(val) and val not in allowed:

                    add_error(
                        respid,
                        "VALUE_CHECK",
                        var,
                        row.get(var),
                        f"Allowed values: {allowed}"
                    )

        # =====================================================
        # PREFIX VALIDATIONS (0/1 VARIABLES)
        # =====================================================

        for col in df.columns:

            for prefix in zero_one_prefixes:

                if col.startswith(prefix):

                    val = pd.to_numeric(row.get(col), errors="coerce")

                    if not pd.isna(val) and val not in [0,1]:

                        add_error(
                            respid,
                            "VALUE_CHECK_01",
                            col,
                            row.get(col),
                            "Allowed values: 0 or 1"
                        )

        # =====================================================
        # ENGINE RANGE VALIDATION
        # =====================================================

        for col in df.columns:

            if col.startswith("engines_"):

                code = col.split("_")[1]

                if code.isdigit():

                    code = int(code)

                    if not (1 <= code <= 15 or code in [95,96,97,99]):

                        add_error(
                            respid,
                            "ENGINE_RANGE",
                            col,
                            code,
                            "Allowed: 1-15,95-99"
                        )

        # =====================================================
        # FLEET SIZE
        # =====================================================

        fleet = pd.to_numeric(row.get("fleet_size"), errors="coerce")

        if not pd.isna(fleet):

            if fleet < 0 or fleet > 999:

                add_error(
                    respid,
                    "FLEET_RANGE",
                    "fleet_size",
                    fleet,
                    "Allowed range 0–999"
                )

            if fleet == 0:

                add_error(
                    respid,
                    "FLEET_ZERO",
                    "fleet_size",
                    fleet,
                    "Fleet size must be >0"
                )

        # =====================================================
        # JOB LEVEL LOGIC
        # =====================================================

        job_level = pd.to_numeric(row.get("job_level"), errors="coerce")
        experience = pd.to_numeric(row.get("working_experience"), errors="coerce")

        if not pd.isna(job_level):

            if job_level == 1:

                add_error(
                    respid,
                    "JOBLEVEL_INVALID",
                    "job_level",
                    job_level,
                    "job_level cannot be 1"
                )

            if job_level == 2 and not pd.isna(experience) and experience < 3:

                add_error(
                    respid,
                    "JOBLEVEL_EXPERIENCE",
                    "working_experience",
                    experience,
                    "job_level=2 requires experience ≥3"
                )

        # =====================================================
        # FUEL TYPE COUNT
        # =====================================================

        fuel_count = sum(
            pd.to_numeric(row.get(c), errors="coerce") == 1
            for c in fuel_cols
        )

        # =====================================================
        # FUEL SPLIT LOGIC
        # =====================================================

        split_values = []

        for c in split_cols:

            val = pd.to_numeric(row.get(c), errors="coerce")

            if not pd.isna(val):
                split_values.append(val)

        # CASE 1: fuel_count = 0 → splits should not exist

        if fuel_count == 0 and split_values:

            for c in split_cols:

                if not pd.isna(row.get(c)):

                    add_error(
                        respid,
                        "FUEL_SPLIT_LOGIC",
                        c,
                        row.get(c),
                        "Fuel split should not exist when no fuel type selected"
                    )

        # CASE 2: fuel_count > 1 → splits must sum to 100

        if fuel_count > 1 and split_values:

            total_split = sum(split_values)

            if total_split != 100:

                add_error(
                    respid,
                    "FUEL_SPLIT_SUM",
                    "fuel_usage_split_total",
                    total_split,
                    "fuel_usage_split_1 + 2 + 3 must equal 100"
                )

        # =====================================================
        # HVO LOGIC
        # =====================================================

        awareness = pd.to_numeric(row.get("hvo100_awareness"), errors="coerce")
        future = pd.to_numeric(row.get("hvo100_future_intention"), errors="coerce")

        if awareness != 1 and not pd.isna(awareness) and not pd.isna(future):

            add_error(
                respid,
                "HVO_FUTURE_LOGIC",
                "hvo100_future_intention",
                future,
                "Only if awareness=1"
            )

        barriers = row.get("hvo100_oe_barriers")

        if future not in [1,2] and not pd.isna(barriers):

            add_error(
                respid,
                "HVO_BARRIER_LOGIC",
                "hvo100_oe_barriers",
                barriers,
                "Only if future intention =1 or 2"
            )

        for c in hvo_cols:

            if c in ["hvo100_awareness","hvo100_future_intention",
                     "hvo100_other_companies","hvo100_communication"]:
                continue

            if awareness != 1 and not pd.isna(awareness) and not pd.isna(row.get(c)):

                add_error(
                    respid,
                    "HVO_AWARENESS_BLOCK",
                    c,
                    row.get(c),
                    "Only if awareness=1"
                )

        # =====================================================
        # ENVIRONMENTAL LOGIC
        # =====================================================

        env_target = pd.to_numeric(row.get("environmental_targets"), errors="coerce")
        env_depth = row.get("environmental_targets_depth")

        if env_target != 1 and not pd.isna(env_depth):

            add_error(
                respid,
                "ENV_DEPTH_LOGIC",
                "environmental_targets_depth",
                env_depth,
                "Only if environmental_targets=1"
            )

        if env_target != 1:

            for c in program_cols:

                if not pd.isna(row.get(c)):

                    add_error(
                        respid,
                        "ENV_PROGRAM_LOGIC",
                        c,
                        row.get(c),
                        "Only if environmental_targets=1"
                    )

        # =====================================================
        # COMMUNICATION LOGIC
        # =====================================================

        other_comp = pd.to_numeric(row.get("hvo100_other_companies"), errors="coerce")
        comm = row.get("hvo100_communication")

        if other_comp not in [1,2] and not pd.isna(comm):

            add_error(
                respid,
                "COMMUNICATION_LOGIC",
                "hvo100_communication",
                comm,
                "Only if hvo100_other_companies =1 or 2"
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