# Architecture

```text
                  ┌─ pdflatex / lualatex / xelatex ─────── PDF
Beamer .tex ──────┤
                  └─ LaTeX DVI / XeLaTeX XDV ─ dvisvgm ─ inline SVG + widget runtime
```

## TeX から SVG 座標へ

Web ビルドは TeX の文書開始フックでパッケージを読み込み、PGF の dvisvgm ドライバを選択します。DVI の変換で閉じていない SVG グループが見つかった場合は、PGF の dvips ドライバと dvisvgm の PostScript サポートを使って再試行します。通常の PDF ビルドでは `\webid` と `webinteractive` は中身をそのまま組版し、ウィジェットの枠に静的な fallback を置きます。

可視要素のまとまりは `dvisvgm:raw` の開始・終了タグで SVG の `g` に収めます。ウィジェットにはゼロ幅の rule と固定幅の箱で所定の空間を割り当てます。marker の左上は `{?x}` と `{?(y-height)}` で、現在の DVI ベースラインから決まります。高さと幅は TeX pt（72.27 pt/in）から big point（72 bp/in）へ変換します。`{?matrix}` は dvisvgm が処理中の変換を引き継ぎます。

`--bbox=papersize` で空白を含む用紙全体を保ちます。marker は物理的に確保済みの矩形なので、描画内容に基づく `dvisvgm:bbox` や `{?bbox name}` に依存しません。定義領域への挿入に使う `rawdef` は、ウィジェットや scene graph のグループを描画位置で生成する今回の用途では不要です。

Python の XML パーサーで SVG の名前空間と `viewBox` を検証し、ID とローカルの `href`・属性中の `url(#id)` にページごとの接頭辞を付けます。これにより、同じグリフ ID が別のページにもある場合に参照が衝突しません。ユーザーが付けた `data-web-id` は API として保持されます。対応する dvisvgm には画像の `--embed-bitmaps` を渡します。TeX Live 2022 最終版に同梱の dvisvgm 2.13.3 ではこのオプションを省略します。

## SVG 座標から HTML 座標へ

SVG は `preserveAspectRatio="xMidYMid meet"` で表示し、余白を付けてアスペクト比を保ちます。HTML overlay では `getScreenCTM()` で marker のローカル座標をブラウザのビューポート座標へ写します。`DOMPoint` による変換で求めた左上座標からレイヤーの `getBoundingClientRect()` を引き、行列の線形成分と組み合わせて HTML に CSS の `matrix()` を適用します。そのため、marker の拡大縮小と回転は HTML にも伝わります。

`ResizeObserver`、ウィンドウと visual viewport の resize、fullscreenchange で行列を更新します。配置は CSS ピクセル単位です。Canvas の描画バッファ解像度にはデモ側で `devicePixelRatio` を使っています。装飾用のレイヤー自体はポインターイベントを通し、ウィジェットの領域だけが入力を受け取ります。

`foreignObject` 方式は marker と同じ SVG 親要素の直下に同一の座標・変換を持つノードを置くため、SVG 内の描画順、clipping、変換を継承できます。HTML overlay は DOM 上で独立した操作レイヤーとなり、入力や CSS を扱いやすく、プレゼンテーション UI と同じ CSS 座標でデバッグできます。こうした扱いやすさを優先して HTML overlay を既定としました。SVG 内の重なり順やクリップを反映したい場合は `foreignObject` を指定します。

## 論理フレームと物理ページ

ランタイムの状態は DVI/XDV の物理ページと一対一です。Beamer の `.nav` に書かれた `\beamer@framepages{first}{last}` を列挙して論理フレームを割り当て、各範囲での 1 始まりの位置を `overlay` とします。タイトルは TeX の shipout フックでそのページのタイトルを文字列として記録します。タイトルに含まれる TeX マクロは文字列に残ります。

```json
{"physicalPage": 2, "frame": 1, "overlay": 2, "frameTitle": "HTML slider"}
```

この `overlay` は出力順です。`\includeonlyframes` やオーバーレイ選択で投影対象から外れたページを数えません。`allowframebreaks` の継続ページも物理ページとして扱います。論理フレームの範囲がないページにも移動でき、その場合の frame と overlay は null になります。

## 対応範囲

- LaTeX DVI は、TeX Live 2022 最終版の dvisvgm 2.13.3 と、dvisvgm 3.4.4 の両方で検証しています。Beamer 3.72 と PGF の SVG ドライバでは、一部の丸角ブロックで SVG グループの不整合を再現し、DVI の再試行で Madrid の丸角ブロックを変換できることを確認しました。デモは XeLaTeX でも比較できるよう通常のブロックテンプレートを指定しています。明示的な背景透過、PDF 画像や PDF 固有の special は使用する TeX エンジンと dvisvgm で確認してください。
- build は LaTeX を 2 回実行します。複雑な文献処理などの追加ツール、SVG 埋め込みスタイルに含まれる独自の ID セレクター、他ページを指す Beamer のリンクの変換、watch は今後の拡張です。
- ソースと sidecar JavaScript は信頼できるものを利用してください。TeX には `-no-shell-escape` を渡し、ウィジェット名は明示的なレジストリで解決します。変換済み SVG と JavaScript を含む出力は作者のコードとして実行されます。
- `_build/html/` には core runtime とデモに必要なファイルが含まれます。作者の JavaScript や CSS が追加アセットを参照する場合は、そのファイルも配布してください。
