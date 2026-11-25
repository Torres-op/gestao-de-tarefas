# Imagem do Grello em dois alvos:
#   dev  (padrão): runserver com recarga automática, usado pelo docker-compose.yml
#   prod: gunicorn + arquivos estáticos coletados e servidos pelo WhiteNoise, usado pelo compose.prod.yml
FROM python:3.13-slim AS base

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

EXPOSE 8000
ENTRYPOINT ["docker-entrypoint.sh"]


FROM base AS prod

# A chave usada aqui serve só para o collectstatic rodar durante o build;
# em execução, DJANGO_SECRET_KEY precisa vir do ambiente.
RUN DJANGO_SECRET_KEY=somente-para-o-build DJANGO_DEBUG=False \
    python manage.py collectstatic --noinput \
    && chown -R app:app /app/staticfiles

USER app
ENV WEB_CONCURRENCY=3
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--access-logfile", "-"]


FROM base AS dev

USER app
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
