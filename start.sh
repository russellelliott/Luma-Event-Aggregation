#!/bin/bash

# Luma Event Aggregation - Complete startup script
# This script:
# 1. Creates a backup of the LanceDB table
# 2. Runs the backend pipeline
# 3. Starts the backend server
# 4. Starts the frontend development server

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BACKEND_PORT=8001
FRONTEND_PORT=3001
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}🚀 Luma Event Aggregation Startup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

echo -e "Please select a startup mode:"
echo -e "  ${GREEN}1)${NC} Start App Only (Skip pipeline & backup)"
echo -e "  ${GREEN}2)${NC} Run Full Pipeline (Backup -> Pipeline -> Start App)"
echo ""
read -p "Enter option (1 or 2): " USER_OPTION
echo ""

if [ "$USER_OPTION" == "2" ]; then
    # Step 1: Backup LanceDB table
    echo -e "${YELLOW}Step 1: Creating LanceDB backup...${NC}"
    cd "$BACKEND_DIR"

    if [ -f "backup_db.py" ]; then
        python3 backup_db.py
    else
        echo -e "${RED}❌ backup_db.py not found in backend directory.${NC}"
        exit 1
    fi

    if [ $? -ne 0 ]; then
        echo -e "${RED}Backup failed. Exiting.${NC}"
        exit 1
    fi
    echo ""

    # Step 2: Run the backend pipeline
    echo -e "${YELLOW}Step 2: Running backend pipeline...${NC}"
    if [ -f "$BACKEND_DIR/run_pipeline.sh" ]; then
        bash "$BACKEND_DIR/run_pipeline.sh"
        if [ $? -ne 0 ]; then
            echo -e "${RED}Pipeline failed. Exiting.${NC}"
            exit 1
        fi
        echo -e "${GREEN}✅ Pipeline completed successfully!${NC}"
    else
        echo -e "${RED}❌ run_pipeline.sh not found in backend directory.${NC}"
        exit 1
    fi
    echo ""
else
    echo -e "${YELLOW}Skipping pipeline and backup...${NC}"
fi


# Step 3: Start the backend server
echo -e "${YELLOW}Step 3: Starting backend server on port ${BACKEND_PORT}...${NC}"
cd "$BACKEND_DIR"
python3 -m uvicorn main:app --host 0.0.0.0 --port $BACKEND_PORT &
BACKEND_PID=$!
echo -e "${GREEN}✅ Backend started (PID: $BACKEND_PID)${NC}"
sleep 2
echo ""

# Step 4: Start the frontend development server
echo -e "${YELLOW}Step 4: Starting frontend server on port ${FRONTEND_PORT}...${NC}"
cd "$FRONTEND_DIR"
PORT=$FRONTEND_PORT npm start &
FRONTEND_PID=$!
echo -e "${GREEN}✅ Frontend started (PID: $FRONTEND_PID)${NC}"
sleep 2
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}🎉 All services started successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Backend:  http://localhost:${BACKEND_PORT}${NC}"
echo -e "${BLUE}Frontend: http://localhost:${FRONTEND_PORT}${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Wait for all background processes
wait
