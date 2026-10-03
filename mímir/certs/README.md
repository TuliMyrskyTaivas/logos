# Certificates

This directory holds the X.509 material used for mutual TLS. It is
intentionally empty in the repository — real certificates and private keys
must never be committed.

Expected files:

| File         | Purpose                                                          |
| ------------ | ---------------------------------------------------------------- |
| `ca.crt`     | CA that signs client certificates (trusted by the server).       |
| `server.crt` | Server TLS certificate (CN/SAN = service hostname).              |
| `server.key` | Server TLS private key (keep secret).                            |
| `client.crt` | Example client certificate signed by `ca.crt`.                   |
| `client.key` | Example client private key.                                      |

Generate a local development CA and certificates with, for example:

```bash
# Development CA
openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
  -keyout ca.key -out ca.crt -subj "/CN=Mimir Dev CA"

# Server certificate (CN must match the hostname clients use)
openssl req -newkey rsa:2048 -nodes -keyout server.key -out server.csr \
  -subj "/CN=localhost"
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -days 3650 -out server.crt

# Example client certificate
openssl req -newkey rsa:2048 -nodes -keyout client.key -out client.csr \
  -subj "/CN=mimir-client"
openssl x509 -req -in client.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -days 3650 -out client.crt
```

Point the service at these files with the `MIMIR_*` environment variables
(see `../AGENTS.md`).
