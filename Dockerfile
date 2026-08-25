FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# persistent state (accounts + tcp domains)
ENV TCP_STATE_FILE=/data/tcp_state.json
ENV ACCOUNTS_FILE=/data/accounts.json

CMD ["python", "bot.py"]
