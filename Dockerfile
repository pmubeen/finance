# Use an official Python runtime as a parent image
FROM python:3.11-slim-buster

# Set the working directory in the container to /app
WORKDIR /app

# Copy the application files into the container
COPY . .

# Install production dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables (if needed)
# If you have environment variables in .env.prod, you can load them here
# Example:
# ENV ALPHA_VANTAGE_API_KEY=your_alpha_vantage_api_key
# ENV FMP_API_KEY=your_fmp_api_key

# Expose the port that Flask listens on (default is 5000, but you can change it)
EXPOSE 8000

# Set the command to run the application using Gunicorn
CMD gunicorn --bind 0.0.0.0:8000 --timeout 120 app:app