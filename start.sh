#!/bin/bash
echo "🚀 [start.sh] Ensuring kgisuperpy is installed..."
pip install kgisuperpy==2.0.3

echo "🚀 [start.sh] Starting background worker for trading strategy..."
python src/main.py &

echo "🚀 [start.sh] Starting foreground web server (Streamlit)..."
# The exec command is used so that streamlit handles OS signals properly
exec streamlit run app.py --server.port ${PORT:-8080} --server.address 0.0.0.0 --server.headless true --server.enableCORS false
