import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import agent_tools
import ollama_client


def _isolated_agenda(monkeypatch, tmp_path):
    path = tmp_path / 'agenda.json'
    path.write_text('[]', encoding='utf-8')
    monkeypatch.setattr(agent_tools, 'AGENDA_FILE', path)
    return path


def test_relative_dates_and_times_are_normalized():
    today = datetime.date(2026, 11, 10)  # martes
    assert agent_tools.normalize_date('Mañana', today) == '2026-11-11'
    assert agent_tools.normalize_date('viernes', today) == '2026-11-13'
    assert agent_tools.normalize_date('12 de noviembre', today) == '2026-11-12'
    assert agent_tools.normalize_date('2026-12-24', today) == '2026-12-24'
    assert agent_tools.normalize_time('4 de la tarde') == '16:00'
    assert agent_tools.normalize_time('') == ''


def test_model_tag_is_saved_and_visible_in_upcoming(monkeypatch, tmp_path):
    _isolated_agenda(monkeypatch, tmp_path)
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    text, action = agent_tools.process_agent_actions('Anotado. [AGREGAR_AGENDA: Comprar pan|mañana|4 pm]')
    assert text == 'Anotado.'
    assert action['item']['date'] == tomorrow and action['item']['time'] == '16:00'
    assert 'Comprar pan' in agent_tools.get_upcoming_agenda_text()


def test_fallback_add_request_is_not_treated_as_listing(monkeypatch, tmp_path):
    _isolated_agenda(monkeypatch, tmp_path)
    reply = ollama_client.query_fallback('agenda una cita con el dentista mañana a las 5 de la tarde', None, None, 0)
    _, action = agent_tools.process_agent_actions(reply)
    assert action is not None
    assert action['item']['time'] == '17:00'
