# Imagem de desenvolvimento do Grello (Django + PostgreSQL via docker-compose.yml).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependências primeiro, para aproveitar o cache de camadas do Docker.
COPY requirements.txt .
RUN pip install -r requirements.txt

# O entrypoint fica fora de /app para não ser sobrescrito pelo bind mount (.:/app).
# O sed remove eventuais \r (checkout no Windows com core.autocrlf=true) e o
# chmod garante o bit de execução independentemente do sistema de arquivos do host.
COPY docker/entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh \
    && chmod +x /usr/local/bin/docker-entrypoint.sh

# Usuário não-root (UID 1000). No Docker Desktop (Windows/macOS) o bind mount
# continua legível e gravável por ele.
RUN useradd --create-home --uid 1000 app
COPY --chown=app:app . .
USER app

EXPOSE 8000

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
