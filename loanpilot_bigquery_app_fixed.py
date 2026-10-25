import streamlit as st
import pandas as pd
from google.cloud import bigquery

# Demo policy used by Agent 2 (Verification and Policy)
DEMO_POLICY = {
    "minimum_credit_score": 700,
    "maximum_foir_percent": 40
}

st.set_page_config(
    page_title="LoanPilot AI",
    page_icon="🏦",
    layout="wide"
)

st.title("LoanPilot AI")
st.caption(
    "AI-assisted personal loan assessment | "
    "Fictional data and simulated checks"
)


# Load applicant data from BigQuery
PROJECT_ID = "loanapp-0911"
TABLE_ID = "loanapp-0911.loan_demo.loan_master_data"

@st.cache_data(ttl=60)
def load_loan_data():
    client = bigquery.Client(project=PROJECT_ID)

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

    return client.query(query).to_dataframe()

try:
    applicants = load_loan_data()
except Exception as exc:
    st.error("Could not load loan applications from BigQuery.")
    st.info(
        "Check that google-cloud-bigquery is installed, the deployed app "
        "has Google Cloud credentials configured, and its identity can run "
        "BigQuery jobs and read the loan_demo dataset."
    )
    st.exception(exc)
    st.stop()

if applicants.empty:
    st.warning("No loan applications were found in BigQuery.")
    st.stop()

st.success(
    f"Loaded {len(applicants)} loan applications from BigQuery."
)




st.dataframe(applicants, use_container_width=True)

def calculate_emi(principal, annual_rate, months):
    r = annual_rate / 1200
    if principal <= 0 or months <= 0:
        raise ValueError("Principal and tenure must be positive.")
    if r == 0:
        return principal / months
    return principal * r * (1 + r)**months / ((1 + r)**months - 1)

def assess(row):
    emi = calculate_emi(
        row["loan_amount"],
        row["annual_interest_rate"],
        row["tenure_months"]
    )
    foir = (row["existing_emi"] + emi) / row["monthly_income"] * 100

    findings = []
    risks = []

    if not row["documents_complete"]:
        findings.append("Required documents are incomplete.")

    if not row["identity_verified"]:
        findings.append("Identity verification is unresolved.")

    if row["credit_score"] < 700:
        risks.append("Credit score is below the demo threshold.")

    if foir > 40:
        risks.append("FOIR exceeds the demo threshold.")

    if row["overdue_flag"]:
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
        "recommendation": recommendation
    }

st.sidebar.header("Navigation")
page = st.sidebar.radio(
    "Select page",
    ["Loan Dashboard", "Approach Story", "Architecture", "About / FAQ"]
)

if page == "Loan Dashboard":
    st.subheader("Loan Operations Dashboard")

    selected_id = st.selectbox(
        "Select application",
        applicants["application_id"]
    )

    row = applicants.loc[
        applicants["application_id"] == selected_id
    ].iloc[0]

    result = assess(row)

    c1, c2, c3 = st.columns(3)
    c1.metric("Monthly income", f"₹{row['monthly_income']:,.0f}")
    c2.metric("Proposed EMI", f"₹{result['emi']:,.0f}")
    c3.metric("FOIR", f"{result['foir']:.1f}%")

    st.subheader("Applicant profile")
    st.write({
        "Application ID": row["application_id"],
        "Applicant": row["name"],
        "Loan amount": f"₹{row['loan_amount']:,.0f}",
        "Tenure": f"{row['tenure_months']} months",
        "Simulated credit score": row["credit_score"]
    })

    st.subheader("Agent activity")
    st.write("1. Document Intelligence Agent: checked document status.")
    st.write("2. Verification and Policy Agent: checked simulated identity and bureau results.")
    st.write("3. Credit Assessment Agent: calculated EMI and FOIR.")

    st.subheader("Recommendation")
    st.info(result["recommendation"])

    if result["findings"]:
        st.warning("Pending checks: " + " ".join(result["findings"]))

    if result["risks"]:
        st.warning("Risk flags: " + " ".join(result["risks"]))

    st.caption(
        "Illustrative rules only. All external checks are simulated. "
        "A credit officer must make the actual decision."
    )

    st.subheader("Credit officer review")
    officer_action = st.selectbox(
        "Record review outcome",
        ["Pending", "Approve", "Reject", "Request more information"]
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
                "This does not execute a real sanction or disbursement."
            )
            st.write("Reason:", review_reason)

elif page == "Approach Story":
    st.header("From fragmented data to informed decisions")

    st.subheader("Act 1 — Build a unified data foundation")
    st.write(
        "Bring customer records, loan history, policy documents "
        "and simulated external verification responses together. "
        "BigQuery provides the analytical data layer for this prototype."
    )

    st.subheader("Act 2 — Apply AI-assisted workflows")
    st.write(
        "Document checks, policy lookup and affordability calculations "
        "produce findings and a recommendation with reasons. "
        "A credit officer retains decision authority."
    )

elif page == "Architecture":
    st.header("Solution Architecture")

    st.code("""
Customer applications / PDFs / Core banking / Mock APIs
                         |
                         v
                Data ingestion layer
                         |
                         v
             BigQuery analytical data layer
                         |
                         v
       Document -> Verification -> Credit assessment
                         |
                         v
               Streamlit application
                         |
                         v
              Credit officer review

Governance: access controls, policy versioning, audit logs,
data quality, explainability and human oversight.
    """)

    st.caption(
        "BigQuery is connected as the prototype's data source. "
        "Production integrations, automated audit logging, and real "
        "external verification services are not implemented."
    )

else:
    st.header("About LoanPilot AI")
    st.write(
        "A fictional point-of-view demo of AI-assisted personal "
        "loan assessment for salaried applicants."
    )
    st.subheader("Frequently asked questions")
    st.write("Are the applicants real? No, all applicants are fictional.")
    st.write("Is CIBIL connected? No, bureau results are simulated.")
    st.write("Does AI approve loans? No, an authorized credit officer "
             "must make the actual decision.")
