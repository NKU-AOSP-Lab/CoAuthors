FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data \
    DBLP_XML_GZ_URL=https://dblp.org/xml/dblp.xml.gz \
    DBLP_DTD_URL=https://dblp.org/xml/dblp.dtd \
    DEFAULT_BUILD_MODE=fullmeta

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY app.py /app/app.py
COPY templates /app/templates
COPY static /app/static

VOLUME ["/data"]
EXPOSE 8090

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8090"]

