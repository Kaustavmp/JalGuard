FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip

RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:${PATH}"

COPY --chown=user:user requirements.txt ./requirements.txt
COPY --chown=user:user BACKEND/requirements.txt ./BACKEND/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user:user . .

EXPOSE 7860

CMD ["uvicorn", "BACKEND.main:app", "--host", "0.0.0.0", "--port", "7860"]
