# BeamerWeb

Beamer が組版した全ページを dvisvgm で SVG に変換し、各ページの inline SVG DOM に JavaScript と HTML ウィジェットを接続します。同じ TeX ソースから PDF を生成できます。

## セットアップとデモ

Python 3.10 以上、TeX Live 2022 最終版以降の LaTeX・Beamer・PGF/TikZ、dvisvgm 2.13.3 以降が必要です。Debian 系では以下のパッケージが揃えばデモをビルドできます。

```sh
sudo apt-get install texlive-latex-recommended texlive-pictures texlive-fonts-recommended dvisvgm ghostscript
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
beamerweb build examples/demo.tex
beamerweb pdf examples/demo.tex
beamerweb serve examples/demo.tex
```

`_build/html/index.html` をブラウザで開けます。デモはスライダーで数式の透明度を変え、TikZ の頂点クリックで辺を強調し、Canvas アニメーションを再生・停止します。`_build/pdf/demo.pdf` には各ウィジェットの静的な表示が入ります。

`serve` はビルド後に loopback の HTTP サーバーを起動します。既定はポート 8000 で、`--port` で変更できます。パッケージをインストールせずにリポジトリから実行する場合は、各コマンドの `beamerweb` を `python3 -m beamerweb` に置き換えられます。`build` と `serve` は `--dvisvgm PATH` で使用する実行ファイルを指定できます。相対パスはコマンドを実行したディレクトリを基準にします。指定を省略した場合は `DVISVGM`、それも未設定の場合は `PATH` 上の `dvisvgm` を使います。

```sh
beamerweb build examples/demo.tex --dvisvgm /path/to/texlive/bin/dvisvgm
```

dvisvgm が Ghostscript を見つけられない場合は、`LIBGS` に Ghostscript の共有ライブラリのパスを設定してください。たとえば Debian の x86-64 環境では `export LIBGS=/usr/lib/x86_64-linux-gnu/libgs.so.10` です。

| 操作 | キー |
| --- | --- |
| 次へ | → / Space / PageDown |
| 前へ | ← / PageUp |
| 最初・最後 | Home / End |
| 全画面 | F |

`#/3` は物理ページ 3 へのリンクです。再読み込みとブラウザの戻る・進むでそのページを復元できます。

## ビルド出力と HTML テンプレート

コマンドを実行したディレクトリの `_build/` に出力します。

| パス | 内容 |
| --- | --- |
| `_build/html/` | HTML、JavaScript、CSS。 `serve` の配信ルート |
| `_build/pdf/` | 完成した PDF |
| `_build/intermediate/` | TeX のログ・補助ファイル、DVI/XDV、中間 SVG |

`-o` に相対パスを渡すと `_build/` を基準にします（例 `beamerweb build examples/demo.tex -o preview`）。`_build/` から始まる相対パスや、その配下の絶対パスも指定できます。

配布パッケージの [Jinja2 テンプレート](beamerweb/templates/index.html.j2) をカレントディレクトリの `_templates/index.html.j2` にコピーすると、プロジェクト単位で HTML を変更できます。テンプレートには `title`、`slides`（SVG の配列）、`metadata`、`placement`、`production` が渡されます。既存ランタイムを使う場合は、デッキやスライドの ID・クラスとスクリプト参照を維持してください。

## TeX と JavaScript の API

```tex
\documentclass{beamer}
\usepackage{beamerweb}
\begin{document}
\begin{frame}{Example}
  \webid{formula}{$f(\lambda)=1-e^{-\lambda}$}

  \webwidget[width=8cm,height=2cm,fallback={Static value: $\lambda=0.43$}]{slider}
\end{frame}
\end{document}
```

`\webid{name}{...}` と `webinteractive` 環境は、出力される SVG ノードを `data-web-id` の付いたグループに入れます。同じ組版ボックス内に収まる内容に使ってください。TikZ のパスや頂点には `\begin{scope}[web id=vertex-v] ... \end{scope}` を使えます。`\webwidget` は指定サイズを確保し、PDF で `fallback` に渡したインラインの TeX を左下のベースラインに置きます。高さを含めた配置が必要な場合は fallback にボックスを渡してください。省略時は空白になります。

`slides.tex` と同じ場所に置いた `slides.js` と `slides.css` を、CLI が配布フォルダへコピーします。`--js` と `--css` で別ファイルを選べます。JavaScript は通常のスクリプトとして実行されます。ライブラリが必要なら、事前に一つのスクリプトへバンドルしてください。

```js
BeamerWeb.registerWidget("slider", ({host, slide, svg, page, state, api}) => {
  const input = document.createElement("input");
  input.type = "range";
  input.value = state.value ?? "43";
  host.append(input);

  const update = () => {
    state.value = input.value;
    api.get("formula").style.opacity = Number(input.value) / 100;
  };
  input.addEventListener("input", update, {signal: api.signal});
  update();

  api.onOverlayEnter(event => console.log(event.detail.overlay));
  return () => { /* stop timers or remove external listeners */ };
});
```

- `api.get(id)` と `api.getAll(id)` は現在の SVG から要素を取得します。`api.on(id, type, listener)` は取得した要素すべてにイベントを登録します。
- ウィジェット関数は物理ページに入ると実行されます。`onSlideEnter` と `onOverlayEnter` はマウント後、`onOverlayLeave` と `onSlideLeave` はアンマウント前です。イベントの `detail` は `page` と同じメタデータです。
- `state` は論理フレーム、ウィジェット名、同名ウィジェットの出現順で保持します。ページを離れると `api.signal` が中止され、登録されたイベントリスナーが外れます。タイマー等の片付けは戻り値の関数で行います。
- 未登録のウィジェットはその領域に診断を表示します。`--production` ではコンソールに記録します。

HTML overlay が既定です。`--placement foreign-object` で、SVG 内部へ HTML を配置する経路も試せます。座標変換、選択理由、対応範囲は [ARCHITECTURE.md](ARCHITECTURE.md) に記載しています。

## テスト

```sh
python -m unittest discover -s tests -v
python -m pip install playwright selenium
python tests/browser_smoke.py chromium /path/to/google-chrome
python tests/browser_smoke.py chromium /path/to/msedge
python tests/browser_smoke.py firefox /path/to/firefox --driver /path/to/geckodriver
```

ブラウザテストは両方の配置方式で、配置、リサイズ、全画面、入力とスライド操作の分離、オーバーレイ移動、TikZ のクリック、Canvas の再生・停止を確認します。

## Related work

- **dvisvgm** は DVI/XDV の出力を SVG DOM に変換します。**media4svg** からは、TeX のボックス寸法と SVG 座標を special で接続する方式を調査しました。[dvisvgm manual](https://dvisvgm.de/Manpage/) · [media4svg](https://ctan.org/pkg/media4svg)
- **beamer2html**（2026 年、LPPL 1.3c 以降）は専用スタイルの LaTeX を解析して HTML デッキを生成し、数式を MathJax で表示し、TikZ はオーバーレイごとに個別変換します。オフライン配布、watch、発表者ビュー、動画やプロットの事例を確認しました。BeamerWeb では Beamer が生成した全ページを dvisvgm で SVG DOM にし、操作対象にします。[beamer2html](https://github.com/arunperiyal/beamer2html)
- **beamer-reveal** は Quarto の Lua フィルターで Reveal.js に対応します。**Slipshow** は Markdown からスクロールと段階的な実行を備えたオフライン HTML を生成します。**svg-animate** は TikZ 図に SMIL のステップアニメーションを埋め込み、同じソースから静的 PDF を出力します。[beamer-reveal](https://github.com/KBurbank/beamer-reveal) · [Slipshow](https://github.com/panglesd/slipshow) · [svg-animate](https://github.com/renard/svg-animate)

調査結果とエンジン比較は [RELATED-WORK.md](RELATED-WORK.md) にまとめています。
