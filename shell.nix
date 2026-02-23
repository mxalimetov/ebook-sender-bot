{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  packages = with pkgs; [
    python311
    uv
    pkg-config
    openssl
    libffi
  ];

  shellHook = ''
    export UV_PYTHON=python3
    echo "Virtual env not required; use 'uv pip install -r requirements.txt' inside this shell."
  '';
}
