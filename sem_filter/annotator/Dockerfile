FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir flask==3.0.3

COPY app.py .
COPY static ./static

ENV DATA=/data/100_sample.jsonl
EXPOSE 8000

CMD ["python", "app.py"]
