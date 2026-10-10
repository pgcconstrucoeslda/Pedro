#!/usr/bin/env bash
# Compila e instala o conversor dwg2dxf (LibreDWG) em ~/.local/bin
set -euo pipefail
WORK=${WORK:-$(mktemp -d)}
cd "$WORK"
git clone --depth 1 https://github.com/LibreDWG/libredwg.git
cd libredwg
git submodule update --init --depth 1 jsmn
mkdir -p b && cd b
cmake .. -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF
make -j"$(nproc)" dwg2dxf
mkdir -p "$HOME/.local/bin"
cp dwg2dxf "$HOME/.local/bin/"
echo "Instalado em $HOME/.local/bin/dwg2dxf"
