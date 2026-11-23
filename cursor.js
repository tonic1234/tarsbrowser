// Cursor dibujado para el Chrome de TARS.
// El movimiento lo maneja el cliente CDP (Python) enviando eventos de mouse reales a lo largo
// de una curva; acá sólo se pinta: flecha, recuadro del objetivo, etiqueta y onda en el clic.
// Todo con animaciones CSS (no requestAnimationFrame) para que ande igual con la ventana
// sin foco. pointer-events:none: no intercepta nada y NO mueve el puntero real del sistema.
(() => {
  const VERSION = '3';
  if (window.__tarsCursor && window.__tarsCursor.version === VERSION
      && document.getElementById('__tars_cursor')) return 'ya';
  // Versión vieja en la página (o nodos huérfanos): se limpia y se reinstala.
  try {
    document.querySelectorAll('#__tars_cursor, .__tars_foco, .__tars_etiqueta, .__tars_rastro, .__tars_onda')
      .forEach((n) => n.remove());
    window.__tarsCursorInstalado = false;
  } catch (e) {}

  const ID = '__tars_cursor';
  let instalado = false;

  function instalar() {
    if (document.getElementById(ID)) { window.__tarsCursorInstalado = true; return 'ya'; }
    const raiz = document.body || document.documentElement;
    if (!raiz) return 'sin-raiz';

    const estilo = document.createElement('style');
    estilo.id = '__tars_cursor_estilo';
    estilo.textContent = `
      #${ID} { position: fixed; left: 0; top: 0; width: 20px; height: 28px;
        pointer-events: none; z-index: 2147483647; will-change: left, top;
        filter: drop-shadow(0 2px 4px rgba(0,0,0,.65)); }
      .__tars_rastro { position: fixed; width: 7px; height: 7px; border-radius: 50%;
        background: #ff7a1a; pointer-events: none; z-index: 2147483645;
        transform: translate(-50%, -50%); animation: __tars_rastro_fx .55s ease-out forwards; }
      @keyframes __tars_rastro_fx { from { opacity: .28; } to { opacity: 0; transform: translate(-50%,-50%) scale(.25); } }
      .__tars_onda { position: fixed; width: 16px; height: 16px; border-radius: 50%;
        border: 3px solid #ff7a1a; background: rgba(255,122,26,.10); pointer-events: none; z-index: 2147483646;
        transform: translate(-50%, -50%);
        animation: __tars_onda_fx 1.5s cubic-bezier(.2,.7,.3,1) forwards; }
      @keyframes __tars_onda_fx {
        from { opacity: .95; transform: translate(-50%,-50%) scale(.35); }
        to   { opacity: 0;   transform: translate(-50%,-50%) scale(3.6); }
      }
      .__tars_foco { position: fixed; pointer-events: none; z-index: 2147483644;
        border: 2px solid #ff7a1a; border-radius: 6px; opacity: 0;
        box-shadow: 0 0 0 3px rgba(255,122,26,.18), inset 0 0 0 1px rgba(255,122,26,.35);
        transition: opacity .16s ease; }
      .__tars_foco.__tars_escribiendo { animation: __tars_pulso 1.1s ease-in-out infinite; }
      @keyframes __tars_pulso {
        0%,100% { box-shadow: 0 0 0 3px rgba(255,122,26,.16), inset 0 0 0 1px rgba(255,122,26,.35); }
        50%     { box-shadow: 0 0 0 7px rgba(255,122,26,.05), inset 0 0 0 1px rgba(255,122,26,.6); }
      }
      .__tars_etiqueta { position: fixed; pointer-events: none; z-index: 2147483647;
        background: rgba(15,15,17,.93); color: #fff; border: 1px solid rgba(255,122,26,.55);
        font: 600 11px/1.35 -apple-system, "Segoe UI", Roboto, sans-serif; padding: 3px 7px;
        border-radius: 5px; letter-spacing: .2px; opacity: 0; white-space: nowrap;
        transition: opacity .16s ease; transform: translate(16px, 20px); max-width: 60vw;
        overflow: hidden; text-overflow: ellipsis; }
    `;
    raiz.appendChild(estilo);

    const cursor = document.createElement('div');
    cursor.id = ID;
    cursor.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="28" viewBox="0 0 20 28">' +
      '<path d="M2.2 1.4 L2.2 22.3 L7.9 16.9 L11.2 25.2 L14.8 23.8 L11.5 15.6 L19.2 15.3 Z" ' +
      'fill="#ffffff" stroke="#111111" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    const foco = document.createElement('div');
    foco.className = '__tars_foco';
    const etiqueta = document.createElement('div');
    etiqueta.className = '__tars_etiqueta';
    raiz.appendChild(cursor);
    raiz.appendChild(foco);
    raiz.appendChild(etiqueta);
    cursor.style.left = (window.innerWidth / 2) + 'px';
    cursor.style.top = (window.innerHeight / 2) + 'px';

    const actual = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
    let ultimoRastro = 0;

    const pintar = (x, y) => {
      actual.x = x; actual.y = y;
      cursor.style.left = x + 'px';
      cursor.style.top = y + 'px';
      etiqueta.style.left = x + 'px';
      etiqueta.style.top = y + 'px';
    };

    const cajaActual = () => (document.body || document.documentElement);

    const rastro = (x, y) => {
      const ahora = performance.now();
      if (ahora - ultimoRastro < 55) return;
      ultimoRastro = ahora;
      const d = document.createElement('div');
      d.className = '__tars_rastro';
      d.style.left = x + 'px';
      d.style.top = y + 'px';
      cajaActual().appendChild(d);
      setTimeout(() => d.remove(), 620);
    };

    const onda = (x, y) => {
      const d = document.createElement('div');
      d.className = '__tars_onda';
      d.style.left = x + 'px';
      d.style.top = y + 'px';
      cajaActual().appendChild(d);
      setTimeout(() => d.remove(), 1600);
    };

    window.addEventListener('mousemove', (e) => { pintar(e.clientX, e.clientY); rastro(e.clientX, e.clientY); }, true);
    window.addEventListener('mousedown', (e) => { pintar(e.clientX, e.clientY); onda(e.clientX, e.clientY); }, true);
    window.addEventListener('mouseup', (e) => { pintar(e.clientX, e.clientY); }, true);
    window.addEventListener('wheel', () => {
      etiqueta.textContent = 'scroll';
      etiqueta.style.opacity = '1';
      setTimeout(() => { etiqueta.style.opacity = '0'; }, 420);
    }, true);

    window.__tarsCursor = {
      version: VERSION,
      mover: (x, y) => { pintar(x, y); return true; },
      apuntar: (r, texto, tipo) => {
        if (!r) { foco.style.opacity = '0'; return false; }
        foco.style.left = (r.left - 4) + 'px';
        foco.style.top = (r.top - 4) + 'px';
        foco.style.width = (r.width + 8) + 'px';
        foco.style.height = (r.height + 8) + 'px';
        foco.style.opacity = '1';
        foco.classList.toggle('__tars_escribiendo', tipo === 'escribiendo');
        if (texto !== undefined) {
          etiqueta.textContent = texto || '';
          etiqueta.style.opacity = texto ? '1' : '0';
        }
        return true;
      },
      onda: (x, y) => { onda(x, y); return true; },
      etiqueta: (t) => { etiqueta.textContent = t || ''; etiqueta.style.opacity = t ? '1' : '0'; return true; },
      limpiar: () => { foco.style.opacity = '0'; etiqueta.style.opacity = '0';
                       foco.classList.remove('__tars_escribiendo'); return true; },
      visible: (v) => { cursor.style.display = v ? 'block' : 'none';
                        if (!v) { foco.style.opacity = '0'; etiqueta.style.opacity = '0'; } return true; },
      posicion: () => ({ x: Math.round(actual.x), y: Math.round(actual.y) }),
      ocupado: () => false,
    };

    if (!window.__tarsCursorLatido) {
      window.__tarsCursorLatido = setInterval(() => {
        const r = document.body || document.documentElement;
        if (!r) return;
        if (!document.getElementById(ID)) r.appendChild(cursor);
        if (!foco.isConnected) r.appendChild(foco);
        if (!etiqueta.isConnected) r.appendChild(etiqueta);
        if (!estilo.isConnected) r.appendChild(estilo);
      }, 1200);
    }
    window.__tarsCursorInstalado = true;
    instalado = true;
    return 'instalado';
  }

  let intentos = 0;
  const intentar = () => {
    try {
      const r = instalar();
      if (r === 'sin-raiz' && intentos++ < 40) setTimeout(intentar, 100);
    } catch (e) {
      if (intentos++ < 40) setTimeout(intentar, 150);
    }
  };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', intentar, { once: true });
    intentar();
  } else {
    intentar();
  }
  return instalado ? 'instalado' : 'ok';
})();
