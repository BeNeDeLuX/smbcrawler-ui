#!/bin/sh
# Ensures /certs/active.{crt,key} exist (generating a self-signed pair on
# first boot if nothing has been uploaded yet), then watches the cert
# directory and reloads nginx whenever the backend swaps active.crt/active.key
# out -- so uploading or resetting the certificate via the API takes effect
# without restarting this container.
set -e

CERT_DIR=/certs
mkdir -p "$CERT_DIR"

generate_self_signed() {
    echo "[proxy] generating self-signed certificate"
    openssl req -x509 -nodes -newkey rsa:2048 -days 3650 \
        -keyout "$CERT_DIR/self-signed.key" \
        -out "$CERT_DIR/self-signed.crt" \
        -subj "/CN=smbcrawler-ui" \
        -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
}

if [ ! -f "$CERT_DIR/self-signed.crt" ] || [ ! -f "$CERT_DIR/self-signed.key" ]; then
    generate_self_signed
fi

if [ ! -f "$CERT_DIR/active.crt" ] || [ ! -f "$CERT_DIR/active.key" ]; then
    cp "$CERT_DIR/self-signed.crt" "$CERT_DIR/active.crt"
    cp "$CERT_DIR/self-signed.key" "$CERT_DIR/active.key"
    echo "self-signed" > "$CERT_DIR/active.source"
fi

# Watch the directory (not the files directly): the backend replaces
# active.crt/active.key via an atomic rename, which swaps the inode at that
# path rather than modifying it in place, so a watch on the file itself can
# miss the change. -m keeps inotifywait running and emitting one line per
# event instead of exiting after the first.
(
    inotifywait -m -e close_write,moved_to,create --format '%f' "$CERT_DIR" 2>/dev/null |
    while read -r changed; do
        case "$changed" in
        active.crt | active.key)
            echo "[proxy] active certificate changed, reloading nginx"
            nginx -s reload || true
            ;;
        esac
    done
) &

exec nginx -g "daemon off;"
