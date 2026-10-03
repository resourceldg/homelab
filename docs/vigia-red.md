# Robustez ante caídas (`vigia_red`)

El servidor está en una casa, con un WiFi USB viejo y sin nadie cerca para
reiniciarlo. Este rol hace que **se recupere solo** de las caídas que puede
arreglar, y que **deje evidencia** de las que no, para entender cada una después.

Se aplica con `--tags vigia-red` (también entra en `--tags network`).

## Por qué existe

El 2026-10-03 el servidor estuvo **dos horas fuera de línea**. El diario del
sistema se cortó en seco a las 12:48:30, sin apagado, y recién volvió cuando
alguien lo prendió a las 14:40. La máquina **se congeló o se quedó sin luz**: no
fue la red. Ningún programa puede actuar en una máquina congelada, así que hace
falta una capa **por debajo** del sistema operativo: el watchdog de hardware.

Caso completo, para alumnos: [capítulo 10, caso 10](handbook/10-casos-practicos.md).

## Las capas

```mermaid
flowchart TB
  C0["0 · Watchdog de hardware<br/>congelamiento → el chip reinicia en 30 s"]
  C1["1 · Energía<br/>corte de luz → BIOS: encender al volver (manual)"]
  C2["2 · Enlace<br/>WiFi sin ahorro de energía · cable si hay"]
  C3["3 · Guardián de red (cada minuto)<br/>sin router → escalera de arreglos"]
  C4["4 · Tailscale<br/>internet sí, tailnet no → reinicia tailscaled"]
  C5["5 · Evidencia<br/>diario cada 30 s · latido · resumen al arrancar"]
  C6["6 · Vigía externo (notebook)<br/>avisa y arma el informe cuando vuelve"]
  C0 --> C1 --> C2 --> C3 --> C4 --> C5 --> C6
```

| Capa | Ante qué | Qué hace | Dónde |
|---|---|---|---|
| **0 · Watchdog de hardware** | la máquina se **congela** | systemd le da señal al chip iTCO de la placa (ASRock H81M) cada pocos segundos; si deja de llegar 30 s, el chip **reinicia** el equipo. Si un reinicio se cuelga, lo fuerza a los 5 min | `/etc/modules-load.d/vigia-watchdog.conf`, `/etc/systemd/system.conf.d/50-vigia-watchdog.conf` |
| **1 · Energía** | corte de luz | BIOS: **Restore on AC/Power Loss → Power On** (ver abajo, es manual) | BIOS |
| **2 · Enlace** | el WiFi USB "se duerme" | ahorro de energía del WiFi **apagado** | `/etc/NetworkManager/conf.d/50-vigia-wifi-powersave.conf` |
| **3 · Guardián de red** | no responde el router | escalera (minutos seguidos sin router): **3** reconectar → **6** reiniciar NetworkManager → **10** resetear el USB del adaptador → **14** probar otras redes guardadas → **30** reiniciar el servidor (último recurso) | `/usr/local/sbin/vigia-red`, timer `vigia-red.timer` |
| **4 · Tailscale** | hay internet pero no tailnet | 3 min así → reinicia `tailscaled` (y cada 10 min si sigue) | idem |
| **5 · Evidencia** | entender después | diario en disco cada 30 s; **latido** por minuto; **resumen** del arranque anterior en cada arranque | `/var/lib/vigia-red/latido`, `/var/log/homelab/arranques/`, `/var/log/homelab/vigia-red.log` |
| **6 · Vigía externo** | el servidor no está | desde la notebook: avisa, y cuando vuelve arma el informe | `scripts/diagnosticar-caida.sh` (cron) |

### Decisiones que no se ven en el código

- **Si responde el router pero no internet, no se toca nada.** El problema está
  afuera (router o proveedor): reiniciar nuestro WiFi no lo arregla y suma ruido.
- **El reinicio por falta de red es el último recurso y tiene límites:** recién a
  los 30 min, nunca en los primeros 20 min de encendido (evita bucles de
  reinicio), y como mucho uno cada 6 h. Con `vigia_red_reinicio_min: 0` se apaga.
- **El watchdog solo se arma si el chip existe.** Si `/dev/watchdog0` no aparece,
  la capa queda apagada y el play lo dice.
- **Se probó sin tocar nada real:** `tests/test_vigia_red.py` simula red sana,
  internet caído afuera, la escalera minuto a minuto, el reinicio con sus límites
  y Tailscale caído.
- **El diagnóstico automático también se equivoca.** La primera versión contó el
  cierre de una sesión SSH como "apagado ordenado". Ahora solo cuenta el gestor
  del **sistema** (`systemd[1]`); el caso quedó como test de regresión mental en el
  manual.

## Lo que hay que hacer a mano (no se puede desde Ansible)

1. **BIOS → encender al volver la luz.** En la ASRock H81M-VG4: entrar al BIOS
   (F2 o Supr al arrancar) → *Advanced* → *Chipset Configuration* →
   **Restore on AC/Power Loss** → **Power On**. Sin esto, después de un corte de
   luz el servidor **se queda apagado** hasta que alguien vaya.
2. **Un cable de red.** La placa tiene Ethernet (`enp2s0`) sin usar. Enchufado,
   NetworkManager lo prefiere solo (métrica 100 contra 600 del WiFi) y el WiFi
   queda de respaldo. Es la mejora más grande que se puede hacer.
3. **Cambiar el adaptador WiFi.** El actual es un **RTL8187B** (802.11g, 54 Mbps,
   de hace más de 15 años). Cualquier adaptador moderno con buen soporte en Linux
   es más estable.
4. **Una UPS** (batería) chica, si los cortes de luz son frecuentes.

## Comprobar que anda

```bash
# En el servidor
systemctl show -p RuntimeWatchdogUSec -p WatchdogDevice   # 30s · /dev/watchdog0
sudo wdctl | grep -E "Timeleft|Timeout"                  # Timeleft baja y se renueva
systemctl list-timers vigia-red.timer                    # corre cada minuto
sudo cat /var/lib/vigia-red/latido                       # hora del último latido
sudo tail /var/log/homelab/vigia-red.log                 # qué hizo (vacío = red sana)
sudo sh -c 'cat $(ls -1t /var/log/homelab/arranques/*.txt | head -1)'   # último resumen
iw dev wlx00085492a428 get power_save                    # Power save: off
```

## Ajustes

Variables en `ansible/roles/vigia_red/defaults/main.yml` (se pisan en el
inventario): minutos de cada paso, reinicio (`vigia_red_reinicio_min`, `0` =
nunca), límite de reinicios, minutos de gracia al arrancar, Tailscale y destinos
para comprobar internet. Se vuelcan en `/etc/default/vigia-red`.
