FROM python:3.10-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /requirements.txt
RUN pip3 install --no-cache-dir -U pip && pip3 install --no-cache-dir -U -r /requirements.txt

RUN mkdir /EvaMaria
WORKDIR /EvaMaria

COPY . /EvaMaria
RUN chmod +x /EvaMaria/start.sh /EvaMaria/serve_and_bot.sh

CMD ["/bin/bash", "/EvaMaria/serve_and_bot.sh"]
