#!/usr/bin/env bash
set -euo pipefail

sudo apt update
sudo apt install -y \
  python3-opencv \
  v4l-utils \
  gstreamer1.0-tools \
  gstreamer1.0-plugins-base \
  gstreamer1.0-plugins-good \
  gstreamer1.0-libav

python3 scripts/diagnosticar_camera_linux.py

cat <<'EOF'

Se "GStreamer no OpenCV" aparecer como False e você estiver dentro de uma
.venv, o ambiente provavelmente está usando o pacote opencv-python do pip.
No Raspberry, use o Python do sistema ou recrie a venv com:

  python3 -m venv --system-site-packages .venv
  source .venv/bin/activate
  python -m pip install numpy gpiozero

Depois execute novamente:

  python scripts/diagnosticar_camera_linux.py --testar
EOF
