"""Diagnóstico del Excel (NO envía nada, NO usa el modelo).

Descarga el Excel del correo MÁS RECIENTE del remitente (ignorando la etiqueta
'procesado'), lo extrae con la misma lógica del pipeline y reporta:
  - nº de hojas y forma (filas x columnas) tras compactar,
  - si aparecen tokens del trimestre actual (1Q26 / 1T26 / 2026 / mar...),
  - la COLA del texto (donde suelen estar los periodos recientes).

Uso:
    python debug_excel.py
"""

from __future__ import annotations

import os
import tempfile

from dotenv import load_dotenv

load_dotenv()

import imaplib  # noqa: E402

import pandas as pd  # noqa: E402

from src.classify import classify  # noqa: E402
from src.config import Settings  # noqa: E402
from src.extract import SHEET_MARKER, extract_text  # noqa: E402
from src.gmail_ingest import _decode_mime  # noqa: E402

TOKENS = ["1q26", "1q2026", "1t26", "1t2026", "2026", "mar-26", "mar 2026", "march 2026"]


def main() -> None:
    s = Settings.from_env()
    imap = imaplib.IMAP4_SSL(s.imap_host)
    imap.login(s.gmail_user, s.gmail_app_password)
    try:
        imap.select("INBOX")
        query = f"from:{s.sender_email} has:attachment filename:xlsx"
        typ, data = imap.uid("SEARCH", None, "X-GM-RAW", f'"{query}"')
        uids = (data[0] or b"").split()
        if not uids:
            print("No se encontró ningún correo con .xlsx del remitente.")
            return
        uid = uids[-1].decode()  # el más reciente
        print(f"Correo más reciente con Excel: UID {uid}")

        typ, data = imap.uid("FETCH", uid, "(BODY.PEEK[])")
        import email as email_mod

        msg = email_mod.message_from_bytes(data[0][1])
        tmp = tempfile.mkdtemp()
        xlsx_path = None
        for part in msg.walk():
            fn = _decode_mime(part.get_filename())
            if fn and classify(fn)["kind"] == "excel":
                xlsx_path = os.path.join(tmp, fn)
                with open(xlsx_path, "wb") as fh:
                    fh.write(part.get_payload(decode=True))
                print(f"Excel: {fn}")
                break
        if not xlsx_path:
            print("El correo no traía .xlsx.")
            return
    finally:
        try:
            imap.logout()
        except Exception:
            pass

    # --- Forma por hoja (tras compactar igual que la extracción) ---
    print("\n== Hojas (tras quitar filas/columnas vacías) ==")
    sheets = pd.read_excel(xlsx_path, sheet_name=None, engine="openpyxl", header=None)
    for name, df in sheets.items():
        df2 = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
        print(f"  - {name!r}: {df.shape} -> {df2.shape}")

    # --- Texto extraído real ---
    text = extract_text(xlsx_path, "excel")
    low = text.lower()
    print(f"\n== Texto extraído: {len(text)} chars, {text.count(SHEET_MARKER)} hoja(s) ==")
    print("== ¿Aparecen tokens del trimestre actual? ==")
    for t in TOKENS:
        print(f"  {t!r:16} -> {low.count(t)} ocurrencia(s)")

    print("\n== COLA del texto extraído (últimos 2000 chars) ==")
    print(text[-2000:])


if __name__ == "__main__":
    main()
