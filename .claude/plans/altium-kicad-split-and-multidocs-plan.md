# Plan: rozdzielenie widoków Altium/KiCad + wiele datasheetów na element

## Context

Dwie nowe potrzeby zgłoszone 2026-09-19:

1. **Rozdzielenie Altium / KiCad.** Obecnie istnieje jeden zestaw widoków `public.table_<id>_<nazwa>`,
   w którym obok siebie leżą kolumny surowe dla Altium (`library_ref`, `library_path`,
   `footprint_path_1..3`) i kolumny wyliczane dla KiCada (`Symbols`, `Footprints` w formacie
   `Nick:Name`). Użytkownik Altium widzi kolumny KiCada i odwrotnie — bałagan i źródło pomyłek.

2. **Wiele dokumentów PDF na element** (#18). Mikrokontroler ma zwykle datasheet + application note
   + erratę. Dziś element ma dokładnie jeden PDF (`<uuid>.pdf`, flaga `datasheet` bool).

Ustalenia z użytkownikiem:
- `docs_count` liczy **tylko dokumenty dodatkowe**; główny datasheet nadal śledzi kolumna `datasheet`.
- Izolacja Altium/KiCad przez **osobne schematy + osobne role Postgres** (read-only).

### Kluczowe odkrycie techniczne

KiCad buduje zapytanie jako `SELECT ... FROM "<tablename>"` — całą nazwę opakowuje w **jedną** parę
cudzysłowów (`common/database/database_connection.cpp:571-573`, też `:443-446`). Oznacza to, że
`"kicad.table_1_x"` jest niepoprawne i **nazwy kwalifikowane schematem nie działają w `.kicad_dbl`**.

→ Jedyny działający mechanizm to `ALTER ROLE kicad_user SET search_path = kicad`, czyli rozdzielenie
ról nie jest kosmetyką, tylko warunkiem koniecznym poprawnego działania strony KiCada.

---

## Część A — schematy `altium` / `kicad` + role read-only

### `backend/utils.py` → `dbCreateOrUpdateElementViews`

Przebudowa na dwa zestawy widoków zamiast jednego:

- `CREATE SCHEMA IF NOT EXISTS altium; CREATE SCHEMA IF NOT EXISTS kicad;`
- usunięcie starych widoków z `public.table_*` (sprzątanie po poprzedniej wersji)
- dla każdej kategorii tworzone są **dwa** widoki o tej samej nazwie w dwóch schematach:

| | `altium.table_N_x` | `kicad.table_N_x` |
|---|---|---|
| klucz | `uuid` | `uuid` |
| podstawowe | `part_name`, `manufacturer`, `description`, `value`, `availability` | to samo |
| datasheet | `HelpURL` | `Datasheet` (nazwa rozpoznawana natywnie przez KiCad) |
| symbol/footprint | `library_ref`, `library_path`, `footprint_reference_1..3`, `footprint_path_1..3` | `Symbols`, `Footprints` (format `Nick:Name`) |
| dostawcy | `supplier_*` | `supplier_*` |

Kolumny wyliczane (`HelpURL`/`Datasheet`, `Symbols`, `Footprints`) bez zmian względem obecnej logiki —
przenoszone tylko do właściwego schematu.

### Role Postgres

Nowa funkcja `dbEnsureToolRoles(db_connection)` wołana przy starcie po utworzeniu widoków:

```sql
CREATE ROLE altium_user LOGIN PASSWORD :pwd;   -- idempotentnie, przez DO $$ + pg_roles
ALTER ROLE altium_user SET search_path = altium;
GRANT USAGE ON SCHEMA altium TO altium_user;
GRANT SELECT ON ALL TABLES IN SCHEMA altium TO altium_user;
REVOKE ALL ON SCHEMA kicad FROM altium_user;
```
(analogicznie `kicad_user` ↔ schemat `kicad`)

Uwagi:
- Widoki w Postgresie wykonują się **z uprawnieniami właściciela** (brak `security_invoker`), więc
  `altium_user`/`kicad_user` **nie potrzebują** żadnego dostępu do `private.elements`. To jest
  właściwa granica bezpieczeństwa.
- `GRANT SELECT` trzeba powtarzać **po każdym odtworzeniu widoków** (`DROP VIEW` kasuje granty),
  dlatego `dbEnsureToolRoles` woła się po `dbCreateOrUpdateElementViews`, a nie raz na starcie.
- Hasła z `.env`: `ALTIUM_DB_PASSWORD`, `KICAD_DB_PASSWORD`. Brak zmiennej → pomijamy tworzenie roli
  (graceful, żeby nie wysypać startu na istniejących instalacjach).

### Generatory plików

- `generateAltiumDbLib(...)` — `SchemaName=altium`, `Mode=Read` zamiast `ReadWrite`, `User ID=altium_user`,
  mapowanie FieldMap wyłącznie na kolumny ze schematu `altium`.
- `generateKicadDbl(...)` — `table` jako **niekwalifikowana** nazwa (patrz odkrycie powyżej),
  `username: "kicad_user"`, pole `Datasheet` mapowane na kolumnę `Datasheet`.

---

## Część B — wiele dokumentów (#18)

### Model i migracja

- `backend/models.py`: nowa kolumna `docsCount = Column('docs_count', Integer, nullable=False, default=0, server_default='0')`
  na `Element`. **Usunięcie** modelu `ElementDocument` i relacji `Element.documents`.
- `private.elements` **istnieje**, więc `create_all()` nie doda kolumny → potrzebny jawny, idempotentny DDL
  w `startup_db`:
  ```sql
  ALTER TABLE private.elements ADD COLUMN IF NOT EXISTS docs_count INTEGER NOT NULL DEFAULT 0;
  DROP TABLE IF EXISTS private.element_documents;
  ```
  `element_documents` ma 0 wierszy (zweryfikowane) → usunięcie jest bezstratne.

### Konwencja plików

```
<uuid>.pdf      główny datasheet   → HelpURL / Datasheet w widokach (bez zmian)
<uuid>_1.pdf    Document 1  ┐
<uuid>_2.pdf    Document 2  ├─ docs_count = N, numeracja zawsze ciągła 1..N
<uuid>_N.pdf    Document N  ┘
```

### `backend/main.py`

- `POST /element/{id}/documents` — zapis jako `<uuid>_<docs_count+1>.pdf`, inkrementacja `docs_count`,
  zwraca nowy `docsCount`.
- `DELETE /element/{id}/documents/{index}` — kasuje `<uuid>_<index>.pdf` i **przenumerowuje** pliki
  `index+1..N` w dół o jeden, żeby numeracja została ciągła; dekrementacja `docs_count`.
- `GET /element/{id}/documents` — usunięty; frontend czyta `docsCount` prosto z `GET /element/{id}`.
- `elementDelete` — kasuje też `<uuid>_1..N.pdf`.
- `elementDuplicate` — przy `change_mode == 0` (kopiuj datasheet) kopiuje również dokumenty dodatkowe;
  w pozostałych trybach nowy element startuje z `docs_count = 0`.
- Usunięcie `ElementDocument*` ze `schemas.py`.

`docsCount` **nie trafia** do `ElementBase` (schemat wejściowy create/edit) — klient nie może go
ustawić ręcznie, a `elementEdit` go nie nadpisze. Pojawia się automatycznie w odpowiedzi
`GET /element/{id}`, bo endpoint serializuje cały obiekt ORM.

### Frontend

- `utils/api.js` → `elementDocument`: `upload(uuid, file)`, `delete(uuid, index)`,
  `open(uuid, index)` = `window.open('/files/<uuid>_<index>.pdf')`.
- `components/ElementDocuments.vue` — przepisany: kafelki `Document 1..N` liczone z `docsCount`,
  każdy z przyciskiem Open (+ Delete gdy `!disabled`), pod spodem upload + „Add document".
  Licznik trzymany lokalnie i synchronizowany z odpowiedzi API (prop → `watch` → lokalny `ref`).
- `components/ElementForm.vue` — przekazanie `:docs-count="model.docsCount"`.
- `utils/db.js` (`ElementModel`) — dodanie `docsCount = 0`, żeby pole istniało przed `fillData()`.

### Świadome ograniczenie

Zgodnie z instrukcją („w tabeli dodaj **tylko** pole `docs_count`") dokumenty nie mają etykiet —
w GUI będą „Document 1", „Document 2". Dla przykładu z zgłoszenia (datasheet / application note /
errata) użytkownik nie rozróżni ich bez otwarcia. Gdyby to przeszkadzało, najtańsze późniejsze
rozszerzenie to jedna kolumna `docs_labels JSONB` — bez zmiany konwencji nazw plików.

---

## Zmiany w bazie danych (do zgłoszenia użytkownikowi)

1. `ALTER TABLE private.elements ADD COLUMN docs_count INTEGER NOT NULL DEFAULT 0`
2. `DROP TABLE private.element_documents` (0 wierszy — bezstratne)
3. `CREATE SCHEMA altium`, `CREATE SCHEMA kicad`
4. Widoki `public.table_*` → usunięte; zastąpione przez `altium.table_*` i `kicad.table_*`
5. Nowe role logowania `altium_user`, `kicad_user` (read-only, `search_path` ustawiony na swój schemat)

Dane w `private.elements` (2 wiersze) nietknięte.

---

## Pliki krytyczne

- `backend/utils.py` — widoki, role, oba generatory
- `backend/main.py` — startup DDL, endpointy dokumentów, delete/duplicate
- `backend/models.py`, `backend/schemas.py`
- `frontend/src/components/ElementDocuments.vue`, `ElementForm.vue`
- `frontend/src/utils/api.js`, `frontend/src/utils/db.js`
- `.env`, `example.env`

## Weryfikacja

1. `docker compose --env-file .env up --build -d backend frontend`
2. `psql`: `\dn`, `\dv altium.*`, `\dv kicad.*`, `\d private.elements`, `\du`
3. Test izolacji: `psql -U altium_user -d appdb -c "\dv"` → widzi tylko swoje; `SELECT * FROM kicad.table_1_x` → permission denied
4. Test `search_path`: `psql -U kicad_user -c "SELECT * FROM table_1_integrated_circuits LIMIT 1"` (bez schematu) → działa
5. `curl /api/settings/dblib`, `curl /api/settings/kicad-dbl` → poprawna treść wskazująca na nowe schematy
6. Upload 2 dokumentów przez GUI → `<uuid>_1.pdf`, `<uuid>_2.pdf` na dysku, `docs_count = 2`
7. Usunięcie dokumentu 1 → `<uuid>_1.pdf` to dawny `_2`, `docs_count = 1` (test przenumerowania)

---

## Dziennik wdrożenia

### 2026-09-19 — wdrożone w całości

Wszystko zweryfikowane na żywym stacku (`docker compose up --build`), nie tylko przez kompilację.

**Stan bazy po wdrożeniu — zweryfikowany:**
- `private.elements`: 2 wiersze, nietknięte, nowa kolumna `docs_count` (obie = 0)
- `private.element_documents`: usunięta (miała 0 wierszy)
- schematy `altium` i `kicad`, po 2 widoki w każdym; `public.table_*` usunięte
- role `altium_user`, `kicad_user` — read-only, `search_path` na swój schemat

**Wyniki testów izolacji:**

| test | wynik |
|---|---|
| `kicad_user` czyta `table_1_...` bez schematu (search_path) | ✅ działa |
| `kicad_user` → `altium.table_1_...` | ✅ permission denied |
| `kicad_user` → `private.elements` | ✅ permission denied |
| `altium_user` INSERT do swojego widoku | ✅ permission denied |
| `altium_user` → kolumna `"Symbols"` | ✅ column does not exist |
| lista widoków z filtrem uprawnień, per rola | ✅ każdy widzi tylko swoje 2 |
| granty po przebudowie widoków (nowa kategoria) | ✅ odtwarzane automatycznie |
| `.DbLib` / `.kicad_dbl` — wyciek kolumn drugiego narzędzia | ✅ 0 wystąpień w obie strony |

**Ograniczenie, którego nie da się obejść:** `pg_class` w Postgresie jest czytelny dla wszystkich,
więc surowy katalog systemowy (`\dv *.*` w psql) nadal **wymienia nazwy** widoków drugiego narzędzia.
Zawartości nie da się odczytać. Każdy klient filtrujący po uprawnieniach (w tym listy tabel w ODBC)
pokazuje już tylko właściwy zestaw — zweryfikowane zapytaniem z `has_schema_privilege`.

**Dwa błędy znalezione i naprawione przy weryfikacji:**

1. **Kolumny `Symbols\` i `Footprints\`** — `_libraryRefExpression` używało surowego f-stringa
   (`rf"""..."{alias}\""""`), w którym `\"` zostaje dosłownym backslashem, więc alias lądował
   w bazie z backslashem na końcu. KiCad by tych kolumn nie znalazł. Naprawione przez wydzielenie
   `_quotedAlias()` zamiast ręcznego escape'owania cudzysłowów w literale.

2. **`/files/` zwracało 404 — również dla głównego datasheetu** (regresja istniejąca *przed* tą turą,
   wprowadzona przy wcześniejszym przejściu na `proxy_pass` ze zmienną). Przy zmiennej w `proxy_pass`
   URI zawarte w zmiennej **zastępuje** URI żądania zamiast być prefiksem do podmiany, więc
   `/files/abc.pdf` szło do backendu jako `/files/` i gubiło nazwę pliku. Naprawione przez usunięcie
   części URI ze zmiennej (`http://backend:8000` bez `/files/`), tak samo jak w `location /`.

**Uwaga poboczna:** `other.updateViews` w `frontend/src/utils/api.js` wskazuje na nieistniejący
endpoint `POST /update-views` (404). Martwy eksport — nie jest podpięty pod żaden przycisk, a widoki
i tak przebudowują się same przy każdej zmianie kategorii/dostawcy. Zostawione bez zmian.

---

## 2026-09-19 (cd.) — przejście z kont serwisowych na konta osobowe

Użytkownik zakwestionował trzymanie hasła ODBC w `.env`. Słusznie — `altium_user`/`kicad_user`
były kontami *serwisowymi* ze współdzielonym hasłem w konfiguracji serwera.

**Nowy model:** 4 role grupowe NOLOGIN (`altium_users`, `altium_editors`, `kicad_users`,
`kicad_editors`) trzymają granty; każda osoba to osobna rola logowania z członkostwem w jednej
z nich. Żadnego hasła w `.env`. Jedno konto = ten sam login i hasło do apki, SVN i ODBC.

**Trzy założenia użytkownika, które wymagały korekty:**

1. *„zachowaj mateo i moje hasło"* — **niewykonalne automatycznie.** `private.users.password` to
   bcrypt (`$2a$06$`, jednokierunkowy), rola Postgresa trzyma weryfikator SCRAM. Jedno z drugiego
   nie wynika. Konieczne jednorazowe podanie hasła jawnego przez użytkownika.
2. *„users vs editors różnią się uprawnieniami"* — **nie na poziomie bazy.** Przez ODBC wszystko
   jest read-only (widoki + `Mode=Read`), a tworzenie kategorii idzie przez apkę jako `appuser`.
   Obie grupy danego narzędzia mają identyczne granty. Rozróżnienie musi egzekwować backend
   po `private.users.rank` — a dziś nie egzekwuje nic (#12 nadal otwarte).
3. *„przy dodaniu wiersza twórz rolę"* — **trigger na INSERT tego nie zrobi**, bo widzi już tylko
   hash. Stąd `private.user_create()`. Operacje niewymagające hasła jawnego (DELETE, zmiana
   rank/tool) są w pełni automatyczne triggerami.

**Dodane z konieczności:** kolumna `private.users.tool` (`altium`/`kicad`) — nie było czym odróżnić,
z którego narzędzia korzysta dana osoba. Mapowanie rang: `viewer` → `_users`, `editor`/`admin` → `_editors`.

**Znalezisko bezpieczeństwa:** `pg_hba.conf` ma `local` i `127.0.0.1` ustawione na **trust**. Izolacja
ról działa tylko dla połączeń zdalnych (`host all all all scram-sha-256`). Ktokolwiek z dostępem do
powłoki kontenera bazy loguje się jako dowolna rola bez hasła, łącznie z `appuser` (superuser).
Do rozważenia osobno.

**Pozostawione celowo:** role `altium_user`/`kicad_user` nie zostały usunięte, żeby nie zerwać
konfiguracji DSN w trakcie. Do usunięcia po migracji kont osobowych.

---

## 2026-09-19 (cd. 2) — weryfikacja „jedno konto = trzy miejsca"

Użytkownik poprosił o potwierdzenie, czy dodanie konta tworzy jednocześnie użytkownika SVN,
GUI i bazy. Odpowiedź: **dwa z trzech**, i po drodze wyszły dwa błędy sprzed tej tury.

| miejsce | działa? |
|---|---|
| baza danych / ODBC | ✅ tak (zweryfikowane po TCP, scram) |
| SVN | ✅ tak — **dopiero po naprawie**, wcześniej nie działało w ogóle |
| GUI webowe | ❌ nie — aplikacja nie ma żadnego logowania |

**Błąd 1 (istniejący): `$2a$` vs `$2y$`.** Apache `mod_authn_dbd` przyjmuje bcrypt wyłącznie
z prefiksem `$2y$` i odrzuca `$2a$`, który produkuje `crypt(..., gen_salt('bf'))` z README —
mimo że to ten sam algorytm. Udowodnione empirycznie: to samo hasło, `$2y$` → HTTP 200,
`$2a$` → 401 „Password Mismatch". Czyli **żadne konto założone wg README nigdy nie mogło
zalogować się do SVN**, łącznie z `mateo`.
Naprawione przez `private.user_password_hash()` (zapis z `$2y$`) + `private.user_check_password()`
(normalizacja prefiksu z powrotem na `$2a$`, bo pgcrypto nie rozumie `$2y$` — też zweryfikowane).

**Błąd 2 (istniejący): `svn/entrypoint.sh`** mapował rangi `server`/`admin`/`editor`/`user`,
a enum to `viewer`/`editor`/`admin`. `viewer` nie pasował do żadnej gałęzi `case`, więc nie
dostawał linii w authz i był odcięty od repozytorium. Poprawione na `viewer) = r`.

**Błąd 3 (mój, w `manage-users.sh`):** `readPassword` jest wołane w `$( )`, a `echo` po
`read -rsp` szedł na stdout i doklejał dwie puste linie do hasła. Przekierowane na stderr.

**Nowe:** `manage-users.sh` (add / passwd / rank / tool / list / delete), hasło czytane
z terminala, nigdy w argv ani w historii powłoki. Świadomie CLI, nie GUI — aplikacja webowa
nie ma autoryzacji, więc panel użytkowników w GUI byłby dostępny dla każdego w sieci.

**Usunięte:** role `altium_user` i `kicad_user`.

**Korekta od użytkownika:** ranga NIE ogranicza SVN. Dodanie elementu wymaga wrzucenia
plików `.SchLib`/`.PcbLib`, więc zapis do repozytorium jest minimum dla każdego konta.
`svn/entrypoint.sh` daje teraz `rw` wszystkim rangom (`viewer|editor|admin`). Rozróżnienie
viewer/editor dotyczy wyłącznie aplikacji webowej (np. tworzenie kategorii) i wciąż nie
jest tam egzekwowane (#12).

Zweryfikowane realnym klientem svn z konta o randze `viewer`: checkout → `Checked out
revision 1`, commit nowego pliku → `Committed revision 2`. Plik testowy usunięty
(rewizja 3), konto testowe skasowane.

---

## 2026-09-19 (cd. 3) — osobne bazy dla narzędzi CAD

**Problem zgłoszony z Altium:** zalogowany jako `mateo` (bez żadnych uprawnień do `private`
ani `kicad`) widział `users`, `tables`, `elements` i widoki obu narzędzi z prefiksami `table_N_`.

**Przyczyna, zweryfikowana tym samym sterownikiem (psqlODBC w kontenerze testowym):**
`SQLTables()` czyta nazwy wprost z `pg_class`, bez filtrowania po uprawnieniach. Role nie
mogą tego ukryć. Tabele obce (`postgres_fdw`) też są listowane (`[FOREIGN TABLE]`), więc
schowanie źródła w osobnym schemacie nie działa.

**Rozwiązanie:** bazy `altium_lib` i `kicad_lib`, w których jedynymi relacjami są widoki
nazwane dokładnie jak kategorie. Każdy widok czyta przez funkcję `SECURITY DEFINER`
(funkcji sterownik nie listuje), która pobiera wiersze z `appdb` przez `dblink`, łącząc się
lokalnym gniazdem jako wewnętrzna rola `<tool>_lib_reader` (LOGIN bez hasła → z sieci się
nie zaloguje). Przebudowa w jednej transakcji przy każdej zmianie kategorii/dostawcy.

**Zmiany w bazie:**
- nowe bazy `altium_lib`, `kicad_lib` (+ schemat `lib_internal`, rozszerzenie `dblink`)
- nowe role `altium_lib_reader`, `kicad_lib_reader`
- `REVOKE CONNECT, TEMPORARY ON DATABASE appdb FROM PUBLIC` — konta osobowe nie łączą się z appdb
- grupy `*_users`/`*_editors` straciły wszystkie uprawnienia w appdb, mają CONNECT tylko do swojej bazy
- `ALTER ROLE ... RESET search_path` dla istniejących kont (mateo), funkcje przestały go ustawiać

**Wynik (psqlODBC):** `altium_lib` → dokładnie `fpga`, `integrated_circuits` jako `[VIEW]`;
logowanie do `kicad_lib` i `appdb` odrzucane (`permission denied for database`).

**Niezweryfikowane:** format `FieldMap` przy `UseTableSchemaName=0` (`FieldName=<tabela>.<kolumna>`
bez schematu) — wyprowadzony, nie potwierdzony w samym Altium.

---

## 2026-09-19 (cd. 4) — przywrócenie wyglądu dashboardu

Wzór: commit `d858152` (wersja Flask, `server/app/templates/dashboard.html` + `static/css/dashboard.css`),
pobrany z GitHuba przez API, bo lokalne repo to płytki klon z jednym commitem.
Układ odtworzony 1:1: duża karta (liczba elementów, nowe dzisiaj, ostatnio dodany), dwie małe
(Footprinty, Symbole), siatka kafelków kategorii; hover z uniesieniem, akcent `--onyks-accent`.

**Korekta wcześniejszego stanu:** `/repository/statistics` zwracał na sztywno 1/2/3/4 — realnego
liczenia nie było. Teraz: `svn list -R` + parsowanie każdego `.SchLib`/`.PcbLib` przez pyaltiumlib
(jak stary `repository_worker.py`), wynik cache'owany per rewizja SVN, liczenie w wątku
(`asyncio.to_thread`) pod `asyncio.Lock`. Stary kod miał zamienione symbole z footprintami
(`footprints_amount = r.get("symbols_amount")`) — nie powielone.

`GET /element/number?since=<ISO>` — „nowe dzisiaj" liczone od lokalnej północy przeglądarki.
Dashboard czyści `setInterval` przy opuszczeniu strony (wcześniej wyciekał).

Zweryfikowane: 5 SchLib / 1 PcbLib zgodne z `svn list`, `since` poprawne. Wygląd — niezweryfikowany
wizualnie (brak przeglądarki).
