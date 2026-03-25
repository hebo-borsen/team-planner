FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for numpy and other packages
RUN apt-get update && apt upgrade -y

COPY requirements.txt .
RUN pip3 install -r requirements.txt

COPY app.py .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.address", "0.0.0.0"]
