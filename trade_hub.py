import streamlit as st
import pandas as pd
import re

from backend import submit_trade
from backend import search_trade

# =====================================================
# PAGE CONFIG
# =====================================================

st.set_page_config(
    page_title="Trade Loading Hub",
    page_icon="📈",
    layout="wide"
)

# =====================================================
# CUSTOM CSS
# =====================================================

st.markdown(
    """
    <style>

    .block-container {
        padding-top: 1rem;
    }

    div.stButton > button {
        background-color: #ff8c00;
        color: white;
        border: none;
        font-weight: 600;
    }

    div.stButton > button:hover {
        background-color: #e67e22;
        color: white;
    }

    </style>
    """,
    unsafe_allow_html=True
)

# =====================================================
# SESSION STATE
# =====================================================

if "environment_results" not in st.session_state:
    st.session_state.environment_results = {}

if "processing" not in st.session_state:
    st.session_state.processing = False

if "trade_search_results" not in st.session_state:
    st.session_state.trade_search_results = {}

# =====================================================
# TITLE
# =====================================================

st.markdown(
    """
    <h1 style='text-align:center;margin-top:0;'>
        Trade Loading Hub
    </h1>
    """,
    unsafe_allow_html=True
)

# =====================================================
# ENVIRONMENTS
# =====================================================

button_left, center_col, button_right = st.columns(
    [4, 2, 4]
)

with center_col:

    selected_environments = st.multiselect(
        "Environment(s)",
        [
            "Smoke2",
            "Smoke3",
            "Smoke5 (Coming Soon)",
            "Systest1 (Coming Soon)",
            "Systest2 (Coming Soon)"
        ],
        default=[]
    )

# =====================================================
# FILE UPLOAD
# =====================================================

button_left, center_col, button_right = st.columns(
    [4, 2, 4]
)

with center_col:

    xml_file = st.file_uploader(
        "Upload Trade XML",
        type=["xml"]
    )
# =====================================================
# LOAD TRADE BUTTON
# =====================================================
load_button_enabled = (
    xml_file is not None
)

if load_button_enabled:

    st.markdown(
        """
        <style>

        div.stButton > button {
            background-color: #ff8c00 !important;
            color: white !important;
            border: none !important;
        }

        div.stButton > button:hover {
            background-color: #e67e22 !important;
            color: white !important;
        }

        </style>
        """,
        unsafe_allow_html=True
    )

else:

    st.markdown(
        """
        <style>

        div.stButton > button {
            background-color: #5f6368 !important;
            color: white !important;
            border: none !important;
        }

        </style>
        """,
        unsafe_allow_html=True
    )

button_left, button_middle, button_right = st.columns(
    [4, 2, 4]
)

with button_middle:

    load_trade = st.button(
        "Load Trade",
        use_container_width=True,
        disabled=xml_file is None
    )

# =====================================================
# XML PARSING
# =====================================================

message_id = "-"
product_type = "-"
currency = "-"
trade_date = "-"
trade_api = "-"
notional = "-"
po = "-"
cp = "-"
xml_content = ""

if xml_file:

    xml_content = xml_file.read().decode(
        "utf-8",
        errors="ignore"
    )

    message_id_match = re.search(
        r"messageId>(.*?)<",
        xml_content,
        re.DOTALL
    )

    trade_date_match = re.search(
        r"tradeDate>(.*?)<",
        xml_content,
        re.DOTALL
    )

    currency_match = re.search(
        r"currency>(.*?)<",
        xml_content,
        re.DOTALL
    )

    notional_match = re.search(
        r"initialValue>(.*?)<",
        xml_content,
        re.DOTALL
    )

    srcsys_match = re.search(
        r"srcSysId>(.*?)<",
        xml_content,
        re.DOTALL
    )

    party_matches = re.findall(
        r"partyId>(.*?)<",
        xml_content,
        re.DOTALL
    )

    if message_id_match:
        message_id = message_id_match.group(1).strip()

    if trade_date_match:
        trade_date = trade_date_match.group(1).strip()

    if currency_match:
        currency = currency_match.group(1).strip()

    if notional_match:
        notional = notional_match.group(1).strip()

    if srcsys_match:
        trade_api = srcsys_match.group(1).strip()

    if len(party_matches) >= 2:
        po = party_matches[0].strip()
        cp = party_matches[1].strip()

    if "<fpml:swap>" in xml_content:
        product_type = "Interest Rate Swap (IRS)"
    elif "fxForward" in xml_content:
        product_type = "FX Forward"
    else:
        product_type = "Unknown"

# =====================================================
# LOAD TRADE PROCESSING
# =====================================================

if load_trade:

    if not xml_content:

        st.error(
            "Please upload an XML file."
        )

    else:

        st.session_state.processing = True

        environment_results = {}
        trade_results = {}

        for environment in selected_environments:

            if environment not in [
                "Smoke2",
                "Smoke3"
            ]:

                environment_results[environment] = {
                    "status": "NOT_SUPPORTED"
                }

                continue

            result = submit_trade(
                environment,
                xml_content
            )

            if result["status"] == "SUCCESS":

                search_result = search_trade(
                    environment,
                    message_id
                )

                environment_results[environment] = {

                    "status": "SUCCESS",

                    "ack": result.get(
                        "response",
                        ""
                    ),

                    "trade_count": search_result.get(
                        "count",
                        0
                    )
                }

                trade_results[environment] = (
                    search_result.get(
                        "rows",
                        []
                    )
                )

            else:

                environment_results[environment] = {
                    "status": "FAILED"
                }

        st.session_state.environment_results = environment_results
        st.session_state.trade_search_results = trade_results
        st.session_state.processing = False

        st.rerun()

# =====================================================
# REQUEST + RESPONSE
# =====================================================

with st.expander(
    "Request & Response",
    expanded=xml_file is not None
):

    request_col, divider_col, response_col = st.columns(
        [1, 0.05, 1.2]
    )

    # =================================================
    # REQUEST
    # =================================================

    with request_col:

        st.subheader("Request")

        summary_data = {
            "Environment(s)": ", ".join(selected_environments),
            "Trade Entry API": trade_api,
            "Product Type": product_type,
            "Message ID": message_id,
            "PO": po,
            "CP": cp,
            "Currency": currency,
            "Trade Date": trade_date,
            "Notional": notional
        }

        for label, value in summary_data.items():

            c1, c2 = st.columns([1, 2])

            with c1:
                st.markdown(f"**{label}**")

            with c2:
                st.write(value)

    # =================================================
    # DIVIDER
    # =================================================

    with divider_col:

        st.markdown(
            """
            <div style="
                border-left:1px solid rgba(200,200,200,0.4);
                height:100%;
                min-height:500px;">
            </div>
            """,
            unsafe_allow_html=True
        )

    # =================================================
    # RESPONSE
    # =================================================

    with response_col:

        st.subheader("Response")

        if xml_file:

            st.success(
                "✅ XML Uploaded"
            )

            st.success(
                "✅ Request Parsed"
            )

        if st.session_state.processing:

            st.info(
                "🔄 Submitting Trade..."
            )

        for env, result in (
            st.session_state.environment_results.items()
        ):

            st.markdown(f"### {env}")

            if result["status"] == "SUCCESS":

                st.success(
                    "✅ Trade Submitted Successfully"
                )

                st.success(
                    "✅ TradeSubmissionAck Received"
                )

                st.success(
                    f"✅ {result['trade_count']} Trade(s) Found"
                )

            elif result["status"] == "FAILED":

                st.error(
                    "❌ Trade Submission Failed"
                )

            elif result["status"] == "NOT_SUPPORTED":

                st.warning(
                    "⚠ Environment Not Supported Yet"
                )

# =====================================================
# TRADE SEARCH RESULTS
# =====================================================

if st.session_state.trade_search_results:

    with st.expander(
        "Trade Search Results",
        expanded=True
    ):

        for env, rows in (
            st.session_state.trade_search_results.items()
        ):

            st.subheader(env)

            df = pd.DataFrame(rows)

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )

# =====================================================
# ACKS
# =====================================================

with st.expander(
    "Trade Submission Acknowledgements"
):

    for env, result in (
        st.session_state.environment_results.items()
    ):

        if "ack" in result:

            st.subheader(env)

            st.code(
                result["ack"],
                language="xml"
            )

# =====================================================
# XML PREVIEW
# =====================================================

if xml_file:

    with st.expander(
        "Uploaded XML Preview"
    ):

        st.code(
            xml_content,
            language="xml"
        )