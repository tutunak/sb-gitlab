# Use an official Python runtime as a parent image
FROM python:3.13-slim

# Install git
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the script into the container at /app
COPY sbg.py .

# Make the script executable
RUN chmod +x sbg.py

# Set the entrypoint to run the script
ENTRYPOINT ["./sbg.py"]
