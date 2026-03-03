#!/bin/bash
set -e

# Colors for terminal output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================================${NC}"
echo -e "${BLUE}         Platform VANGUARD - Bootstrap Sequence       ${NC}"
echo -e "${BLUE}======================================================${NC}"

# 1. Environment Verification
if ! command -v docker &> /dev/null; then
    echo -e "${RED}[!] Docker is not installed or not in PATH. Please install Docker.${NC}"
    exit 1
fi
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[!] Python3 is required. Please install Python3.${NC}"
    exit 1
fi

# 2. Virtual Environment Setup
echo -e "${YELLOW}[*] Validating Python Virtual Environment...${NC}"
if [ ! -d "venv" ]; then
    echo -e "  [+] Creating virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate
echo -e "  [+] Installing dependencies..."
pip install -r requirements.txt > /dev/null 2>&1

# 3. ELK SIEM Stack Initialization
echo -e "\n${YELLOW}[*] Initializing Vanguard SIEM (Elasticsearch & Kibana)...${NC}"
if ! docker ps | grep -q 'elastic-vanguard'; then
    echo -e "  [+] Starting Elasticsearch container..."
    docker run -d --name elastic-vanguard \
        -p 9200:9200 \
        -e "discovery.type=single-node" \
        -e "xpack.security.enabled=false" \
        docker.elastic.co/elasticsearch/elasticsearch:8.10.2 > /dev/null
else
    echo -e "  [+] Elasticsearch is already running."
fi

if ! docker ps | grep -q 'kibana-vanguard'; then
    echo -e "  [+] Starting Kibana container..."
    docker run -d --name kibana-vanguard \
        --link elastic-vanguard:elasticsearch \
        -p 5601:5601 \
        -e "xpack.encryptedSavedObjects.encryptionKey=min_32_byte_long_encryption_key_vanguard" \
        -e "ELASTICSEARCH_URL=http://elasticsearch:9200" \
        -e "ELASTICSEARCH_HOSTS=http://elasticsearch:9200" \
        docker.elastic.co/kibana/kibana:8.10.2 > /dev/null
else
    echo -e "  [+] Kibana is already running."
fi

# 4. Kibana SOC Dashboard Provisioning
echo -e "\n${YELLOW}[*] Provisioning Kibana SOC Dashboards...${NC}"
python3 setup_kibana_dashboard.py || {
    echo -e "${RED}[!] Failed to provision Kibana Dashboards. Ensure containers are up.${NC}"
}

# 5. FastAPI Backend Orchestrator
echo -e "\n${YELLOW}[*] Booting VANGUARD Autonomous Orchestrator...${NC}"
echo -e "  [+] Initializing uvicorn server in the background..."
# Kill any existing uvicorn instances to prevent port collisions
pkill -f "uvicorn backend.main:app" || true
nohup uvicorn backend.main:app --reload > vanguard_backend.log 2>&1 &
BACKEND_PID=$!
sleep 3

if ps -p $BACKEND_PID > /dev/null; then
    echo -e "${GREEN}  [+] Backend Orchestrator running on http://127.0.0.1:8000${NC}"
else
    echo -e "${RED}[!] Backend Server failed to start. Check vanguard_backend.log.${NC}"
    exit 1
fi

echo -e "\n${GREEN}======================================================${NC}"
echo -e "${GREEN}  VANGUARD DEPLOYMENT COMPLETE                        ${NC}"
echo -e "${GREEN}======================================================${NC}"
echo -e "${BLUE}1. Frontend App:${NC} Open ${YELLOW}file://$(pwd)/palantir_clone.html${NC} in your browser."
echo -e "${BLUE}2. Kibana SOC:${NC} Open ${YELLOW}http://localhost:5601/app/dashboards#/view/vanguard-soc-dashboard${NC}"
echo -e "${BLUE}3. Deep Attack Trace:${NC} To run an unconstrained raw payload test bypassing UI, execute:"
echo -e "   ${YELLOW}  python3 run_attack.py${NC}"
echo -e "${GREEN}======================================================${NC}"
echo -e "To shutdown the backend cleanly, run: ${YELLOW}kill $BACKEND_PID${NC}"
