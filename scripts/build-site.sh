#!/bin/sh
# fonts/ と out/ から、fonts.euphoric.band で配るファイルを dist/ に並べる。
set -eu
cd "$(dirname "$0")/.."

FONT=fonts/webfonts/EuphoricPixel-Regular.woff2
DEST=dist/euphoric-pixel

rm -rf dist
mkdir -p "$DEST"
cp site/_headers site/_redirects dist/
cp site/index.html "$FONT" "$DEST/"
HASH=$(sha256sum "$FONT" | cut -c1-8)
sed "s/@HASH@/$HASH/" site/euphoric-pixel.css > "$DEST/euphoric-pixel.css"

# 検査レポートと proof は make test / make proof を走らせたときだけある。
for report in fontspector proof; do
	if [ -d "out/$report" ]; then
		cp -r "out/$report" "$DEST/"
	fi
done
