Corteris Tender AI — Commit #71 Dashboard Demo Data & Visual Review

Добавлено:
- синтетический набор из 6 KPI;
- 5 демонстрационных тендеров;
- реалистичные AI-рекомендации и предупреждения;
- демонстрационная лента событий;
- включение через demo_mode=True;
- включение через CORTERIS_DASHBOARD_DEMO=1;
- отдельный visual-review launcher;
- кнопка выключения демо-режима;
- чек-лист визуальной проверки;
- автоматические тесты.

Все номера и организации являются вымышленными.

Проверка:
python -m py_compile app/ui/dashboard/demo_data.py
python -m py_compile app/ui/pages/dashboard_page.py
python -m py_compile tools/run_dashboard_demo.py
pytest -q
python tools/run_dashboard_demo.py
