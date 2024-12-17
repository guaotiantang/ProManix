FROM python:latest
LABEL authors="NIXEVOL"
WORKDIR /app
COPY . /app
RUN pip install --no-index --find-links=/app/packages-linux -r /app/requirements.txt

EXPOSE 3206

CMD ["python", "main.py"]