<div align="center">

# 🛡️ VANGUARD
**A Cognitive Purple Agent Framework for Autonomous Adversarial Simulation and Real-Time SIEM Validation**

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18846075.svg)](https://doi.org/10.5281/zenodo.18846075)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-brightgreen.svg)](https://www.python.org/downloads/release/python-3100/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com/)
[![React Edge](https://img.shields.io/badge/Architecture-ReAct_LLM-purple.svg)](https://arxiv.org/abs/2210.03629)

> **"VANGUARD transforms Breach and Attack Simulation (BAS) from static, deterministic playbooks into a dynamic, mathematically validated Cyber Wargaming arena."**
> 
> *Read the full academic preprint:* [10.5281/zenodo.18846075](https://doi.org/10.5281/zenodo.18846075)

</div>

---

## ⚡ Overview & Vision

The rapid evolution of Advanced Persistent Threats (APTs) severely outpaces the scaling capabilities of static Security Operations Centers (SOCs). Conventional penetration testing and "dumb" replay engines execute known Indicators of Compromise (IoCs) but fail to emulate the adaptive, lateral reasoning of a human threat actor. 

**VANGUARD** is an open-source, mathematically grounded framework that introduces the **Cognitive Purple Agent**. Engineered for **PhD Researchers, Defense Contractors, and Enterprise SecOps**, VANGUARD solves two critical paradigms in offensive AI:

1. **The "Black Box" Validation Gap:** VANGUARD doesn't just attack; it streams its kill-chain telemetry ($t_{attack}$) to a local Elasticsearch/Kibana SIEM to compute its exact **Time-to-Detect (TTD)**. When it discovers a 0.0% SOC alert gap, the agent *reverses its ontology* and synthesizes real KQL defensive rules to actively patch the SIEM.
2. **The Agentic Alignment Problem:** Unconstrained LLMs cannot be trusted with generic shell access without risking CI/CD system death. VANGUARD pioneers the **FATAL_OS_BLOCKLIST**, granting the agent total operational autonomy recursively (e.g., dynamically resolving apt/brew target dependencies) while mathematically sandboxing destructive regex patterns.

<br>

<div align="center">
  <img
    src="https://github.com/user-attachments/assets/0bb86418-31e5-4dee-843e-f478c3ddb364"
    alt="Vanguard Dashboard UI"
    width="900"
  />
  <p><i>Figure 1: The Reactive Event-Ontology Dashboard rendering LLM cognitions in real-time.</i></p>
</div>

## 🏗️ Technical Architecture

VANGUARD operates a tripartite closed-loop interaction mapped over an asynchronous Server-Sent Events (SSE) stream, providing total cryptographic transparency into the AI's "brain."

<div align="center">
  <img
    src="https://github.com/user-attachments/assets/272a064c-5fdd-4be7-8bf3-6700c90f27f9"
    alt="Vanguard Architecture Flow Diagram"
    width="250"
  />
  <p><i>Figure 2: End-to-end autonomous pipeline - from LLM cognition loop through sandboxed execution, target exploitation, and dynamic SOC rule synthesis.</i></p>
</div>

## 🎯 Groundbreaking Capabilities

### 1. "Glass Box" SSE Transparency (The Live Stream)
Conventional LLMs operate opaquely. VANGUARD utilizes an asynchronous web-stream (SSE) allowing human operators to cryptographically observe the agent's real-time state transitions (`🧠 Cognitive Reason` → `⚡ Tool Executed` → `📤 Observation`) through a custom, Palantir-inspired UI. 

<div align="center">
  <video
    src="https://github.com/user-attachments/assets/d36af1c1-8d87-49fc-b4a2-20dfddfe37a5"
    autoplay
    muted
    loop
    playsinline
    controls
    width="900"
    title="VANGUARD Full Application Walkthrough">
  </video>
  <p><i>Figure 3: Full VANGUARD application walkthrough - SSE live-stream of agent state transitions across the Palantir-inspired UI.</i></p>
</div>

### 2. Autonomous DefSecOps (Dynamic Purple Teaming)
The framework does not merely highlight vulnerabilities—it acts as an autonomous DefSecOps engineer. Following a successful simulated breach, the LLM systematically structures its un-logged attack vectors into **Elasticsearch KQL Heuristics** and autonomously deploys them to the SIEM (`vanguard-rules`). Defensive parity natively scales with offensive automation.

<div align="center">
  <img
    src="https://github.com/user-attachments/assets/3db9af86-beb8-4b3c-8f2f-5fddf004ba0f"
    alt="Vanguard Autonomous KQL Rule Synthesis"
    width="900"
  />
  <p><i>Figure 4: Autonomous DefSecOps loop - LLM-structured attack vectors synthesized into Elasticsearch KQL heuristics and autonomously deployed to the <code>vanguard-rules</code> SIEM index.</i></p>
</div>



### 3. Multi-Vertical Attack Surfaces (Zero-Shot Capability)
VANGUARD ships with a standalone suite of vulnerable enterprise targets to validate Zero-Shot exploitation logic:
* `targets/cloud_storage.py`: Advanced IDOR, JSON Web Token (JWT) signature stripping via `alg: none`, and PDF Conversion Command Injection.
* `targets/vulnerable_app.py`: Generic corporative monolithic APIs leaking LFI and RCE vectors via Base64 serialization.
* `targets/legacy_erp.py`: Emulation of unpatched, critical internal architecture.

<div align="center">
  <img
    src="https://github.com/user-attachments/assets/e48e48f1-60d2-429f-84a9-167059abe742"
    alt="Vanguard Attack Chain Visualization"
    width="900"
  />
  <p><i>Figure 5: Real-time Attack Chain Visualization - the LLM's exploitation path rendered as a live directed graph across multi-vertical targets.</i></p>
</div>

---

## 🔭 The Evolution of Vanguard (Future Work)

For **Defense Contractors** and **Academic Research Groups (PhD)**, VANGUARD serves as the foundational architecture for the next decade of Cyber Warfare capabilities:

1. **Multi-Agent Wargaming (Swarm Logic):** Evolving from a single Purple node to a distributed swarm. "Red" LLM agents coordinating lateral movement across diverse VPC segments, while an entirely separate "Blue" LLM dynamically rewrites YARA/Zeek rules in real-time to intercept them.
2. **Reinforcement Learning from Human Feedback (RLHF):** Training proprietary defense-sector weights by having human elite Red Teamers grade the efficacy and stealth of VANGUARD's generated payloads.
3. **Air-Gapped Operationalization:** VANGUARD is purposely engineered to thrive entirely off-grid. By leveraging quantized edge-models (`Qwen 3 8B`) and completely cutting reliance on OpenAI/Anthropic APIs, the framework is mathematically cleared for deployment within partitioned hyper-secure enclaves.

---

## 🚀 Deployment & Installation

### Prerequisites
- macOS/Linux (Tested on Ubuntu 22.04 & macOS Sonoma)
- Python 3.10+
- [Ollama](https://ollama.com/) installed locally (Required models: `qwen3:8b` or `llama3`)
- [Docker](https://www.docker.com/) (For Elasticsearch/Kibana integration)

### 1. Zero-Touch Deployment
The repository includes an aggressive bootstrap script to stand up the frontend UI, the FastAPI backend, and the initial SQLite databases organically.

```bash
git clone https://github.com/usualdork/VANGUARD.git
cd VANGUARD
chmod +x run_demo.sh
./run_demo.sh
```

### 2. SIEM Telemetry Stack (Highly Recommended)
To enable the mathematically verifiable Gap Analysis and TTD visualization, spin up the local SIEM data pipeline:
```bash
# Start Elastic Stack in an isolated network
docker-compose up -d

# Push Vanguard Index Data Views directly to Kibana
python setup_kibana_dashboard.py
```

### 3. Initiate an Engagement
1. Access the VANGUARD Dashboard at `http://localhost:8080`
2. Start an enterprise target in an adjacent terminal: `python targets/cloud_storage.py` (Binds to `9997`)
3. Supply the Target URL into the UI Simulation pane and execute **INITIALIZE RUN**.
4. Observe the real-time AI Kill Chain generation and navigate to the **SOC Rules** tab to review the autonomously patched heuristics.

---

## 📚 Academic Citation & Impact

If you utilize VANGUARD or the FATAL_OS_BLOCKLIST methodology in your defense systems or academic research, please cite our preprint:

```bibtex
@article{tripathy2026vanguard,
  title={VANGUARD: A Cognitive Purple Agent Framework for Autonomous Adversarial Simulation and Real-Time SIEM Validation},
  author={Tripathy, Manish},
  year={2026},
  publisher={Zenodo},
  doi={10.5281/zenodo.18846075},
  url={https://doi.org/10.5281/zenodo.18846075}
}
```

## 📜 Notice
Distributed under the Apache 2.0 License. See `LICENSE` for more information.

> *WARNING: This framework utilizes live exploitation methodologies. Do not point VANGUARD at domains or IP addresses you do not explicitly own or have authorization to audit. The authors assume no liability for misuse.*
