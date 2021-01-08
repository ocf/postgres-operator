FROM python:3.9-alpine
ADD requirements.txt /
# TODO: Figure out how to not do this but also use alpine.
RUN apk --no-cache add gcc musl-dev
RUN pip install -r requirements.txt
ADD src /mko
CMD kopf run --liveness=http://0.0.0.0:8080/healthz /mko/main.py