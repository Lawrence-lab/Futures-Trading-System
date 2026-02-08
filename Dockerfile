# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Make sure we don't copy .env or certs if they are in .dockerignore (though we rely on .gitignore usually, docker builds context includes everything unless ignored)
# Since .env and certs are sensitive, they might be mounted as volumes or secrets in Zeabur.
# For now, we assume the code structure is copied.

# Command to run on container start
# Command to run on container start
CMD ["python", "/app/src/main.py"]  
