// Captura qué pide la vista PÚBLICA de los tableros, con un navegador real.
//
// Para qué: la lista de rutas permitidas de publico/Caddyfile salió de acá. Al
// actualizar ThingsBoard, la interfaz puede empezar a usar rutas nuevas: se
// vuelve a correr esto CONTRA THINGSBOARD DIRECTO (sin el proxy) y se compara
// con la lista. Ver docs/thingsboard.md, "Al actualizar ThingsBoard".
//
// Uso (Node + playwright-core + un Chromium):
//   CHROME=/ruta/a/chrome NODE_PATH=/ruta/a/node_modules \
//     node capturar-rutas-publicas.js /srv/tableros/.tableros.json http://127.0.0.1:18080 /tmp/capturas
//
// Imprime "MÉTODO /ruta" (los ids reemplazados por {id}) con la cantidad de
// pedidos, los WebSocket y los tipos de comando que manda por el WebSocket.
// Deja una captura de pantalla de cada tablero en el tercer argumento.
const { chromium } = require('playwright-core');
const fs = require('fs');

(async () => {
  const [tableros, base, capturas] = process.argv.slice(2);
  const urls = JSON.parse(fs.readFileSync(tableros))
    .filter(t => t.publico)
    .map(t => t.url.replace(/^https?:\/\/[^/]+/, base));
  const browser = await chromium.launch({ executablePath: process.env.CHROME });
  const vistos = new Map();
  const anotar = k => vistos.set(k, (vistos.get(k) || 0) + 1);

  for (const [i, url] of urls.entries()) {
    const page = await browser.newPage();
    page.on('request', r => {
      const ruta = new URL(r.url()).pathname.replace(/[0-9a-f]{8}-[0-9a-f-]{27}/g, '{id}');
      anotar(`${r.method()} ${ruta}`);
    });
    page.on('websocket', ws => {
      anotar(`WS ${new URL(ws.url()).pathname}`);
      ws.on('framesent', f => {
        try {
          const j = JSON.parse(f.payload);
          anotar(`WS-CMD ${(j.cmds || []).map(c => c.type).join(',') || Object.keys(j).join(',')}`);
        } catch (e) { /* frame no JSON */ }
      });
    });
    await page.goto(url, { waitUntil: 'networkidle', timeout: 90000 });
    await page.waitForTimeout(15000);
    if (capturas) await page.screenshot({ path: `${capturas}/${i}.png`, fullPage: true });
    await page.close();
  }
  await browser.close();
  for (const [k, n] of [...vistos.entries()].sort()) console.log(k.padEnd(90), n);
})();
