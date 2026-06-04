# AlphaHire

**Concept:** AI-native quant recruitment engine.  
Accepts a candidate pool, runs a fully autonomous 5-agent pipeline, and produces a complete hiring dossier — zero human input after trigger.

**Stack**
- Framework: CrewAI
- LLM: llama-3.2-3b-instruct via LM Studio
- Frontend: Streamlit
- Tunnel: Ngrok

**Agents**
| # | Agent | Task |
|---|---|---|
| 1 | JD Writer | Generates quant role job description |
| 2 | Screener | Scores and ranks candidates 0–100 |
| 3 | Scheduler | Books interview slots for shortlisted candidates |
| 4 | Onboarding Agent | Builds 30-day onboarding plan for top hire |
| 5 | Assessment Designer | Creates quant aptitude test with answer keys |

**Features**
- Secure login with session management
- Live candidate pool with add/remove CRUD
- Skill match chart — candidate skills vs role requirements
- Candidate score bar chart
- Interview invite email simulator with download
- Full dossier auto-saved to `outputs/` as markdown

**Run locally**
```bash
# Start LM Studio with llama-3.2-3b-instruct on port 1234
cd Week1
py -m streamlit run app.py --server.port 8501
```
