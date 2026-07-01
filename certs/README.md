# certs

This directory is for local HTTPS certificates.

Generate a self-signed certificate with:

```bash
bash scripts/make_self_signed_cert.sh <LAN_IP>
```

Expected output files:

```text
certs/localhost.pem
certs/localhost-key.pem
```

Do not commit private keys for real projects.
