# Cliente liviano: tarsbrowser corre donde está el agente, no donde está el navegador.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends openssh-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY tarsbrowser.py cursor.js mcp_server.py README.md ./
RUN pip install --no-cache-dir websockets

# El host del navegador y la clave se pasan por entorno/montaje:
#   docker run --rm -it -e TARS_HOST=usuario@host -v ~/.ssh:/root/.ssh:ro tarsbrowser sistema
ENTRYPOINT ["python3", "tarsbrowser.py"]
