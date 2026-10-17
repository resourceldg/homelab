# tb-puente: mqtt-aula -> ThingsBoard. Ver puente.py.
FROM python:3.12.14-alpine

RUN pip install --no-cache-dir paho-mqtt==2.1.0 \
    && adduser -D -H -u 10001 puente

COPY puente.py simulador.py /app/
USER 10001
EXPOSE 9101
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:9101/salud', timeout=3).status == 200 else 1)"
CMD ["python", "-u", "/app/puente.py"]
