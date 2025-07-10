import streamlit as st
import pandas as pd
import torch
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sentence_transformers import SentenceTransformer, util

# Load dataset
df = pd.read_csv("mock_startup_leads.csv")

# Calculate lead score
def calculate_score(row):
    score = 0
    if row['Hiring'] == 'Yes':
        score += 3
    if row['Funding Stage'] in ['Series A', 'Series B']:
        score += 5
    if row['Funding Amount'] in ['$1M', '$5M', '$10M', '$50M']:
        score += 5
    if any(loc in row['Location'] for loc in ['San Francisco', 'New York', 'London']):
        score += 2
    return score

df['Lead Score'] = df.apply(calculate_score, axis=1)

# Parse funding to numeric (millions)
def parse_funding(val):
    if not isinstance(val, str):
        return 0
    val = val.replace("$", "").upper()
    if "M" in val:
        return float(val.replace("M", ""))
    elif "K" in val:
        return float(val.replace("K", "")) / 1000
    return 0

df["FundingNum"] = df["Funding Amount"].apply(parse_funding)

# Build semantic context
df["Context"] = df.apply(lambda row: (
    f"{row['Company Name']} is located in {row['Location']}, "
    f"has raised {row['Funding Amount']} funding in the {row['Funding Stage']} stage. "
    f"They use {row['Tech Stack']} and are currently {'hiring' if row['Hiring'] == 'Yes' else 'not hiring'}."
), axis=1)

# Load transformer model
model = SentenceTransformer("all-MiniLM-L6-v2")
corpus_embeddings = model.encode(df["Context"].tolist(), convert_to_tensor=True)

# Sidebar
st.sidebar.title("📌 Navigation")
page = st.sidebar.radio("Go to:", ["🏠 Dashboard", "💬 Chat with Data", "📄 View CSV", "📨 Send Collaboration Email", "📞 Contact Us"])

# Styling
st.markdown("""
<style>
/* App background and text */
.stApp {
    background: linear-gradient(to right, #141E30, #243B55);
    color: white;
    font-family: 'Segoe UI', sans-serif;
}

/* Metric cards */
[data-testid="metric-container"] {
    background: rgba(255, 255, 255, 0.08);
    border-radius: 15px;
    padding: 15px;
    margin: 10px 0;
    text-align: center;
    box-shadow: 0 0 15px rgba(0,0,0,0.2);
}

/* Buttons */
.stButton>button {
    color: white;
    background: linear-gradient(90deg, #00C9FF, #92FE9D);
    border: none;
    border-radius: 10px;
    padding: 0.6rem 1.4rem;
    font-weight: bold;
    transition: 0.3s ease-in-out;
}
.stButton>button:hover {
    transform: scale(1.05);
    box-shadow: 0 0 15px #00C9FF;
}

/* Text inputs */
input, textarea {
    background-color: #1e293b !important;
    color: white !important;
    border: 1px solid #4f46e5 !important;
    border-radius: 8px !important;
}

/* Sidebar */
.css-1d391kg, .css-1cpxqw2 {
    background: #0f172a;
}

/* Section headers */
h1, h2, h3 {
    color: #f8fafc;
    font-weight: 700;
    margin-top: 20px;
}

/* Markdown text */
.markdown-text-container {
    font-size: 1rem;
    line-height: 1.6;
    color: #e2e8f0;
}
<div style="text-align:center;">
    <h2 style='color:#00ffff;'>🚀 LeadGen Pro</h2>
    <hr style="border: 1px solid #00ffff;">
</div>
</style>
""", unsafe_allow_html=True)


# ========== Dashboard ==========
if page == "🏠 Dashboard":
    st.title("✨ LeadGen Pro Dashboard")
    st.subheader("📊 Lead Summary")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Leads", len(df))
    col2.metric("Hiring Leads", len(df[df["Hiring"] == "Yes"]))
    col3.metric("Avg Lead Score", round(df["Lead Score"].mean(), 2))

    st.subheader("🔎 Filter Leads")
    with st.expander("Click to Filter by Attributes"):
        location = st.multiselect("🌍 Filter by Location", options=df["Location"].unique())
        funding = st.multiselect("💰 Funding Stage", options=df["Funding Stage"].unique())
        hiring = st.radio("🧑‍💼 Hiring?", ["All", "Yes", "No"])
        tech = st.text_input("🔧 Search by Tech Stack")

    filtered_df = df.copy()
    if location:
        filtered_df = filtered_df[filtered_df["Location"].isin(location)]
    if funding:
        filtered_df = filtered_df[filtered_df["Funding Stage"].isin(funding)]
    if hiring != "All":
        filtered_df = filtered_df[filtered_df["Hiring"] == hiring]
    if tech:
        filtered_df = filtered_df[filtered_df["Tech Stack"].str.contains(tech, case=False, na=False)]

    st.subheader("📋 Leads Table")
    st.dataframe(filtered_df[["Company Name", "Location", "Funding Stage", "Funding Amount", "Tech Stack", "Hiring", "Lead Score"]])

    st.download_button("⬇️ Download Filtered CSV", filtered_df.to_csv(index=False), "filtered_leads.csv")

    st.subheader("📧 Cold Email Generator (Top Lead)")
    if not filtered_df.empty:
        lead = filtered_df.iloc[0]
        email = f"""
Hi {lead['Founder Name']},

I came across {lead['Company Name']} and was impressed by your work in the {lead['Tech Stack']} space.  
If you're looking to accelerate growth or explore automation tools, I’d love to connect.

Best,  
[Your Name]
"""
        st.code(email, language="markdown")
    else:
        st.info("No leads found for selected filters.")

# ========== Chat with Data ==========
elif page == "💬 Chat with Data":
    st.title("💬 Chat with Your Startup Data")
    query = st.text_input("🔍 Ask anything about the companies...")

    if query:
        response_generated = False

        match = re.search(r"more than \$?(\d+)([MK]?)", query.lower())
        if match:
            value = float(match.group(1))
            unit = match.group(2).upper()
            if unit == "K":
                value = value / 1000
            elif unit == "M":
                value = value

            result_df = df[df["FundingNum"] > value]
            if not result_df.empty:
                st.subheader(f"💰 Companies with funding > ${value}M:")
                for _, row in result_df.iterrows():
                    st.markdown(f"""
**🏢 Company Name:** {row['Company Name']}  
📍 **Location:** {row['Location']}  
💰 **Funding:** {row['Funding Amount']} ({row['Funding Stage']})  
🧠 **Tech Stack:** {row['Tech Stack']}  
🧑‍💼 **Hiring:** {row['Hiring']}  
📈 **Lead Score:** {row['Lead Score']}  
""")
            else:
                st.info("❌ No companies found with funding above that amount.")
            response_generated = True

        if not response_generated:
            query_embedding = model.encode(query, convert_to_tensor=True)
            scores = util.pytorch_cos_sim(query_embedding, corpus_embeddings)[0]
            top_k = 10
            top_results = torch.topk(scores, k=top_k)

            st.subheader("🔍 Top Matches")
            for score, idx in zip(top_results.values, top_results.indices):
                row = df.iloc[int(idx)]
                sim_score = score.item()
                st.markdown(f"""
**🏢 Company Name:** {row['Company Name']}  
📍 **Location:** {row['Location']}  
💰 **Funding:** {row['Funding Amount']} ({row['Funding Stage']})  
🧠 **Tech Stack:** {row['Tech Stack']}  
🧑‍💼 **Hiring:** {row['Hiring']}  
📈 **Lead Score:** {row['Lead Score']}  
🔍 **Match Score:** {sim_score:.2f}
""")

# ========== View CSV ==========
elif page == "📄 View CSV":
    st.title("📄 All Startup Leads")
    st.dataframe(df)

# ========== Send Email ==========
# ========== Send Email ==========
elif page == "📨 Send Collaboration Email":
    st.title("📨 Send Collaboration Email")

    company_name = st.text_input("Enter Company Name")
    your_name = st.text_input("Your Name")
    your_email = st.text_input("Your Email Address")
    your_password = st.text_input("Your Email Password / App Password", type="password")

    st.markdown("Choose your email type:")
    col1, col2 = st.columns(2)
    send_default = col1.button("✅ Send Default Message")
    send_custom = col2.button("📝 Send Custom Message")

    if send_custom:
        custom_message = st.text_area("✍️ Write your custom message")

    if send_default or (send_custom and custom_message):
        row = df[df["Company Name"].str.lower() == company_name.strip().lower()]
        if not row.empty:
            row = row.iloc[0]
            receiver_email = row["Email"]  # Ensure 'Email' column exists

            subject = f"Collaboration Opportunity with {row['Company Name']}"

            if send_default:
                message = f"""
Hi {row['Founder Name']},

I'm reaching out to explore potential collaboration opportunities between our teams.  
{row['Company Name']}'s innovation in the {row['Tech Stack']} domain is inspiring, and I believe we can create meaningful synergy.

Let's connect and discuss how we can support each other’s goals.

Looking forward to hearing from you,  
{your_name}
"""
            else:
                message = f"""
Hi {row['Founder Name']},

{custom_message}

Looking forward to hearing from you,  
{your_name}
"""

            # SMTP setup
            msg = MIMEMultipart()
            msg['From'] = your_email
            msg['To'] = receiver_email
            msg['Subject'] = subject
            msg.attach(MIMEText(message, 'plain'))

            try:
                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.starttls()
                server.login(your_email, your_password)
                server.send_message(msg)
                server.quit()
                st.success(f"✅ Email sent to {receiver_email}")
            except Exception as e:
                st.error(f"❌ Failed to send email: {e}")
        else:
            st.warning("⚠️ Company not found. Please check the name.")
    elif send_custom and not custom_message:
        st.warning("✍️ Please write a custom message before sending.")

            
# ========== Contact Us ==========
elif page == "📞 Contact Us":
    st.title("📞 Contact Us")

    st.markdown("""
    We’d love to hear from you!  
    If you have any suggestions, feedback, or partnership inquiries, feel free to reach out.

    **📧 Email:** yourname@example.com  
    **🔗 LinkedIn:** [Your LinkedIn](https://www.linkedin.com/in/yourprofile)  
    **💼 GitHub:** [Your GitHub](https://github.com/yourusername)
    """, unsafe_allow_html=True)

    st.subheader("💬 Send a Message")
    contact_name = st.text_input("Your Name")
    contact_email = st.text_input("Your Email")
    contact_message = st.text_area("Your Message")

    if st.button("Submit"):
        if contact_name and contact_email and contact_message:
            # Optionally save to CSV or database
            st.success("✅ Thank you for contacting us! We'll get back to you soon.")
            # Optionally, send email to you using smtplib (you can reuse the same method)
        else:
            st.warning("Please fill out all fields.")