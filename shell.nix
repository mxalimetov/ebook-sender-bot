{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  packages = with pkgs; [
    python311
    uv
    pkg-config
    openssl
    libffi
    calibre
  ];

  shellHook = ''
    export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
    export UV_PYTHON=python3
    echo "Calibre CLI (ebook-meta) available. Virtual env not required; use 'uv pip install -r requirements.txt' inside this shell."
  '';
}
