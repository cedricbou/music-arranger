#!/usr/bin/env bash
# Lance une commande arr sur une sortie son virtuelle et silencieuse.
#
# C'est la seule façon autorisée de tester l'audio en direct (capture, play, record,
# calibrate, levels) : rien ne sort sur les enceintes, et ce qui est joué revient sur
# l'entrée, comme si un câble reliait la sortie à l'entrée.
#
#   scripts/loopback.sh arr calibrate
#   scripts/loopback.sh arr record essai --count-in 1      (depuis un dossier de projet)
#   CHANNELS=12 scripts/loopback.sh arr levels --seconds 2
#
# La sortie virtuelle et le fichier de réglages temporaire sont retirés à la fin, même en
# cas d'erreur ou de Ctrl+C.
set -euo pipefail

if [ $# -eq 0 ]; then
    sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
fi

name="arr_test"
channels="${CHANNELS:-2}"
map=$(seq -s, -f "aux%g" 0 $((channels - 1)))
config=$(mktemp --suffix=.toml)
module=$(pactl load-module module-null-sink sink_name="$name" \
    sink_properties=device.description="$name" channels="$channels" channel_map="$map" rate=48000)

cleanup() {
    pactl unload-module "$module" 2>/dev/null || true
    rm -f "$config"
}
trap cleanup EXIT

cat > "$config" <<TOML
[output]
device = "$name"
channels = [1, 2]

[input]
device = "$name"
channels = [1]

[capture]
source = "$name.monitor"
channels = []
TOML

sleep 1  # le temps que PipeWire annonce la nouvelle sortie
ARR_AUDIO="$config" "$@"
