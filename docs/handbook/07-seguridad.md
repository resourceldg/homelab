# 7. Seguridad (defensa en profundidad)

🎯 **Objetivo:** entender cómo se protege el laboratorio en varias capas, de modo
que si una falla, otra sigue cubriendo.

🧩 **Prerequisitos:** [cap. 2](02-fundamentos.md).

> 📝 **Capítulo en desarrollo.**

## Temario
- **Defensa en profundidad:** no confiar en una sola barrera. Varias capas
  independientes.
- **SSH y claves:** clave pública/privada, por qué no se usan contraseñas, el
  diseño anti-lockout (bootstrap separado del "lockdown").
- **Firewall (UFW):** default-deny; solo se abren los puertos necesarios; el cierre
  del bypass de Docker con `ufw-docker`.
- **Fail2ban:** banea IPs que intentan entrar por fuerza bruta.
- **AppArmor:** limita qué puede hacer cada programa.
- **Hardening del kernel/SO:** sysctl, políticas de contraseñas, blacklist de
  módulos.
- **Tailscale:** acceso remoto privado sin exponer puertos; Tailscale SSH vs.
  OpenSSH; el modo `check` de la ACL.
- **Authelia (SSO):** login único con **grupos** (operators/students/family);
  `forward_auth` en Caddy; qué ve cada grupo.
- **Least privilege:** los alumnos sin sudo/docker/socket; cuentas de servicio
  separadas.

## Ideas clave (adelanto)
- Ninguna capa sola alcanza; el conjunto es lo robusto.
- El acceso web se controla en Caddy + Authelia; el de terminal, con SSH + Tailscale.

*(Resumen, errores comunes, preguntas y ejercicios: al completar el capítulo.)*
