FROM python:3.12-slim

WORKDIR /app

# Install PostgreSQL client tools and network diagnostic tools
RUN apt-get update && apt-get install -y \
    postgresql-client \
    iputils-ping \
    dnsutils \
    curl \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Copy the entrypoint script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 8000

# Use the entrypoint script to wait for PostgreSQL and run migrations
ENTRYPOINT ["/docker-entrypoint.sh"]
