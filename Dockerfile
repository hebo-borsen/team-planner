FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY db.py .
COPY migrate.py .
COPY migrations/ ./migrations/
COPY templates/ ./templates/

EXPOSE 5000

ENV FLASK_APP=app.py

CMD ["sh", "-c", "if [ \"$FLASK_DEBUG\" = '1' ]; then python -m flask run --host=0.0.0.0 --port=5000 --reload --debugger; else gunicorn --bind 0.0.0.0:5000 --workers 2 --reload app:app; fi"]
