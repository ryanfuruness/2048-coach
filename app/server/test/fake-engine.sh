#!/usr/bin/env bash
# A stand-in for build/analyze --stdin in tests: answers each line with a tiny analysis; "hang" never answers,
# "crash" exits. Ignores its arguments.
while IFS= read -r line; do
  case "$line" in
    *hang*) exec sleep 3600 ;;
    *crash*) exit 3 ;;
    *) echo "{\"board\":[],\"moves\":[{\"move\":\"up\"}],\"echo\":\"${line//\"/}\"}" ;;
  esac
done
