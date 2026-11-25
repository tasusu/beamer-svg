# Related work

| プロジェクト | 実装で参考にした点 |
| --- | --- |
| [dvisvgm](https://github.com/mgieseki/dvisvgm) | 変換器として直接使用。公式の現行マニュアルで `raw`、`rawdef`、`bbox`、座標・変換マクロ、用紙サイズ、フォント形式を確認した。 |
| [media4svg](https://ctan.org/pkg/media4svg) | LaTeX で動画領域を確保し、dvisvgm special から SVG 内の `foreignObject` へ HTML の動画を配置する。TeX Live 収録の実装で TeX 寸法から bp への変換、現在座標、bbox と定義の収集を確認した。 |
| [beamer2html](https://github.com/arunperiyal/beamer2html) | 2026 年公開。Python のパーサーが専用スタイルの構文、Beamer の段階表示やノートを処理し、専用 HTML デッキと MathJax、CSS/JS を生成する。TikZ は別単位で LaTeX に渡してオーバーレイごとの画像にし、PDF 画像は内容に応じて SVG または PNG とする。未知構文は警告とプレーンテキストになる。配布 ZIP、watch、オフライン表示、アニメーションと動画、発表者機能の先例。作者のコードは LPPL 1.3c 以降で、同梱 MathJax は Apache-2.0。 |
| [beamer-reveal](https://github.com/KBurbank/beamer-reveal) | Quarto 拡張。Lua フィルターを用意して Beamer 由来の内容を Reveal.js のプレゼンテーションに統合する。 |
| [Slipshow](https://github.com/panglesd/slipshow) | Markdown からスタンドアロン HTML を生成し、スクロール領域、段階的な実行、手描きの再生を提供する。 |
| [svg-animate](https://github.com/renard/svg-animate) | LaTeX パッケージ。TikZ 図の開示ステップを SMIL の opacity キーフレームにし、同じソースで静的 PDF を生成できる。AGPL。 |
| [animate](https://ctan.org/pkg/animate) | フレーム列を PDF や SVG でアニメーションにする既存の LaTeX パッケージ。 |

既存プロジェクトからコードをコピーしていません。BeamerWeb の操作単位は dvisvgm が変換した**スライド全体の SVG DOM**です。Beamer が出す組版結果に、作者が付けた ID と HTML ウィジェットを結び付けます。

## エンジンとフォント

- **LaTeX DVI** は標準 Beamer 構成で使いやすく、raw special と PGF の SVG ドライバが動作するため既定にしました。
- **dviLuaLaTeX** は DVI を直接出力します。同じデモの変換を確認しました。LuaLaTeX の PDF 専用拡張を利用する原稿は個別の互換性確認が必要です。
- **XeLaTeX `-no-pdf`** は XDV を生成します。同じデモを変換できましたが、dvisvgm は PDF special の一部を無視したと報告しました。システムフォントを使用する原稿の候補です。
- **グリフのパス化**は `--no-fonts` で有効にし、同一ページ内でパス定義を再利用します。ブラウザのフォント形式と読み込みに依存せず、配置を保持できます。テキスト選択・検索とテキストとしてのアクセシビリティは失われます。
- **WOFF/WOFF2** は dvisvgm の `--font-format` で埋め込みできます。文字列を保持しやすい一方、複数 SVG の inline 化ではフォントファミリー名や CSS をページ間で管理する必要があるため、MVP ではパスを選びました。dvisvgm 3.4.4 でデモの第 1 ページを変換すると、パス版は 26,429 バイト、WOFF2 埋め込み版は 14,752 バイトでした。

参照資料は [dvisvgm upstream man page](https://github.com/mgieseki/dvisvgm/blob/master/doc/dvisvgm.1) と [media4svg source](https://ctan.org/tex-archive/macros/latex/contrib/media4svg) です。
