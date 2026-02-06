Write-Host "Running Black Code Formatter..."
black src tests

Write-Host "Running Pylint..."
pylint src

Write-Host "Running Pytest..."
pytest tests

Write-Host "QA Check Complete."
