"""
Corre dos chequeos de arbitraje de dolares, usando datos en tiempo real de
ComparaDolar.ar (que refleja los precios reales de cada entidad):

  Chequeo 1: Comprar en Uala vs Vender en Fiwind
    - Compra: "Compras a" en comparadolar.ar/usd/uala
    - Venta:  "Vendes a" en comparadolar.ar/usd/fiwind-cripto
    - Avisa si la ganancia es >= THRESHOLD_ARS_1

  Chequeo 2: (Comprar en Supervielle - 10) vs Vender en Fiwind
    - Compra: "Compras a" en comparadolar.ar/usd/banco-supervielle, menos $10
    - Venta:  "Vendes a" en comparadolar.ar/usd/fiwind-cripto
    - Avisa si la ganancia es >= THRESHOLD_ARS_2

Cada chequeo que supera su umbral manda un mensaje de Telegram por separado,
indicando de cuanto es la diferencia.

Variables de entorno necesarias:
  TELEGRAM_BOT_TOKEN  -> token del bot (te lo da @BotFather)
  TELEGRAM_CHAT_ID    -> tu chat id (te lo da @userinfobot)
  THRESHOLD_ARS_1     -> opcional, default 4.0 (umbral Uala vs Fiwind)
  THRESHOLD_ARS_2     -> opcional, default 4.0 (umbral Supervielle-10 vs Fiwind)
  AJUSTE_SUPERVIELLE  -> opcional, default 10.0 (se resta al precio de Supervielle)
"""

import os
import re
import sys
import json
import urllib.request
import urllib.error

UALA_URL = "https://comparadolar.ar/usd/uala"
FIWIND_URL = "https://comparadolar.ar/usd/fiwind-cripto"
SUPERVIELLE_URL = "https://comparadolar.ar/usd/banco-supervielle"
TELEGRAM_API_TEMPLATE = "https://api.telegram.org/bot{token}/sendMessage"

# Numeros con formato argentino: 1.510,00 (despues de la etiqueta "Compras a" / "Vendes a")
COMPRAS_PATTERN = re.compile(r"Compras a.{0,150}?([\d]{1,3}(?:\.\d{3})*,\d{2})", re.DOTALL)
VENDES_PATTERN = re.compile(r"Vendes a.{0,150}?([\d]{1,3}(?:\.\d{3})*,\d{2})", re.DOTALL)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}


def parse_ar_number(text: str) -> float:
    """Convierte '1.510,00' (formato argentino) a 1510.00 (float)."""
    return float(text.replace(".", "").replace(",", "."))


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def strip_html_tags(html: str) -> str:
    """Saca todas las etiquetas HTML y colapsa espacios, para que la
    etiqueta ('Compras a') y el numero queden cerca en el texto plano."""
    sin_tags = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", sin_tags)


def solo_seccion_principal(texto_plano: str) -> str:
    """Corta el texto antes de la lista 'Otras opciones para operar USD',
    para no confundir el precio de la entidad principal con el de otro
    proveedor listado mas abajo en la misma pagina."""
    corte = texto_plano.find("Otras opciones")
    return texto_plano if corte == -1 else texto_plano[:corte]


def get_precio(url: str, patron: re.Pattern, etiqueta: str) -> float:
    """Descarga una pagina de ComparaDolar.ar y extrae el precio principal
    (compra o venta) segun el patron pasado."""
    html = fetch_text(url)
    seccion = solo_seccion_principal(strip_html_tags(html))
    match = patron.search(seccion)
    if not match:
        raise RuntimeError(
            f"No se pudo encontrar el precio de '{etiqueta}' en {url}. "
            "La pagina puede haber cambiado de estructura."
        )
    return parse_ar_number(match.group(1))


def get_uala_compra() -> float:
    """Precio al que Uala te vende dolares (lo que vos pagas al comprar)."""
    return get_precio(UALA_URL, COMPRAS_PATTERN, "Compras a")


def get_supervielle_compra() -> float:
    """Precio al que Supervielle te vende dolares (lo que vos pagas al comprar)."""
    return get_precio(SUPERVIELLE_URL, COMPRAS_PATTERN, "Compras a")


def get_fiwind_venta() -> float:
    """Precio al que Fiwind te compra dolares (lo que vos recibis al vender)."""
    return get_precio(FIWIND_URL, VENDES_PATTERN, "Vendes a")


def send_telegram_message(token: str, chat_id: str, text: str) -> None:
    url = TELEGRAM_API_TEMPLATE.format(token=token)
    payload = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        print(f"Error enviando mensaje a Telegram: {e.read().decode('utf-8')}", file=sys.stderr)
        raise


def chequear_y_avisar(
    bot_token: str,
    chat_id: str,
    nombre_chequeo: str,
    precio_compra: float,
    precio_venta: float,
    threshold_ars: float,
    detalle_compra: str,
    detalle_venta: str,
) -> None:
    """Calcula la diferencia entre un precio de compra y uno de venta,
    imprime el resultado y manda un aviso a Telegram si supera el umbral."""
    diferencia = precio_venta - precio_compra
    diferencia_pct = (diferencia / precio_compra) * 100

    print(f"--- {nombre_chequeo} ---")
    print(f"{detalle_compra}: {precio_compra:.2f} ARS/USD")
    print(f"{detalle_venta}: {precio_venta:.2f} ARS/USD")
    print(f"Diferencia: {diferencia:.2f} ARS/USD ({diferencia_pct:.2f}%)")

    if diferencia >= threshold_ars:
        mensaje = (
            f"🟢 <b>Oportunidad detectada: {nombre_chequeo}</b>\n\n"
            f"{detalle_compra}: <b>{precio_compra:.2f}</b> ARS/USD\n"
            f"{detalle_venta}: <b>{precio_venta:.2f}</b> ARS/USD\n"
            f"Diferencia: <b>{diferencia:.2f} ARS por dolar ({diferencia_pct:.2f}%)</b>\n\n"
            f"(Umbral configurado: ${threshold_ars:.2f} por dolar)"
        )
        send_telegram_message(bot_token, chat_id, mensaje)
        print("Notificacion enviada.")
    else:
        print("Diferencia por debajo del umbral, no se notifica.")
    print()


def main() -> None:
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    threshold_1 = float(os.environ.get("THRESHOLD_ARS_1", "4.0"))
    threshold_2 = float(os.environ.get("THRESHOLD_ARS_2", "4.0"))
    ajuste_supervielle = float(os.environ.get("AJUSTE_SUPERVIELLE", "10.0"))

    if not bot_token or not chat_id:
        print("Faltan TELEGRAM_BOT_TOKEN y/o TELEGRAM_CHAT_ID en las variables de entorno.", file=sys.stderr)
        sys.exit(1)

    # Se piden los tres precios una sola vez y se reusan en los dos chequeos.
    uala_compra = get_uala_compra()
    supervielle_compra = get_supervielle_compra()
    fiwind_venta = get_fiwind_venta()

    # --- Chequeo 1: Uala vs Fiwind ---
    chequear_y_avisar(
        bot_token,
        chat_id,
        nombre_chequeo="Uala vs Fiwind",
        precio_compra=uala_compra,
        precio_venta=fiwind_venta,
        threshold_ars=threshold_1,
        detalle_compra="Comprar en Uala",
        detalle_venta="Vender en Fiwind",
    )

    # --- Chequeo 2: (Supervielle - ajuste) vs Fiwind ---
    supervielle_ajustado = supervielle_compra - ajuste_supervielle
    chequear_y_avisar(
        bot_token,
        chat_id,
        nombre_chequeo="Supervielle vs Fiwind",
        precio_compra=supervielle_ajustado,
        precio_venta=fiwind_venta,
        threshold_ars=threshold_2,
        detalle_compra=f"Comprar en Supervielle ({supervielle_compra:.2f} - {ajuste_supervielle:.2f})",
        detalle_venta="Vender en Fiwind",
    )


if __name__ == "__main__":
    main()
