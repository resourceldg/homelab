#!/usr/bin/env python3
"""Arma el manual en PDF, ordenado desde Fundamentos, con portada, índice,
diagramas dibujados y enlaces internos. Corre EN TU COMPUTADORA.

    python3 scripts/manual-pdf.py            (deja docs/manual-arquitectura-homelab.pdf)

Por qué así: el sitio (MkDocs) dibuja los diagramas Mermaid en el navegador, con
JavaScript; un PDF no ejecuta nada. Por eso este script los dibuja antes
(mermaid-cli), convierte cada capítulo a HTML, une todo en el orden del `nav` de
mkdocs.yml y lo imprime con Chrome, que muestra bien SVG, acentos y emojis.

Navegación del PDF: índice con número de página y enlace a cada capítulo,
marcadores (el panel lateral del visor: partes y capítulos), y en cada hoja el
nombre del capítulo arriba. Los números de página salen de imprimir dos veces:
la primera mide dónde cae cada capítulo, la segunda los escribe en el índice.

Necesita: Python con `markdown` y `pymdown-extensions` (vienen con
mkdocs-material) y `pypdf`, `npx` (Node) para mermaid-cli, y Google Chrome o
Chromium.
"""
import hashlib
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date

import markdown
import yaml

try:
    import pypdf
except ImportError:
    sys.exit("Falta pypdf (números de página del índice y marcadores): pip install pypdf")

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS = os.path.join(RAIZ, "docs", "handbook")
SALIDA = os.path.join(RAIZ, "docs", "manual-arquitectura-homelab.pdf")
CACHE = os.path.join(tempfile.gettempdir(), "manual-pdf-mermaid")
CHROME = next((c for c in ("google-chrome", "chromium", "chromium-browser") if shutil.which(c)), None)


def leer_nav():
    """[(parte, titulo, archivo)] en el orden del manual."""
    with open(os.path.join(RAIZ, "mkdocs.yml"), encoding="utf-8") as fh:
        # mkdocs.yml usa una etiqueta !!python/name: que yaml.safe_load no acepta
        texto = re.sub(r"!!python/name:\S+", "''", fh.read())
    nav = yaml.safe_load(texto)["nav"]
    paginas = []
    for item in nav:
        (titulo, valor), = item.items()
        if isinstance(valor, list):
            for sub in valor:
                (t, archivo), = sub.items()
                paginas.append((titulo, t, archivo))
        else:
            paginas.append((None, titulo, valor))
    return paginas


def dibujar_mermaid(codigo):
    """Dibuja un diagrama Mermaid a SVG (con caché) y devuelve la ruta."""
    os.makedirs(CACHE, exist_ok=True)
    h = hashlib.sha1(("pdf22seq" + codigo).encode()).hexdigest()[:16]
    svg = os.path.join(CACHE, f"{h}.svg")
    if not os.path.exists(svg):
        mmd = os.path.join(CACHE, f"{h}.mmd")
        with open(mmd, "w", encoding="utf-8") as fh:
            fh.write(codigo)
        # Letra más grande que en la web: en papel el diagrama se achica al ancho de la hoja.
        conf = os.path.join(CACHE, "mermaid-pdf.json")
        with open(conf, "w") as fh:
            fh.write('{"themeVariables": {"fontSize": "22px"}, "flowchart": {"nodeSpacing": 30, "rankSpacing": 40},'
                     ' "sequence": {"messageFontSize": 22, "actorFontSize": 22, "noteFontSize": 20,'
                     ' "actorMargin": 30, "width": 120, "useMaxWidth": true}}')
        subprocess.run(["npx", "-y", "-p", "@mermaid-js/mermaid-cli@11", "mmdc", "-q", "-c", conf,
                        "-i", mmd, "-o", svg, "-b", "white"], check=True, timeout=180)
    return svg


# Letra de los diagramas en papel: se dibujan con 22 px y después se achican al
# ancho de la hoja. Si en una hoja vertical la letra queda por debajo de este
# mínimo, el diagrama va solo en una hoja apaisada (50 % más de ancho).
LETRA_MINIMA_PT = 7.5
MM_POR_PT = 0.3528


def letra_pt(svg, ancho_mm, alto_mm):
    with open(svg, encoding="utf-8") as fh:
        m = re.search(r'viewBox="[\d.\-]+ [\d.\-]+ ([\d.]+) ([\d.]+)"', fh.read())
    w, h = float(m.group(1)), float(m.group(2))
    return 22 * min(ancho_mm / w, alto_mm / h) / MM_POR_PT


# Lo que se lee en la hoja vertical antes de una apaisada: sin esto, el título de
# la sección queda solo al pie de una hoja casi vacía.
AVISO_APAISADA = '<p class="aviso-apaisada">→ El diagrama sigue en la página siguiente (hoja apaisada).</p>'


def bloque_diagrama(svg):
    vertical, apaisada = letra_pt(svg, 178, 200), letra_pt(svg, 273, 180)
    # Apaisada solo si la vertical no alcanza el mínimo Y la apaisada mejora: un
    # diagrama alto se lee PEOR apaisado (lo limita la altura de la hoja).
    clase = "apaisada" if vertical < LETRA_MINIMA_PT and apaisada > vertical else "diagrama"
    aviso = AVISO_APAISADA if clase == "apaisada" else ""
    return f'\n{aviso}<div class="{clase}"><img src="file://{svg}" alt="diagrama"></div>\n'


def slug_parte(parte):
    return "parte-" + re.sub(r"[^a-z0-9]+", "-", parte.lower()).strip("-")


def texto_css(t):
    return t.replace("\\", "\\\\").replace('"', '\\"')


def capitulo_html(archivo, ids_paginas, parte=None, titulo=""):
    slug_pag = os.path.splitext(archivo)[0]
    with open(os.path.join(DOCS, archivo), encoding="utf-8") as fh:
        texto = fh.read()
    # Mermaid -> imagen ya dibujada
    texto = re.sub(r"```mermaid\n(.*?)```", lambda m: bloque_diagrama(dibujar_mermaid(m.group(1))), texto, flags=re.S)
    cuerpo = markdown.markdown(texto, extensions=[
        "tables", "toc", "attr_list", "admonition", "pymdownx.superfences", "pymdownx.details", "sane_lists"])
    # ids únicos por capítulo y enlaces internos
    cuerpo = re.sub(r'id="([^"]+)"', lambda m: f'id="{slug_pag}--{m.group(1)}"', cuerpo)

    def enlace(m):
        destino = m.group(1)
        if re.match(r"^(https?:|mailto:)", destino):
            return m.group(0)
        if destino.startswith("#"):
            return f'href="#{slug_pag}--{destino[1:]}"'
        arch, _, ancla = destino.partition("#")
        base = os.path.basename(arch)
        if base.endswith(".md") and os.path.splitext(base)[0] in ids_paginas:
            otro = os.path.splitext(base)[0]
            return f'href="#{otro}--{ancla}"' if ancla else f'href="#{otro}"'
        # Enlaces a archivos del repo fuera del manual: a GitHub
        ruta = os.path.normpath(os.path.join("docs/handbook", arch))
        return f'href="https://github.com/resourceldg/homelab/blob/main/{ruta}{("#" + ancla) if ancla else ""}"'
    cuerpo = re.sub(r'href="([^"]+)"', enlace, cuerpo)
    cuerpo = re.sub(r'src="img/([^"]+)"', lambda m: f'src="file://{os.path.join(DOCS, "img", m.group(1))}"', cuerpo)
    # Imágenes propias: misma regla que los diagramas (la orientación que deje la
    # letra más grande), medida con su letra más chica.
    def img_propia(m):
        ruta = m.group(2)
        with open(ruta, encoding="utf-8") as fh:
            t = fh.read()
        w, h = map(float, re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', t).groups())
        chica = min(float(x) for x in re.findall(r'font-size="([\d.]+)"', t))
        vertical = chica * min(178 / w, 200 / h) / MM_POR_PT
        apaisada = chica * min(273 / w, 180 / h) / MM_POR_PT
        if vertical < LETRA_MINIMA_PT and apaisada > vertical:
            return AVISO_APAISADA + f'<div class="apaisada">{m.group(1)}</div>'
        return f'<p>{m.group(1)}</p>'
    cuerpo = re.sub(r'<p>(<img [^>]*src="file://([^"]+\.svg)"[^>]*>)</p>', img_propia, cuerpo)
    # Banda arriba del título: a qué parte pertenece (se ve al pasar las hojas).
    banda = f'<div class="cap-banda">{html.escape(parte or "Manual")}</div>'
    return f'<section class="capitulo" id="{slug_pag}" style="page: p-{slug_pag}">{banda}{cuerpo}</section>'


CSS = """
@page { size: A4; margin: 18mm 16mm 20mm 16mm;
  @bottom-center { content: counter(page); font: 9pt 'DejaVu Sans', sans-serif; color: #777; }
  @top-right { content: "Manual de Arquitectura del Homelab"; font: 8pt 'DejaVu Sans', sans-serif; color: #999; } }
@page portada { @bottom-center { content: none; } @top-right { content: none; } }
@page apaisada { size: A4 landscape; margin: 12mm; }
.apaisada { page: apaisada; break-before: page; break-after: page; display: flex; align-items: center; height: 180mm; }
.apaisada img { width: 100%; max-height: 180mm; object-fit: contain; }
.aviso-apaisada { color: #757575; font-style: italic; font-size: 9.5pt; }
body { font-family: 'DejaVu Sans', 'Noto Sans', Arial, sans-serif; font-size: 10.5pt; line-height: 1.5; color: #212121; }
.portada { page: portada; height: 250mm; display: flex; flex-direction: column; justify-content: center; text-align: center; }
.portada h1 { font-size: 30pt; color: #00796b; margin: 0 0 6mm; }
.portada .sub { font-size: 14pt; color: #424242; margin-bottom: 18mm; }
.portada img { width: 100%; margin: 6mm 0 14mm; }
.portada .autor { font-size: 13pt; font-weight: bold; } .portada .fecha { color: #757575; }
.indice { break-before: page; } .indice h1 { color: #00796b; margin-bottom: 1mm; }
.indice .ayuda { color: #757575; font-size: 9pt; margin: 0 0 4mm; }
.indice ul { list-style: none; padding: 0; margin: 0; }
.indice li { margin: 0; break-inside: avoid; }
.indice a { display: flex; align-items: baseline; gap: 2mm; padding: 1.1mm 0; text-decoration: none; color: #004d40; }
.indice a .t { flex: none; max-width: 85%; }
.indice a .puntos { flex: 1; border-bottom: 1.5px dotted #80cbc4; transform: translateY(-1mm); }
.indice a .n { flex: none; min-width: 9mm; text-align: right; font-weight: bold; color: #00796b; }
.indice li.parte a { margin-top: 4mm; padding: 1.6mm 2mm; background: #e0f2f1; border-left: 4px solid #00796b;
                     font-weight: bold; color: #00695c; }
.indice li.cap a { padding-left: 6mm; }
.separador { break-before: page; height: 230mm; display: flex; flex-direction: column; align-items: center;
             justify-content: center; }
.separador .rotulo { color: #80cbc4; font-size: 11pt; letter-spacing: 3px; text-transform: uppercase; }
.separador h1 { font-size: 28pt; color: #00796b; border: none; text-align: center; }
.capitulo { break-before: page; }
.cap-banda { background: #00796b; color: #fff; font-size: 9pt; letter-spacing: 1.5px; text-transform: uppercase;
             padding: 1.6mm 3mm; margin: 0 0 3mm; border-radius: 2px; }
h1 { color: #00796b; font-size: 21pt; border-bottom: 2px solid #00796b; padding-bottom: 2mm; }
h2 { color: #004d40; font-size: 15pt; margin-top: 7mm; break-after: avoid; }
h3 { color: #00695c; font-size: 12.5pt; break-after: avoid; } h4 { break-after: avoid; }
a { color: #00796b; }
table { border-collapse: collapse; width: 100%; margin: 3mm 0; font-size: 9.2pt; break-inside: avoid; }
th, td { border: 1px solid #cfd8dc; padding: 1.6mm 2mm; vertical-align: top; text-align: left; }
th { background: #e0f2f1; }
code { font-family: 'DejaVu Sans Mono', monospace; font-size: 8.8pt; background: #f1f3f4; padding: 0 1mm; border-radius: 2px; }
pre { background: #f6f8fa; border: 1px solid #e0e0e0; border-radius: 3px; padding: 3mm; font-size: 8.4pt;
      white-space: pre-wrap; word-break: break-word; break-inside: avoid; }
pre code { background: none; padding: 0; }
blockquote { border-left: 4px solid #80cbc4; margin: 3mm 0; padding: 1mm 4mm; background: #f1f8f7; color: #37474f; }
img { max-width: 100%; } .diagrama { text-align: center; margin: 4mm 0; break-inside: avoid; }
.diagrama img { max-height: 200mm; } p img { display: block; margin: 4mm auto; break-inside: avoid; }
"""


def main():
    if not CHROME:
        sys.exit("No encontré Chrome/Chromium para imprimir el PDF.")
    paginas = leer_nav()
    ids = {os.path.splitext(a)[0] for _, _, a in paginas}

    portada = f"""<div class="portada">
      <h1>Manual de Arquitectura del Homelab</h1>
      <div class="sub">Arquitectura de software aplicada al diseño IoT,<br>desde cero, con el servidor del aula como caso real</div>
      <img src="file://{os.path.join(DOCS, 'img', 'ciclo-completo.svg')}" alt="El ciclo completo">
      <div class="autor">Lucas D. Gómez — arquitecto de software</div>
      <div class="fecha">Versión del {date.today().strftime('%d/%m/%Y')} · generado desde el repositorio</div>
    </div>"""

    def indice(paginas_de):
        n = lambda ancla: paginas_de.get(ancla, "")
        out = ['<div class="indice"><h1>Índice</h1>',
               '<p class="ayuda">Tocá un título para ir a ese capítulo. También podés usar los marcadores '
               '(el panel lateral de tu visor de PDF).</p><ul>']
        parte_actual = object()
        for parte, titulo, archivo in paginas:
            if parte and parte != parte_actual:
                a = slug_parte(parte)
                out.append(f'<li class="parte"><a href="#{a}"><span class="t">{html.escape(parte)}</span>'
                           f'<span class="puntos"></span><span class="n">{n(a)}</span></a></li>')
            parte_actual = parte
            a = os.path.splitext(archivo)[0]
            out.append(f'<li class="{"cap" if parte else "suelto"}"><a href="#{a}"><span class="t">{html.escape(titulo)}</span>'
                       f'<span class="puntos"></span><span class="n">{n(a)}</span></a></li>')
        out.append("</ul></div>")
        return "".join(out)

    cuerpo = []
    estilos_pagina = []
    parte_actual = object()
    for parte, titulo, archivo in paginas:
        if parte and parte != parte_actual:
            cuerpo.append(f'<div class="separador" id="{slug_parte(parte)}"><div class="rotulo">Parte</div>'
                          f'<h1>{html.escape(parte)}</h1></div>')
        parte_actual = parte
        print("capítulo:", archivo)
        cuerpo.append(capitulo_html(archivo, ids, parte, titulo))
        # Cada capítulo es una "página con nombre": arriba de cada hoja dice dónde estás.
        slug = os.path.splitext(archivo)[0]
        arriba = f"{parte} · {titulo}" if parte else titulo
        estilos_pagina.append(f'@page p-{slug} {{ @top-left {{ content: "{texto_css(arriba)}"; '
                              f"font: 8pt 'DejaVu Sans', sans-serif; color: #00796b; }} }}")

    def imprimir(paginas_de):
        doc = (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Manual de Arquitectura del Homelab</title>'
               f'<style>{CSS}{"".join(estilos_pagina)}</style></head><body>{portada}{indice(paginas_de)}'
               f'{"".join(cuerpo)}</body></html>')
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as fh:
            fh.write(doc)
            html_tmp = fh.name
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-sandbox", "--allow-file-access-from-files",
                        "--no-pdf-header-footer", f"--print-to-pdf={SALIDA}", f"file://{html_tmp}"],
                       check=True, timeout=300, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.unlink(html_tmp)
        # Dónde cayó cada capítulo: Chrome deja un destino con nombre por cada ancla enlazada.
        r = pypdf.PdfReader(SALIDA)
        return {nombre.lstrip("/"): r.get_destination_page_number(d) + 1
                for nombre, d in r.named_destinations.items()}

    # Dos pasadas (o más, si agregar los números corriera el índice a otra hoja).
    paginas_de = {}
    for _ in range(4):
        medidas = imprimir(paginas_de)
        if all(paginas_de.get(k) == medidas.get(k) for k in medidas) and paginas_de:
            break
        paginas_de = medidas
    else:
        sys.exit("Los números de página del índice no se estabilizan.")

    # Marcadores (panel lateral): Portada, Índice y cada parte con sus capítulos.
    lector = pypdf.PdfReader(SALIDA)
    escritor = pypdf.PdfWriter(clone_from=lector)
    escritor.add_outline_item("Portada", 0)
    escritor.add_outline_item("Índice", 1)
    padre, parte_actual = None, object()
    for parte, titulo, archivo in paginas:
        if parte != parte_actual:
            padre = (escritor.add_outline_item(parte, paginas_de[slug_parte(parte)] - 1, bold=True)
                     if parte else None)
            parte_actual = parte
        escritor.add_outline_item(titulo, paginas_de[os.path.splitext(archivo)[0]] - 1, parent=padre)
    for pagina in escritor.pages:
        pagina.compress_content_streams(level=9)
    escritor.compress_identical_objects(remove_duplicates=True, remove_unreferenced=True)
    escritor.page_mode = "/UseOutlines"   # que el visor abra con el panel de marcadores
    escritor.add_metadata({"/Title": "Manual de Arquitectura del Homelab", "/Author": "Lucas D. Gómez"})
    with open(SALIDA, "wb") as fh:
        escritor.write(fh)
    print("PDF listo:", SALIDA, f"({os.path.getsize(SALIDA) // 1024} KB)")


if __name__ == "__main__":
    main()
