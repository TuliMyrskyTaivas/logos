# Certificates

This directory holds the public root certificates of the Russian Ministry of
Digital Development (Минцифры) — the Russian Trusted Root CA and Russian
Trusted Sub CA. They are needed to verify TLS connections to upstream
providers whose certificates are signed by that CA, and are intended to be
copied into the service image (see `../Dockerfile`).

Unlike `mímir/certs/`, these files are public trust anchors: they contain no
private keys and may be committed.

Expected files:

| File                        | Purpose                             |
| --------------------------- | ----------------------------------- |
| `russian_trusted_root_ca.crt` | Russian Trusted Root CA            |
| `russian_trusted_sub_ca.crt`  | Russian Trusted Sub CA             |

Source: the [Gosuslugi](https://www.gosuslugi.ru/crt) certificate
distribution page ("Русский доверенный корневой сертификат" and
"Русский доверенный суб-сертификат").

Keep the `.crt` extension: when the image CA bundle is assembled,
`update-ca-certificates` only picks up `*.crt` files from
`/usr/local/share/ca-certificates`. The file content is ordinary PEM.

The `ca-bundle` stage in `../Dockerfile` installs these certificates into a
copy of the Debian CA bundle, which then replaces
`/etc/ssl/certs/ca-certificates.crt` in the final image. That is the default
bundle Go reads at runtime, so TLS clients in the service trust the Минцифры
roots without any code changes.
