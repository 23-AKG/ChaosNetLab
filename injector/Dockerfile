
FROM python:3.10-slim
WORKDIR /app
RUN apt update && apt install -y iproute2 iputils-ping curl tcpdump netcat
COPY modules/ modules/
COPY cli.py .
CMD ["bash"]
