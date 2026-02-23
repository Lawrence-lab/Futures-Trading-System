#!/bin/bash
# Start the background worker
python src/main.py &

# Start the foreground web server
# The exec command is used so that streamlit handles OS signals properly
exec streamlit run app.py --server.port ${PORT:-8080} --server.address 0.0.0.0 --server.headless true --server.enableCORS false
