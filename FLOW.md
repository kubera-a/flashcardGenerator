# Flow: Markdown ZIP to Anki

1. Upload markdown ZIP (contains `.md` + images) via web UI
2. Process — LLM generates cards with `[IMAGE: ...]` references
3. Review cards in web UI (approve/reject/edit)
4. Click "Export with Images" — creates `data/exports/<deck_tag>/` with `cards.csv` + image files flat
5. Run `./scripts/sync_to_anki.sh` — copies images to Anki's `collection.media`, moves folder to `synced/`
6. Import `cards.csv` into Anki (check "Allow HTML in fields")
