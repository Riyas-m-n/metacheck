import streamlit as st
import pandas as pd
import csv
import os
import google.generativeai as genai
from pipeline import run_audit

st.set_page_config(page_title="MetaCheck | Triage Cockpit", layout="wide")
st.title("MetaCheck: Triage Cockpit & Curator Dashboard")
st.markdown("Automated semantic verification pipeline for live-service game guides.")

# Gemini Config
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    llm = genai.GenerativeModel('gemini-1.5-flash')
except Exception:
    llm = None

def generate_ai_summary(claim, rule):
    if not llm:
        return "Gemini API key not configured in Streamlit Secrets."
    try:
        prompt = f"The game patch note says: '{rule}'. The video guide claims: '{claim}'. In one short sentence, explain why the video's strategy is outdated."
        return llm.generate_content(prompt).text
    except Exception:
        return "AI Summary unavailable."

if "audit_results" not in st.session_state:
    st.session_state.audit_results = []

st.markdown("### 📈 Live Telemetry")
kpi_col1, kpi_col2, kpi_col3 = st.columns(3)

total_audits = len(st.session_state.audit_results)
rejected_audits = len([r for r in st.session_state.audit_results if r["Status"] == "REJECT"])
hours_saved = round((rejected_audits * 15) / 60, 1)
rejection_rate = round((rejected_audits / max(total_audits, 1)) * 100)

kpi_col1.metric("Videos Processed", total_audits)
kpi_col2.metric("Curator Hours Saved", f"{hours_saved} hrs")
kpi_col3.metric("Auto-Rejection Rate", f"{rejection_rate}%")
st.divider()

st.markdown("### 📥 Submit Video for Audit")
url = st.text_input("Enter YouTube Video URL:")

if st.button("Run Audit"):
    if url:
        try:
            # Handle both standard and shortened YouTube links
            if "youtu.be" in url:
                video_id = url.split("/")[-1].split("?")[0]
            else:
                video_id = url.split("v=")[-1].split("&")[0]
        except IndexError:
            st.error("Invalid YouTube URL format.")
            st.stop()

        with st.spinner("Executing API pipeline (Steam, Wiki, YouTube, Hugging Face)..."):
            result = run_audit(video_id)

            if result.get("status") == "ERROR":
                st.error(result["message"])
            else:
                st.session_state.audit_results.append({
                    "Video ID": video_id,
                    "Status": result["status"],
                    "Density %": f"{result['density']}%",
                    "Target Entity": result.get("targets_detected", "N/A"),
                    "Progression Gate": result.get("skill_metrics", {}).get("progression_tier", "N/A"),
                    "Violations": len(result.get("violations", []))
                })

                col1, col2, col3 = st.columns(3)
                with col1:
                    if result["status"] == "VERIFIED":
                        st.success("🟢 VERIFIED: Compliant with Current Patch")
                    else:
                        st.error("🔴 REJECT: Outdated Mechanics Detected")
                with col2:
                    st.metric("Information Density", f"{result['density']}%")
                with col3:
                    st.info(f"Active Target: {result.get('targets_detected', 'N/A')}")

                skill = result.get("skill_metrics", {})
                if skill:
                    st.markdown("#### ⚙️ Replication Feasibility (Skill Floor)")
                    s1, s2, s3 = st.columns(3)
                    s1.metric("Skill Floor Score", f"{skill.get('composite_score', 'N/A')}/100")
                    s2.metric("Progression Gate", skill.get("progression_tier", "N/A"))
                    s3.markdown(f"**Difficulty Tier:** {skill.get('difficulty_tag', 'N/A')}")
                    st.divider()

                violations = result.get("violations", [])
                if violations:
                    st.subheader("Semantic Contradictions Detected")
                    for v in violations:
                        with st.expander(f"Timestamp: [{v['timestamp']}s] | Confidence: {v['confidence']}%"):
                            ai_context = generate_ai_summary(v['claim'], v['rule'])
                            st.warning(f"**AI Context:** {ai_context}")
                            st.markdown(f"**Creator Claim:** *\"{v['claim']}\"*")
                            st.markdown(f"**Developer Rule:** *\"{v['rule']}\"*")
                            
                            btn_key = f"{video_id}_{v['timestamp']}"
                            if st.button(f"Flag as False Positive (Override {v['timestamp']}s)", key=btn_key):
                                file_exists = os.path.isfile("exceptions_log.csv")
                                with open("exceptions_log.csv", mode="a", newline="", encoding="utf-8") as f:
                                    writer = csv.writer(f)
                                    if not file_exists:
                                        writer.writerow(["Video_ID", "Timestamp", "Claim", "Rule", "Curator_Label"])
                                    writer.writerow([video_id, v["timestamp"], v["claim"], v["rule"], "True_Match"])
                                st.toast("Override permanently written to exceptions_log.csv.")
    else:
        st.warning("Please enter a valid YouTube URL.")

if st.session_state.audit_results:
    st.divider()
    st.markdown("### 📋 Verification Batch Queue")
    st.dataframe(pd.DataFrame(st.session_state.audit_results), use_container_width=True)