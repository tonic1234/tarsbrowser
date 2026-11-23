# Changelog

## 1.1.0
- **macOS y Linux**: detección de sistema en el host remoto (`uname -s`) y lanzadores
  `arrancar-macos.sh` / `arrancar-linux.sh`. El perfil y la geometría se resuelven por sistema.
- **`sistema`**: informe de host, SO, Chrome, perfil, geometría y estado de CDP.
- **`ventana <izq,arriba,ancho,alto|0>`**: fija la geometría y la persiste en `config.json`
  (el env `TARS_BOUNDS` sigue mandando).
- Decodificación de salida tolerante a Windows (cp850) y a UTF-8.
- Tests sin red + CI en Ubuntu/macOS/Windows.

## 1.0.0
- Primera versión: `abrir`, `estado`, `nav`, `captura`, `buscar`, `imagenes`, `bajar`, `clic`,
  `apuntar`, `demo`, `escribir`, `login`, `tipear_secreto`, `cursor`, `cerrar`.
- Cursor dibujado con movimiento en curva, recuadro del objetivo y etiqueta de la acción.
- Descargas autónomas por `Browser.setDownloadBehavior`.
- Login con el buzón de secretos (la clave nunca se imprime).
