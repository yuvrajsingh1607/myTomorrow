# Uses a minimal Python 3.13 image based on Alpine Linux.
FROM python:3.13-alpine
# Sets the working directory to /app inside the container.
WORKDIR /app
# Copy the requirements.txt file into the container.
COPY requirements.txt .
# Install Python dependencies from requirements.txt
RUN pip install -r requirements.txt
# copy app.py into the container    
COPY app.py .
# Add a non-root user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
# Switch to non-root user
USER appuser
# run command "python app.py" when the container starts 
CMD ["python", "app.py"]