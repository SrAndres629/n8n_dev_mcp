# n8n Architect - Quantum Core MCP

A Senior-Grade Master Control Process (MCP) for n8n and Docker orchestration, designed for high-fidelity agentic autonomous development.

## 🚀 Architecture: Expert Kernels

The system has been refactored from a flat 94-tool model to **10 High-Fidelity Expert Kernels**. This reduces agent cognitive load while maintaining 100% of the underlying power.

### Available Kernels
1.  **`kernel_workflow_architect`**: Full workflow lifecycle (Deploy, Snapshots, Git).
2.  **`kernel_operational_surgeon`**: Live state manipulation & auto-healing.
3.  **`kernel_system_oracle`**: Predictive metrics, anomalies & reliability grades.
4.  **`kernel_infrastructure_guardian`**: Docker, security & resource optimization.
5.  **`kernel_semantic_intelligence`**: Documentation, diagrams & impact analysis.
6.  **`kernel_asset_factory`**: Custom node scaffolding & credentials.
7.  **`list_expert_skills`**: Dynamic discovery of 85+ underlying skills.

### Strategic Protocols
- **`system_war_room_report`**: Strategic system overview.
- **`protocol_execute_sdlc`**: Automated Audit/Security/Optimization loop.
- **`shadow_simulation_patch`**: Risk-free fix simulation.

## 🛠️ Setup & Usage

### 1. Requirements
- Python 3.10+
- n8n instance with API enabled
- Docker Desktop (local)

### 2. Environment Configuration
Create a `.env` file with:
```env
N8N_BASE_URL=http://localhost:5678
N8N_API_KEY=your_api_key
ENABLE_DOCKER_TOOLS=True
ENABLE_N8N_TOOLS=True
```

### 3. Launching
```bash
# Production (SSE via FastAPI)
python run.py

# CLI / Debug Mode
python run_stdio.py
```

### 4. Verification
Run the unified verification suite:
```bash
python verify_system.py
```

## 🧠 Design Philosophy
Built on the **"Jorge Aguirre" Protocol**, prioritizing Robustness, Security, and Clean-Code through iterative AUDIT phases before any production deployment.
