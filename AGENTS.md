# AGENTS.md

Руководство для разработчиков и ИИ-агентов, работающих с этим репозиторием.

## Проект

Кастомная интеграция Home Assistant `novatek_em12x` (Novatek Electro EM-12x).
Код: `custom_components/novatek_em12x/`. Тесты: `tests/` (без реального железа).
Документация пользователя: `README.md`, история версий: `CHANGELOG.md`.

## Обязательные проверки перед коммитом

```bash
ruff check .
pytest
python3 -m py_compile custom_components/novatek_em12x/*.py
```

Все три должны быть зелёными. CI (GitHub Actions, `.github/workflows/validate.yml`)
дополнительно запускает HACS-валидацию и hassfest.

## Правила коммитов

- Только локальные коммиты по явной просьбе; не пушить без запроса.
- Один логический пункт — один коммит; сообщение по-английски, кратко, с сутью.
- Не добавлять секреты/токены в файлы и не печатать их.

## Правила релиза

1. **Версия и тег — только на финальном коммите.** Сначала весь код и тесты,
   затем последним коммитом поднять `version` в `manifest.json` и обновить
   `CHANGELOG.md`. После этого не должно быть коммитов до создания тега.
2. **Перед релизом проверить, что тег не существует** (не переиспользовать):

   ```bash
   git ls-remote --tags origin | grep -E "refs/tags/v<ВЕРСИЯ>$" || echo "tag is free"
   # либо через API:
   curl -s https://api.github.com/repos/vedga/ha-novatek-em12x/git/ref/tags/v<ВЕРСИЯ>
   ```

3. Версия в `manifest.json` должна совпадать с тегом: тег `vX.Y.Z` ↔ `version: X.Y.Z`.
4. Сначала push в `main`, дождаться зелёного CI, затем создать релиз
   (тег + релиз через API/веб). Для default-списка HACS релиз должен быть
   создан **после** успешного прогона Actions.
5. Теги неизменяемы: новые коммиты после тега в релиз не попадают — для них
   нужен новый тег/версия.

Готовый скрипт проверки: `scripts/release_check.sh <версия>`.

## Тесты

- `tests/test_api.py` — клиент API на локальном эмуляторе устройства (aiohttp).
- `tests/test_journals.py`, `tests/test_billing.py` — чистые хелперы.
- `tests/test_config_flow_smoke.py`, `tests/test_auto_on_smoke.py`,
  `tests/test_billing_smoke.py` — smoke-тесты на стабах Home Assistant.
- `tests/test_ha_contract.py` — AST-стражи (имена HA, `get`/`vol` аргументы,
  паритет ключей схемы и переводов, единицы).
- Тесты **не ходят на реальное оборудование**; живая проверка — отдельный
  скрипт `scripts/live_device_check.py` (запускается вручную).

## Локализация

`strings.json` — базовый (en). Полные паритетные переводы: `translations/en.json`,
`ru.json`, `pl.json`, `uk.json` (языки прошивки прибора). При добавлении ключей
обновлять все файлы; паритет проверяется тестом.
