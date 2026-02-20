#!/bin/bash
# Copies all exported image files to Anki's collection.media folder.
# Moves processed export folders to a synced/ subfolder so they aren't re-processed.
# Usage: ./scripts/sync_to_anki.sh [anki_profile]

PROFILE="${1:-User 1}"
ANKI_MEDIA="$HOME/Library/Application Support/Anki2/$PROFILE/collection.media"
EXPORTS_DIR="$(dirname "$0")/../data/exports"
SYNCED_DIR="$EXPORTS_DIR/synced"

if [ ! -d "$ANKI_MEDIA" ]; then
    echo "Error: Anki media folder not found at: $ANKI_MEDIA"
    echo "Usage: $0 [profile_name]"
    exit 1
fi

mkdir -p "$SYNCED_DIR"

count=0

for dir in "$EXPORTS_DIR"/*/; do
    # Skip the synced/ directory
    dirname_base="$(basename "$dir")"
    if [ "$dirname_base" = "synced" ]; then
        continue
    fi

    # Only process folders that contain a cards.csv
    if [ ! -f "$dir/cards.csv" ]; then
        continue
    fi

    # Copy image files directly from the folder
    n=0
    for ext in png jpg jpeg gif webp; do
        for img in "$dir"*."$ext"; do
            if [ -f "$img" ]; then
                cp "$img" "$ANKI_MEDIA/"
                n=$((n + 1))
            fi
        done
    done

    count=$((count + n))
    echo "Copied $n images from $dirname_base/"

    # Move processed folder to synced/
    mv "$dir" "$SYNCED_DIR/"
done

if [ "$count" -eq 0 ]; then
    echo "No image files found to copy."
else
    echo "Done — copied $count images to $ANKI_MEDIA"
fi
