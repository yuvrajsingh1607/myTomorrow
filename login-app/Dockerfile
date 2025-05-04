# Use a lightweight Python image as the base
FROM python:3.9-slim

# Set environment variables to prevent Python from writing .pyc files and to ensure output is logged
ENV PYTHONUNBUFFERED=1

# Set the working directory inside the container
WORKDIR /app

# Copy the application files into the container
COPY . /app/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port that Flask will run on
EXPOSE 5000

# Set the command to run the Flask app
CMD ["python", "app.py"]
