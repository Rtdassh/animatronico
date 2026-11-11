#!/usr/bin/env python3
"""
=============================================================================
HERRAMIENTAS DE AGENTE Y GESTIÓN DE AGENDA / FECHA PARA V DE VENGANZA
Proyecto: Cabeza Animatrónica con IA Local
=============================================================================
Proporciona capacidades de agente para:
  1. Consulta de fecha y hora exacta con conmemoraciones históricas (5 de noviembre).
  2. Gestión de agenda, citas, misiones y recordatorios persistentes en JSON.
  3. Contexto dinámico en tiempo real para el modelo de lenguaje Ollama.
  4. Ejecución de acciones agénticas (agregar tareas, listar compromisos).
=============================================================================
"""

import os
import json
import uuid
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
AGENDA_FILE = DATA_DIR / "agenda.json"

DIAS_SEMANA = [
    "lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"
]

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
]


def _sin_tildes(text: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def normalize_date(value: Optional[str], today: Optional[datetime.date] = None) -> str:
    """Convierte 'hoy', 'mañana', 'viernes', '12 de noviembre', '12/11', ISO... a AAAA-MM-DD."""
    import re
    today = today or datetime.date.today()
    if not value or not value.strip():
        return today.isoformat()
    v = _sin_tildes(value.strip().lower())
    try:
        return datetime.date.fromisoformat(v[:10]).isoformat()
    except ValueError:
        pass
    if "pasado manana" in v:
        return (today + datetime.timedelta(days=2)).isoformat()
    if "manana" in v and not re.search(r"\d+\s*(?:de la|en la)?\s*manana", v):
        return (today + datetime.timedelta(days=1)).isoformat()
    if "hoy" in v:
        return today.isoformat()
    m = re.search(r"en (\d+) dias?", v)
    if m:
        return (today + datetime.timedelta(days=int(m.group(1)))).isoformat()
    meses = [_sin_tildes(x) for x in MESES]
    m = re.search(r"(\d{1,2})\s*de\s*([a-z]+)(?:\s*(?:de|del)?\s*(\d{4}))?", v)
    if m and m.group(2) in meses:
        return _future_date(today, int(m.group(1)), meses.index(m.group(2)) + 1, m.group(3))
    m = re.search(r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?", v)
    if m:
        year = m.group(3)
        if year and len(year) == 2:
            year = "20" + year
        return _future_date(today, int(m.group(1)), int(m.group(2)), year)
    for i, dia in enumerate(DIAS_SEMANA):
        if _sin_tildes(dia) in v:
            delta = (i - today.weekday()) % 7 or 7  # el próximo día con ese nombre
            return (today + datetime.timedelta(days=delta)).isoformat()
    return today.isoformat()


def _future_date(today, day, month, year=None) -> str:
    try:
        date = datetime.date(int(year) if year else today.year, month, day)
        if not year and date < today:
            date = date.replace(year=today.year + 1)
        return date.isoformat()
    except ValueError:
        return today.isoformat()


def normalize_time(value: Optional[str]) -> str:
    """Convierte '16:00', '4 pm', '4 de la tarde', '9:30 de la mañana', 'mediodía' a HH:MM ('' si no hay hora)."""
    import re
    if not value or not value.strip():
        return ""
    v = _sin_tildes(value.strip().lower())
    if "mediodia" in v:
        return "12:00"
    if "medianoche" in v:
        return "00:00"
    m = re.search(r"(\d{1,2})(?:[:.h](\d{2}))?", v)
    if not m:
        return ""
    hour, minute = int(m.group(1)), int(m.group(2) or 0)
    if any(w in v for w in ("pm", "p.m", "tarde", "noche")) and hour < 12:
        hour += 12
    if any(w in v for w in ("am", "a.m", "madrugada", "manana")) and hour == 12:
        hour = 0
    if "y media" in v:
        minute = 30
    elif "y cuarto" in v:
        minute = 15
    if hour > 23 or minute > 59:
        return ""
    return f"{hour:02d}:{minute:02d}"


def _init_default_agenda():
    """Inicializa la agenda con entradas temáticas por defecto si no existe."""
    today = datetime.date.today().isoformat()
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()

    default_items = [
        {
            "id": "item_1",
            "title": "Calibración de la mirada y mecanismo ocular de precisión",
            "date": today,
            "time": "10:00",
            "category": "sistema"
        },
        {
            "id": "item_2",
            "title": "Audiencia vespertina con mi estimado interlocutor",
            "date": today,
            "time": "18:00",
            "category": "reunión"
        },
        {
            "id": "item_3",
            "title": "Inspección de ideales y lectura de literatura libertaria",
            "date": tomorrow,
            "time": "15:30",
            "category": "misión"
        }
    ]
    with open(AGENDA_FILE, "w", encoding="utf-8") as f:
        json.dump(default_items, f, ensure_ascii=False, indent=2)


def load_agenda() -> List[Dict[str, Any]]:
    """Carga la lista de eventos y tareas de la agenda."""
    if not AGENDA_FILE.exists():
        _init_default_agenda()

    try:
        with open(AGENDA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_agenda(items: List[Dict[str, Any]]) -> bool:
    """Guarda la agenda en disco."""
    try:
        with open(AGENDA_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def add_agenda_item(title: str, date_str: Optional[str] = None, time_str: Optional[str] = None, category: str = "general") -> Dict[str, Any]:
    """Añade un nuevo evento o recordatorio a la agenda."""
    items = load_agenda()
    today_iso = datetime.date.today().isoformat()
    now_time = datetime.datetime.now().strftime("%H:%M")

    new_item = {
        "id": f"item_{uuid.uuid4().hex[:6]}",
        "title": title.strip(),
        "date": normalize_date(date_str),
        "time": normalize_time(time_str),
        "category": category
    }
    items.append(new_item)
    save_agenda(items)
    return new_item


def delete_agenda_item(item_id: str) -> bool:
    """Elimina un elemento de la agenda por su identificador."""
    items = load_agenda()
    new_items = [it for it in items if it.get("id") != item_id]
    if len(new_items) != len(items):
        save_agenda(new_items)
        return True
    return False


def get_current_datetime_info() -> Dict[str, Any]:
    """Obtiene la fecha y hora actual en español con contexto de V de Venganza."""
    now = datetime.datetime.now()
    dia_sem = DIAS_SEMANA[now.weekday()]
    dia = now.day
    mes = MESES[now.month - 1]
    anio = now.year
    hora = now.strftime("%H:%M")

    # Referencia especial de V de Venganza al 5 de noviembre
    nov5_note = ""
    if now.month == 11 and now.day == 5:
        nov5_note = "¡Hoy es el glorioso 5 de noviembre! ¡El día de la conspiración de la pólvora y el triunfo de los ideales inmunes a las balas!"
    elif now.month == 11:
        diff = now.day - 5
        if diff > 0:
            nov5_note = f"Nos encontramos en noviembre, a {diff} días de nuestra conmemoración del 5 de noviembre."
        else:
            nov5_note = f"Nos encontramos en noviembre, a pocos días del sagrado 5 de noviembre."

    texto_fecha = f"Hoy es {dia_sem}, {dia} de {mes} del año {anio}, y el reloj marca exactamente las {hora}."

    return {
        "dia_semana": dia_sem,
        "dia": dia,
        "mes": mes,
        "anio": anio,
        "hora": hora,
        "texto_fecha": texto_fecha,
        "nov5_note": nov5_note,
        "iso_date": now.date().isoformat()
    }


def get_agenda_summary_for_today() -> str:
    """Genera un resumen en prosa de los eventos programados para hoy."""
    today_iso = datetime.date.today().isoformat()
    items = load_agenda()
    today_items = [it for it in items if it.get("date") == today_iso]

    if not today_items:
        return "Para hoy no hay compromisos agendados en nuestros registros."

    desc = []
    for it in today_items:
        t = it.get("time", "")
        tit = it.get("title", "")
        desc.append(f"A las {t}: '{tit}'")

    return "Tus compromisos para el día de hoy son: " + "; ".join(desc) + "."


def get_upcoming_agenda_text(days: int = 7) -> str:
    """Compromisos desde hoy hasta dentro de `days` días, ordenados (para el prompt del modelo)."""
    today = datetime.date.today()
    limit = (today + datetime.timedelta(days=days)).isoformat()
    items = sorted((it for it in load_agenda() if today.isoformat() <= str(it.get("date", "")) <= limit),
                   key=lambda it: (it.get("date", ""), it.get("time", "")))
    if not items:
        return "No hay compromisos agendados para los próximos días."
    lines = []
    for it in items:
        d = datetime.date.fromisoformat(it["date"])
        if d == today:
            cuando = "hoy"
        elif d == today + datetime.timedelta(days=1):
            cuando = "mañana"
        else:
            cuando = f"el {DIAS_SEMANA[d.weekday()]} {d.day} de {MESES[d.month - 1]}"
        hora = f" a las {it['time']}" if it.get("time") else ""
        lines.append(f"{cuando}{hora}: {it.get('title')}")
    return "; ".join(lines) + "."


def get_all_agenda_text() -> str:
    """Genera una lista textual de todos los compromisos agendados."""
    items = load_agenda()
    if not items:
        return "La agenda se encuentra completamente libre de compromisos."

    lines = []
    for it in items:
        lines.append(f"- [{it.get('date')} {it.get('time')}]: {it.get('title')}")
    return "\n".join(lines)


def process_agent_actions(text: str) -> tuple[str, Optional[Dict[str, Any]]]:
    """
    Detecta etiquetas de acción generadas por el modelo como [AGREGAR_AGENDA: Título|Fecha|Hora]
    las ejecuta en el sistema y retorna el texto limpio y la acción efectuada.
    """
    action_performed = None
    import re

    added = []
    for match in re.finditer(r'\[AGREGAR_AGENDA:\s*([^\|\]]+)(?:\|([^\|\]]*))?(?:\|([^\]]*))?\]', text):
        title = match.group(1).strip()
        if not title:
            continue
        added.append(add_agenda_item(title=title, date_str=match.group(2), time_str=match.group(3)))
        text = text.replace(match.group(0), "")

    if added:
        action_performed = {"action": "add_agenda", "item": added[0], "items": added}
        print(f"[Agenda] Guardado: {added}", flush=True)
    elif "AGREGAR_AGENDA" in text:
        print(f"[Agenda] Etiqueta mal formada, no se guardó nada: {text!r}", flush=True)

    return text.strip(), action_performed

