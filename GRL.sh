#!/bin/sh
echo -ne '\033c\033]0;AutoLander\a'
base_path="$(dirname "$(realpath "$0")")"
"$base_path/GRL.x86_64" "$@"
