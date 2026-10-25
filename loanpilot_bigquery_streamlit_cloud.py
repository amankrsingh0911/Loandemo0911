import json
import streamlit as st
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

# LoanPilot AI - Streamlit Cloud deployment version
# Configure credentials in Streamlit Cloud -> Manage app -> Settings -> Secrets.

PROJECT_ID = "loanapp-0911"
DATASET_ID = "loan_demo"
TABLE_NAME = "loan_master_data"
TABLE_ID = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_NAME}"

DEMO_POLICY = {
    "minimum_credit_score": 700,
    "maximum_foir_percent": 40,
}

st.set_page_config(page_title="LoanPilot AI", page_icon="🏦", layout="wide")
st.title("LoanPilot AI")
st.caption("AI-assisted personal loan assessment | Fictional data and simulated checks")


def get_bigquery_client():
    """Create an explicitly authenticated client for Streamlit Cloud.

    Supported secrets formats:
      1) gcp_service_account_json = '''{ ... downloaded service account JSON ... }'''
      2) [gcp_service_account] followed by the JSON key fields as TOML values.
    """
    if "gcp_service_account_json" in st.secrets:
        raw = st.secrets["gcp_service_account_json"]
        if isinstance(raw, str):
            service_account_info = json.loads(raw)
        else:
            service_account_info = dict(raw)
    elif "gcp_service_account" in st.secrets:
        service_account_info = dict(st.secrets["gcp_service_account"])
    else:
        raise RuntimeError(
            "Google Cloud credentials are not configured. In Streamlit Cloud, "
            "open Manage app → Settings → Secrets and add either a "
            "gcp_service_account_json secret containing the complete service-account "
            "JSON, or a [gcp_service_account] TOML section containing its fields."
        )

    credentials = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return bigquery.Client(project=PROJECT_ID, credentials=credentials)


@st.cache_data(ttl=60, show_spinner="Loading loan applications from BigQuery...")
def load_loan_data():
    client = get_bigquery_client()
    query = f"""
        SELECT
            application_id,
            name,
            monthly_income,
            existing_emi,
            loan_amount,
            tenure_months,
            annual_interest_rate,
            credit_score,
            documents_complete,
            identity_verified,
            overdue_flag
        FROM `{TABLE_ID}`
        ORDER BY application_id
    """
    df = client.query(query).to_dataframe()

    required = {
        "application_id", "name", "monthly_income", "existing_emi",
        "loan_amount", "tenure_months", "annual_interest_rate", "credit_score",
        "documents_complete", "identity_verified", "overdue_flag",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError("BigQuery table is missing required columns: " + ", ".join(missing))
    return df


try:
    applicants = load_loan_data()
except Exception as exc:
    st.error("Could not load loan applications from BigQuery.")
    st.markdown(
        "Check that `requirements.txt` includes `google-cloud-bigquery`, "
        "that Streamlit Cloud Secrets contain the service-account credentials, "
        "and that the service account has **BigQuery Job User** on the project "
        "and **BigQuery Data Viewer** access to the `loan_demo` dataset."
    )
    # Show useful error detail while avoiding printing credential contents.
    st.exception(exc)
    st.stop()

if applicants.empty:
    st.warning("No loan applications were found in BigQuery.")
    st.stop()

st.success(f"Loaded {len(applicants)} loan applications from BigQuery.")


def calculate_emi(principal, annual_rate, months):
    principal = float(principal)
    annual_rate = float(annual_rate)
    months = int(months)
    if principal <= 0 or months <= 0:
        raise ValueError("Principal and tenure must be positive.")
    monthly_rate = annual_rate / 1200
    if monthly_rate == 0:
        return principal / months
    factor = (1 + monthly_rate) ** months
    return principal * monthly_rate * factor / (factor - 1)


def assess(row):
    income = float(row["monthly_income"])
    if income <= 0:
        return {
            "emi": 0.0,
            "foir": 100.0,
            "findings": ["Monthly income is missing or not positive; manual review required."],
            "risks": [],
            "recommendation": "MANUAL REVIEW",
        }

    emi = calculate_emi(row["loan_amount"], row["annual_interest_rate"], row["tenure_months"])
    foir = (float(row["existing_emi"]) + emi) / income * 100
    findings = []
    risks = []

    if not bool(row["documents_complete"]):
        findings.append("Required documents are incomplete.")
    if not bool(row["identity_verified"]):
        findings.append("Identity verification is unresolved.")
    if int(row["credit_score"]) < DEMO_POLICY["minimum_credit_score"]:
        risks.append("Credit score is below the demo threshold.")
    if foir > DEMO_POLICY["maximum_foir_percent"]:
        risks.append("FOIR exceeds the demo threshold.")
    if bool(row["overdue_flag"]):
        risks.append("Simulated overdue flag detected.")

    if findings:
        recommendation = "MANUAL REVIEW"
    elif risks:
        recommendation = "REFER FOR CREDIT REVIEW"
    else:
        recommendation = "RECOMMEND APPROVAL"

    return {
        "emi": round(emi, 2),
        "foir": round(foir, 2),
        "findings": findings,
        "risks": risks,
        "recommendation": recommendation,
    }


st.sidebar.header("Navigation")
page = st.sidebar.radio(
    "Select page",
    ["Loan Dashboard", "Approach Story", "Architecture", "About / FAQ"],
)

if page == "Loan Dashboard":
    st.subheader("Loan Operations Dashboard")
    st.dataframe(applicants, use_container_width=True)

    selected_id = st.selectbox("Select application", applicants["application_id"].astype(str))
    row = applicants.loc[applicants["application_id"].astype(str) == selected_id].iloc[0]
    result = assess(row)

    c1, c2, c3 = st.columns(3)
    c1.metric("Monthly income", f"₹{float(row['monthly_income']):,.0f}")
    c2.metric("Proposed EMI", f"₹{result['emi']:,.0f}")
    c3.metric("FOIR", f"{result['foir']:.1f}%")

    st.subheader("Applicant profile")
    st.write({
        "Application ID": str(row["application_id"]),
        "Applicant": str(row["name"]),
        "Loan amount": f"₹{float(row['loan_amount']):,.0f}",
        "Tenure": f"{int(row['tenure_months'])} months",
        "Simulated credit score": int(row["credit_score"]),
    })

    st.subheader("Agent activity")
    st.write("1. Document Intelligence Agent: checked simulated document status.")
    st.write("2. Verification and Policy Agent: checked simulated identity and bureau results.")
    st.write("3. Credit Assessment Agent: calculated EMI and FOIR.")

    st.subheader("Recommendation")
    st.info(result["recommendation"])
    if result["findings"]:
        st.warning("Pending checks: " + " ".join(result["findings"]))
    if result["risks"]:
        st.warning("Risk flags: " + " ".join(result["risks"]))

    st.caption(
        "Illustrative rules only. External checks are simulated. "
        "A credit officer must make the actual decision; this demo does not sanction or disburse loans."
    )
    st.subheader("Credit officer review")
    officer_action = st.selectbox(
        "Record review outcome",
        ["Pending", "Approve", "Reject", "Request more information"],
    )
    review_reason = st.text_area("Review comments / reason")
    if st.button("Record review"):
        if officer_action == "Pending":
            st.warning("Choose a review outcome before recording.")
        elif not review_reason.strip():
            st.warning("Enter a reason for the review decision.")
        else:
            st.success(
                f"Demo review recorded: {officer_action}. "
                "This decision is displayed for this session only; it is not persisted to BigQuery."
            )
            st.write("Reason:", review_reason)

elif page == "Approach Story":
    st.header("From fragmented data to informed decisions")
    st.subheader("Act 1 — Build a unified data foundation")
    st.write(
        "Applicant profiles, loan terms and simulated verification outcomes are unified in BigQuery. "
        "The Streamlit app reads the loan_master_data table for this prototype."
    )
    st.subheader("Act 2 — Apply AI-assisted workflows")
    st.write(
        "Rule-based document checks and affordability calculations produce findings and a recommendation. "
        "These are simulated agent steps, not a production AI underwriting system. A credit officer retains authority."
    )

elif page == "Architecture":
    st.header("Solution Architecture")
    st.code("""
Synthetic applicant + loan + verification data
                    |
                    v
      BigQuery: loan_demo.loan_master_data
                    |
                    v
  Streamlit app / data validation / EMI + FOIR
                    |
                    v
    Risk flags + explainable recommendation
                    |
                    v
          Credit officer review

Governance: service-account access controls, policy thresholds,
manual review and explicit demo-only decision handling.
    """)
    st.caption(
        "BigQuery is connected as this prototype's data source. External bureau/document APIs, "
        "durable audit logging, and real loan decisions are not implemented."
    )

else:
    st.header("About LoanPilot AI")
    st.write("A fictional demo of AI-assisted personal loan assessment for salaried applicants.")
    st.subheader("Frequently asked questions")
    st.write("Are the applicants real? No, all applicants are fictional demo records.")
    st.write("Is CIBIL connected? No, credit bureau results are simulated.")
    st.write("Does AI approve loans? No, an authorized credit officer must make the actual decision.")
